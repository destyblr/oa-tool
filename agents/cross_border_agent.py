"""
CrossBorderAgent (v2) — Sourcing EU natif.

Nouveau rôle : cherche directement sur DE/IT/ES des ASINs avec un prix EU > prix FR + 15%.
N'analyse plus les deals Agent 1 — c'est un agent indépendant qui alimente l'onglet Cross Border.
"""
import json
import anthropic

from config import ANTHROPIC_API_KEY, AGENT_MAX_ITERATIONS
from agents.agent_tools import (
    tool_search_keepa_eu,
    tool_get_asin_details_eu,
    tool_get_fr_prices_for_asins,
    tool_calculate_efn_profitability,
    tool_get_efn_fee_table,
    tool_save_cross_border_opportunity,
)

SYSTEM_PROMPT = """Tu es un agent de sourcing cross-border pour Online Arbitrage Amazon FBA.

## Concept
Trouver des produits qui se vendent PLUS CHER sur DE/IT/ES que sur FR.
Acheter en FR (via Amazon.fr ou retailer FR), revendre sur EU via EFN = profit.

## Critères d'une opportunité valide
- prix_eu > prix_fr_avg90 × 1.15 (écart minimum 15%)
- profit_net EFN >= 5€
- BSR EU < 80 000
- Amazon N'est PAS vendeur sur la marketplace EU cible
- nb_vendeurs_fba >= 1 sur EU

## Workflow strict

### Étape 1 — Frais EFN (une seule fois)
Appelle get_efn_fee_table.

### Étape 2 — Recherche sur chaque domaine EU
Pour chaque domaine dans l'ordre DE, IT, ES :
  a. Appelle search_keepa_eu : domain=<domaine>, bsr_min=1000, bsr_max=80000,
     buy_box_min_cents=1500, buy_box_max_cents=20000, max_asins=15
  b. Si tokens_left < 50 → STOP immédiat, aller à l'étape finale
  c. Appelle get_asin_details_eu pour les ASINs trouvés (batches de 10 max)
  d. Garde uniquement : amazon_en_stock=False ET nb_vendeurs_fba >= 1 ET buy_box_current > 0

### Étape 3 — Prix FR
Pour chaque lot d'ASINs filtrés (max 10 par appel) :
  a. Appelle get_fr_prices_for_asins
  b. Skip si amazon_en_stock_fr = True
  c. Skip si buy_box_fr_avg90 est null ou 0
  d. Calcule écart : (buy_box_current - buy_box_fr_avg90) / buy_box_fr_avg90 × 100
  e. Garde uniquement si écart >= 15%

### Étape 4 — Rentabilité EFN
Pour chaque ASIN avec écart >= 15% :
  a. Appelle calculate_efn_profitability :
     - sell_price = buy_box_current (prix EU)
     - buy_price = buy_box_fr_avg90 × 0.70 (estimation achat FR)
     - category = "Kitchen" (défaut si inconnu)
     - size_tier et weight_g depuis get_asin_details_eu
     - marketplace = domaine EU cible
  b. Skip si profit_net < 5€

### Étape 5 — Sauvegarde
Pour chaque opportunité validée (écart >=15% ET profit_net >=5€) :
  Appelle save_cross_border_opportunity avec toutes les données.

### Étape finale
Réponds : "CROSS-BORDER EU TERMINÉ — X opportunités sauvegardées sur DE/IT/ES"

## Règles importantes
- Traiter DE en premier (plus grand marché EU)
- Grouper les appels en batches de 10 ASINs max
- Ne jamais appeler search_keepa_eu si tokens_left < 50
- alerte_arbitrage format : "DE +22%" ou "IT +18%"
"""

