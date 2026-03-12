"""
Agent 1 — Acquisition intelligente des ASINs via Claude AI SDK.

Responsabilités :
- Lire les restrictions du compte
- Choisir les catégories à scanner
- Éviter les doublons récents
- Retourner une List[Deal] filtrée et enrichie (prix FR + frais)
"""
import json
import anthropic

from models.deal import Deal
from utils.fees_calculator import calculate_total_fees, get_size_tier
from clients.keepa_client import detect_arbitrage, calculate_score, recommend_marketplace
from config import (
    ANTHROPIC_API_KEY, AGENT_MAX_ITERATIONS,
    BSR_MIN, BSR_MAX, BUY_BOX_MIN, BUY_BOX_MAX, BUY_BOX_90J_MIN,
    FBA_SELLERS_MIN, FBA_SELLERS_MAX, EXCLURE_AMAZON_VENDEUR, EFN_DESTINATIONS,
)
from agents.agent_tools import (
    tool_read_restrictions,
    tool_query_past_scanned_asins,
    tool_get_available_categories,
    tool_search_keepa_category,
    tool_get_asin_details_fr,
    tool_fetch_multimarket_prices,
)

SYSTEM_PROMPT = """Tu es un agent d'acquisition ASIN pour un outil d'Online Arbitrage Amazon FBA France.
Ton rôle : décider quelles catégories scanner sur Keepa, récupérer les ASINs pertinents, et collecter leurs données produit FR.

Note : après ta réponse "ACQUISITION TERMINÉE", le pipeline Python prend le relais automatiquement pour :
- Calculer les frais, ROI FR, profit net estimé
- Enrichir les prix DE/IT/ES via Keepa (_enrich_multimarket)
- Calculer la meilleure marketplace et les alertes arbitrage
Tu n'as PAS à faire ces calculs — collecte uniquement les données FR.

Workflow à suivre dans l'ordre :
1. Appelle read_restrictions → note account_profile, restricted_categories, restricted_asins, restricted_brands, approved_brands
2. Appelle query_past_scanned_asins → note les ASINs déjà vus récemment (à éviter)
3. Appelle get_available_categories → liste des catégories Keepa disponibles
4. Détermine les catégories à scanner selon le profil compte (voir règles ci-dessous)
5. Pour chaque catégorie retenue :
   a. Appelle search_keepa_category avec les filtres standard
   b. Retire de la liste les ASINs déjà scannés et les ASINs dans restricted_asins
   c. Appelle get_asin_details_fr avec les ASINs restants (batch max 50)
6. Une fois toutes les catégories traitées, réponds uniquement :
   "ACQUISITION TERMINÉE - X produits collectés"

Règles sur les marques :
- restricted_brands = marques INTERDITES (gatées, génériques) → exclure tout ASIN de ces marques
- approved_brands = marques déjà confirmées ELIGIBLE par Seller Central → les prioriser
- Ignorer systématiquement les ASINs avec brand="Générique", brand="" ou brand absente

Règles sur le profil compte (account_profile) :
- Lis toujours account_profile dans les restrictions
- Si is_new_account = true ET approved_categories est vide :
  → Scanner UNIQUEMENT les catégories non-gatées : Toys & Games, Sports & Outdoors, Kitchen,
    Home & Garden, Electronics, Pet Supplies, Office Products
  → NE PAS scanner Health & Beauty, Grocery, Baby, Jewelry, Watches, Clothing, Shoes, etc.
- Si approved_categories est rempli : scanner en priorité ces catégories approuvées
- Ne JAMAIS scanner une catégorie présente dans restricted_categories

Règles de filtrage :
- Ne JAMAIS scanner une catégorie présente dans restricted_categories
- Exclure les ASINs présents dans restricted_asins avant d'appeler get_asin_details_fr
- Filtres par défaut pour search_keepa_category :
  bsr_min=1000, bsr_max=50000, buy_box_min_cents=1500, buy_box_max_cents=20000, max_asins=50
- Chaque réponse d'outil Keepa inclut "tokens_left" (solde réel du compte) → adapte ton comportement :
  - tokens_left < 100 : réduire max_asins à 10, scanner max 2 catégories
  - tokens_left < 30 : arrêter immédiatement et répondre "ACQUISITION TERMINÉE - X produits collectés"
- Si le budget tokens fourni au départ est faible (< 100) : même comportement restrictif
"""