TOOLS_SCHEMA = [
    {
        "name": "get_efn_fee_table",
        "description": "Retourne la table des frais EFN. Appeler une seule fois au départ.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_keepa_eu",
        "description": "Cherche des ASINs sur un domaine EU (DE/IT/ES) via Keepa. Coût ~2-5 tokens.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["DE", "IT", "ES"]},
                "bsr_min": {"type": "integer"},
                "bsr_max": {"type": "integer"},
                "buy_box_min_cents": {"type": "integer"},
                "buy_box_max_cents": {"type": "integer"},
                "max_asins": {"type": "integer"},
                "category_name": {"type": "string", "description": "Optionnel"},
            },
            "required": ["domain", "bsr_min", "bsr_max", "buy_box_min_cents", "buy_box_max_cents", "max_asins"],
        },
    },
    {
        "name": "get_asin_details_eu",
        "description": "Récupère prix buy box, BSR, vendeurs FBA, poids pour des ASINs sur EU. Coût 1 token/ASIN.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asins": {"type": "array", "items": {"type": "string"}},
                "domain": {"type": "string", "enum": ["DE", "IT", "ES"]},
            },
            "required": ["asins", "domain"],
        },
    },
    {
        "name": "get_fr_prices_for_asins",
        "description": "Récupère les prix buy box FR pour comparer avec les prix EU. Coût 1 token/ASIN.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asins": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["asins"],
        },
    },
    {
        "name": "calculate_efn_profitability",
        "description": "Calcule profit net et ROI EFN pour vendre depuis FR vers EU.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sell_price": {"type": "number"},
                "buy_price": {"type": "number"},
                "category": {"type": "string"},
                "size_tier": {"type": "string"},
                "weight_g": {"type": "number"},
                "marketplace": {"type": "string", "enum": ["DE", "IT", "ES"]},
            },
            "required": ["sell_price", "buy_price", "category", "size_tier", "weight_g", "marketplace"],
        },
    },
    {
        "name": "save_cross_border_opportunity",
        "description": "Sauvegarde une opportunité cross-border validée dans Supabase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asin": {"type": "string"},
                "titre": {"type": "string"},
                "domain_source": {"type": "string", "enum": ["DE", "IT", "ES"]},
                "buy_box_eu": {"type": "number"},
                "buy_box_fr": {"type": "number"},
                "size_tier": {"type": "string"},
                "weight_g": {"type": "number"},
                "categorie": {"type": "string"},
                "profit_net": {"type": "number"},
                "roi": {"type": "number"},
                "bsr_eu": {"type": ["integer", "null"]},
                "alerte_arbitrage": {"type": "string"},
                "ecart_arbitrage": {"type": "number"},
            },
            "required": ["asin", "titre", "domain_source", "buy_box_eu", "buy_box_fr",
                         "size_tier", "weight_g", "categorie", "profit_net", "roi"],
        },
    },
]


class CrossBorderAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.last_tokens_left: int | None = None
        self.opportunities_saved: int = 0

    def _dispatch_tool(self, name: str, input_data: dict):
        if name == "get_efn_fee_table":
            return tool_get_efn_fee_table()
        elif name == "search_keepa_eu":
            return tool_search_keepa_eu(**input_data)
        elif name == "get_asin_details_eu":
            return tool_get_asin_details_eu(input_data["asins"], input_data["domain"])
        elif name == "get_fr_prices_for_asins":
            return tool_get_fr_prices_for_asins(input_data["asins"])
        elif name == "calculate_efn_profitability":
            return tool_calculate_efn_profitability(**input_data)
        elif name == "save_cross_border_opportunity":
            result = tool_save_cross_border_opportunity(**input_data)
            if result.get("status") == "ok":
                self.opportunities_saved += 1
            return result
        return {"error": f"Outil inconnu: {name}"}

    def _update_tokens(self, result):
        if isinstance(result, dict):
            tl = result.get("_tokens_left") or result.get("tokens_left")
            if tl is not None:
                self.last_tokens_left = tl
        elif isinstance(result, list):
            meta = next((x for x in result if isinstance(x, dict) and "_tokens_left" in x), None)
            if meta:
                self.last_tokens_left = meta["_tokens_left"]

    def run(self, token_budget: int = 150) -> int:
        """Lance le sourcing cross-border EU. Retourne le nombre d'opportunités sauvegardées."""
        messages = [{
            "role": "user",
            "content": (
                f"Lance la recherche cross-border EU.\n"
                f"Budget tokens Keepa disponible : {token_budget}\n"
                f"Traite les domaines dans l'ordre : DE, IT, ES.\n"
                f"Suis exactement le workflow décrit dans tes instructions."
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
                        self._update_tokens(result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, ensure_ascii=False, default=str),
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        tokens_info = f" | Keepa tokens restants: {self.last_tokens_left}" if self.last_tokens_left is not None else ""
        print(f"[Agent 2 EU] {self.opportunities_saved} opportunités sauvegardées ({iterations} itérations).{tokens_info}")
        return self.opportunities_saved