TOOLS_SCHEMA = [
    {
        "name": "read_restrictions",
        "description": "Lit le fichier de restrictions du compte (catégories interdites, ASINs interdits, marques interdites).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "query_past_scanned_asins",
        "description": "Retourne les ASINs déjà scannés récemment pour éviter les doublons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {
                    "type": "integer",
                    "description": "Nombre de jours à regarder en arrière (défaut : 7)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_available_categories",
        "description": "Liste les catégories disponibles dans Keepa avec leurs IDs.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_keepa_category",
        "description": "Cherche des ASINs dans une catégorie Keepa selon des filtres BSR et prix. Retourne une liste d'ASINs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_name": {"type": "string", "description": "Nom exact de la catégorie (ex: 'Toys & Games')"},
                "bsr_min": {"type": "integer", "description": "BSR minimum"},
                "bsr_max": {"type": "integer", "description": "BSR maximum"},
                "buy_box_min_cents": {"type": "integer", "description": "Prix Buy Box minimum en centimes (ex: 1500 = 15€)"},
                "buy_box_max_cents": {"type": "integer", "description": "Prix Buy Box maximum en centimes (ex: 20000 = 200€)"},
                "max_asins": {"type": "integer", "description": "Nombre maximum d'ASINs à retourner"},
            },
            "required": ["category_name", "bsr_min", "bsr_max", "buy_box_min_cents", "buy_box_max_cents", "max_asins"],
        },
    },
    {
        "name": "get_asin_details_fr",
        "description": "Récupère les détails complets (prix FR, BSR, vendeurs FBA, poids, etc.) pour une liste d'ASINs depuis Keepa. Coûte 1 token Keepa par ASIN.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asins": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Liste d'ASINs Amazon (max 50 par appel)",
                },
                "category_name": {
                    "type": "string",
                    "description": "Nom de la catégorie pour ces ASINs",
                },
            },
            "required": ["asins", "category_name"],
        },
    },
]


class AcquisitionAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._collected_products: list[dict] = []
        self.last_tokens_left: int | None = None

    def _dispatch_tool(self, name: str, input_data: dict):
        if name == "read_restrictions":
            return tool_read_restrictions()
        elif name == "query_past_scanned_asins":
            return tool_query_past_scanned_asins(input_data.get("days_back", 7))
        elif name == "get_available_categories":
            return tool_get_available_categories()
        elif name == "search_keepa_category":
            return tool_search_keepa_category(**input_data)
        elif name == "get_asin_details_fr":
            result = tool_get_asin_details_fr(
                input_data["asins"],
                input_data.get("category_name", "Unknown"),
            )
            # Accumulation des produits valides (side effect)
            valid = [p for p in result if "error" not in p and p.get("asin")]
            self._collected_products.extend(valid)
            return {
                "count": len(result),
                "valid": len(valid),
                "products_collected_total": len(self._collected_products),
            }
        return {"error": f"Outil inconnu: {name}"}

    def _products_to_deals(self, products: list[dict], restrictions: dict | None = None) -> list[Deal]:
        """Convertit les produits bruts Keepa en objets Deal filtrés et enrichis."""
        restricted_asins = set((restrictions or {}).get("restricted_asins", []))
        restricted_brands = set(
            b.lower() for b in (restrictions or {}).get("restricted_brands", [])
        )

        deals = []
        for p in products:
            try:
                asin = p.get("asin", "")
                if not asin:
                    continue

                # Filtre restrictions
                if asin in restricted_asins:
                    continue
                brand = (p.get("brand") or "").lower()
                if brand and brand in restricted_brands:
                    continue

                # Filtres Keepa standards
                bsr = p.get("bsr_fr")
                if not bsr or not (BSR_MIN <= bsr <= BSR_MAX):
                    continue
                if EXCLURE_AMAZON_VENDEUR and p.get("amazon_en_stock"):
                    continue
                nb_fba = p.get("nb_vendeurs_fba", 0)
                if not (FBA_SELLERS_MIN <= nb_fba <= FBA_SELLERS_MAX):
                    continue

                buy_box_moy = p.get("buy_box_90j_moy_fr")
                buy_box_fr = p.get("buy_box_fr")
                if not buy_box_moy or buy_box_moy < BUY_BOX_90J_MIN:
                    continue
                if buy_box_fr and not (BUY_BOX_MIN <= buy_box_fr <= BUY_BOX_MAX):
                    continue

                size_tier = p.get("size_tier", "large_standard_400")
                weight_g = p.get("weight_g", 500)
                category = p.get("categorie", "Toys & Games")

                fees_fr = calculate_total_fees(buy_box_moy, category, size_tier, weight_g, "FR")

                deal = Deal(
                    asin=asin,
                    titre=p.get("titre", ""),
                    categorie=category,
                    bsr_fr=bsr,
                    nb_vendeurs_fba=nb_fba,
                    amazon_en_stock=p.get("amazon_en_stock", False),
                    buy_box_fr=buy_box_fr,
                    buy_box_90j_moy_fr=buy_box_moy,
                    buy_box_90j_min_fr=p.get("buy_box_90j_min_fr"),
                    referral_fee=fees_fr["referral_fee"],
                    frais_fba=fees_fr["frais_fba"],
                    envoi_fba=fees_fr["envoi_fba"],
                    urssaf=fees_fr["urssaf"],
                    total_frais=fees_fr["total_frais"],
                    lien_google_shopping=p.get("lien_google_shopping"),
                    weight_g=weight_g,
                    size_tier=size_tier,
                )

                # ROI FR estimé (70% du buy box comme prix achat)
                prix_achat_estime = round(buy_box_moy * 0.7, 2)
                profit_fr = round(buy_box_moy - fees_fr["total_frais"] - prix_achat_estime, 2)
                deal.roi_fr = round((profit_fr / prix_achat_estime) * 100, 1) if prix_achat_estime > 0 else 0
                deal.profit_net_fr = profit_fr

                # Frais EFN DE (référence cross-border)
                fees_de = calculate_total_fees(buy_box_moy, category, size_tier, weight_g, "DE")
                deal.frais_efn = fees_de.get("total_frais")

                deal.score_deal = calculate_score(deal)
                deals.append(deal)

            except Exception as e:
                print(f"[Agent 1] Erreur conversion {p.get('asin', '?')}: {e}")

        return deals

    def _enrich_multimarket(self, deals: list[Deal]) -> list[Deal]:
        """Récupère les prix réels DE/IT/ES et recalcule les métriques cross-border."""
        asins = [d.asin for d in deals]
        print(f"[Agent 1] Enrichissement multimarket ({len(asins)} ASINs × 3 marchés)...")
        try:
            prices = tool_fetch_multimarket_prices(asins, list(EFN_DESTINATIONS))
            tokens_left = prices.pop("_tokens_left", None)
            if tokens_left is not None:
                self.last_tokens_left = tokens_left
        except Exception as e:
            print(f"[Agent 1] Erreur multimarket: {e}")
            return deals

        deals_map = {d.asin: d for d in deals}
        for asin, mp_prices in prices.items():
            if asin not in deals_map:
                continue
            deal = deals_map[asin]
            deal.buy_box_de = mp_prices.get("DE")
            deal.buy_box_it = mp_prices.get("IT")
            deal.buy_box_es = mp_prices.get("ES")

            # Recalcul métriques avec prix réels
            fees_by_mp = {}
            for mp in EFN_DESTINATIONS:
                sell_price = getattr(deal, f"buy_box_{mp.lower()}") or deal.buy_box_90j_moy_fr
                fees_by_mp[mp] = calculate_total_fees(
                    sell_price, deal.categorie, deal.size_tier or "large_standard_400", deal.weight_g or 500, mp
                )

            best_mp, best_roi, gain = recommend_marketplace(deal, fees_by_mp)
            deal.marketplace_recommandee = best_mp
            deal.roi_meilleur = best_roi
            deal.gain_vs_fr = gain

            alerte, ecart = detect_arbitrage(deal)
            deal.alerte_arbitrage = alerte
            deal.ecart_arbitrage = ecart
            deal.score_deal = calculate_score(deal)

        return deals

    def run(self, token_budget: int = 500) -> list[Deal]:
        """Lance l'agent et retourne la liste de deals candidats."""
        self._collected_products = []
        restrictions = None

        messages = [{
            "role": "user",
            "content": (
                f"Lance l'acquisition ASIN pour ce run OA.\n"
                f"Budget tokens Keepa disponible : {token_budget}\n"
                f"Suis le workflow décrit dans tes instructions système."
            ),
        }]

        iterations = 0
        while iterations < AGENT_MAX_ITERATIONS:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS_SCHEMA,
                messages=messages,
            )
            iterations += 1

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._dispatch_tool(block.name, block.input)
                        # Capture des restrictions pour le filtrage final
                        if block.name == "read_restrictions" and isinstance(result, dict):
                            restrictions = result
                        # Capture du solde Keepa réel
                        if isinstance(result, dict) and "tokens_left" in result and result["tokens_left"] is not None:
                            self.last_tokens_left = result["tokens_left"]
                        elif isinstance(result, list):
                            meta = next((x for x in result if isinstance(x, dict) and "_tokens_left" in x), None)
                            if meta:
                                self.last_tokens_left = meta["_tokens_left"]
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        print(f"[Agent 1] {len(self._collected_products)} produits bruts collectés ({iterations} itérations).")
        deals = self._products_to_deals(self._collected_products, restrictions)
        print(f"[Agent 1] {len(deals)} deals valides après filtrage.")
        skip_mm = getattr(self, "_skip_multimarket", False)
        if deals and not skip_mm:
            deals = self._enrich_multimarket(deals)
            print(f"[Agent 1] Enrichissement multimarket terminé. Tokens restants : {self.last_tokens_left}")
        elif deals:
            print("[Agent 1] Multimarket désactivé (stratégie réduite).")
        return deals
