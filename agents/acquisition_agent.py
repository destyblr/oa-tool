"""
Agent 1 — Acquisition ASIN (pur Python, sans Claude AI).

Flow entrelacé (catégorie par catégorie) :
  Pour chaque catégorie :
    1. product_finder Keepa (tokens_left >= 5 requis)
    2. Pour chaque ASIN retourné immédiatement :
       a. check_eligibility SP API (0 token)
       b. RESTRICTED/HAZMAT → skip
       c. ELIGIBLE/UNKNOWN → fetch FR (1 token, wait=False)
       d. Filtre BSR / prix / vendeurs
       e. Fetch prix DE/IT/ES (3 tokens, wait=False) si dispo
       f. Calcule frais + ROI + score → sauvegarde Supabase
       g. tokens < 4 → stop tout
"""
import time
import json
import requests as _req
from pathlib import Path
from datetime import date, timedelta

import keepa as keepa_lib

from config import (
    KEEPA_API_KEY,
    BSR_MIN, BSR_MAX, BUY_BOX_MIN, BUY_BOX_MAX, BUY_BOX_90J_MIN,
    FBA_SELLERS_MIN, FBA_SELLERS_MAX, EXCLURE_AMAZON_VENDEUR, EFN_DESTINATIONS,
)
from models.deal import Deal
from clients.sp_api_client import check_eligibility
from clients.keepa_client import (
    get_buy_box_stats, amazon_in_stock, count_fba_sellers, get_bsr,
    generate_shopping_link, calculate_score, detect_arbitrage, recommend_marketplace,
    KEEPA_CATEGORY_IDS, KEEPA_DOMAINS,
)
from utils.fees_calculator import calculate_total_fees, get_size_tier
from clients.supabase_client import get_client, save_deals

RESTRICTIONS_PATH = Path(__file__).parent.parent / "restrictions.json"
APPROVED_BRANDS_PATH = Path(__file__).parent.parent / "approved_brands.json"


def _load_restrictions() -> dict:
    try:
        with open(RESTRICTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"restricted_asins": [], "restricted_brands": []}
    try:
        if APPROVED_BRANDS_PATH.exists():
            with open(APPROVED_BRANDS_PATH, "r", encoding="utf-8") as f:
                data["approved_brands"] = json.load(f).get("approved_brands", [])
    except Exception:
        data["approved_brands"] = []
    return data


def _get_past_scanned_asins(days_back: int = 7) -> set:
    client = get_client()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    try:
        resp = client.table("deals").select("asin").gte("date_scan", since).execute()
        return {r["asin"] for r in (resp.data or [])}
    except Exception:
        return set()


def _product_to_deal(product: dict, category: str, statut: str, api) -> Deal | None:
    """Construit un Deal depuis un produit Keepa brut. Retourne None si filtres non passés."""
    asin = product.get("asin", "")
    titre = product.get("title", "") or ""

    bsr = get_bsr(product)
    if not bsr or not (BSR_MIN <= bsr <= BSR_MAX):
        return None

    # Filtre Private Label : max historique vendeurs <= 2 → probablement PL → skip
    stats = product.get("stats", {})
    max_counts = stats.get("max", [])
    if len(max_counts) > 10 and max_counts[10] is not None:
        try:
            val = max_counts[10]
            if isinstance(val, list):
                val = max((v for v in val if isinstance(v, (int, float))), default=None)
            if val is not None and val <= 2:
                print(f"  [PL] {asin} — max {val} vendeurs historiques → skip")
                return None
        except Exception:
            pass

    if EXCLURE_AMAZON_VENDEUR and amazon_in_stock(product):
        return None

    nb_fba = count_fba_sellers(product)
    if not (FBA_SELLERS_MIN <= nb_fba <= FBA_SELLERS_MAX):
        return None

    bb_stats = get_buy_box_stats(product)
    buy_box_fr = bb_stats["current"]
    buy_box_moy = bb_stats["avg90"]
    buy_box_min = bb_stats["min90"]

    if not buy_box_moy or buy_box_moy < BUY_BOX_90J_MIN:
        return None
    if buy_box_fr and not (BUY_BOX_MIN <= buy_box_fr <= BUY_BOX_MAX):
        return None

    weight_g = product.get("packageWeight") or product.get("itemWeight") or 500
    length = product.get("packageLength") or 0
    width  = product.get("packageWidth") or 0
    height = product.get("packageHeight") or 0
    size_tier = get_size_tier(weight_g, length, width, height)

    fees_fr = calculate_total_fees(buy_box_moy, category, size_tier, weight_g, "FR")
    prix_achat_estime = round(buy_box_moy * 0.7, 2)
    profit_fr = round(buy_box_moy - fees_fr["total_frais"] - prix_achat_estime, 2)
    roi_fr = round((profit_fr / prix_achat_estime) * 100, 1) if prix_achat_estime > 0 else 0

    fees_de = calculate_total_fees(buy_box_moy, category, size_tier, weight_g, "DE")

    deal = Deal(
        asin=asin,
        titre=titre,
        categorie=category,
        statut=statut,
        bsr_fr=bsr,
        nb_vendeurs_fba=nb_fba,
        amazon_en_stock=amazon_in_stock(product),
        buy_box_fr=buy_box_fr,
        buy_box_90j_moy_fr=buy_box_moy,
        buy_box_90j_min_fr=buy_box_min,
        referral_fee=fees_fr["referral_fee"],
        frais_fba=fees_fr["frais_fba"],
        frais_efn=fees_de.get("total_frais"),
        envoi_fba=fees_fr["envoi_fba"],
        urssaf=fees_fr["urssaf"],
        total_frais=fees_fr["total_frais"],
        roi_fr=roi_fr,
        profit_net_fr=profit_fr,
        lien_google_shopping=generate_shopping_link(titre, asin),
        weight_g=weight_g,
        size_tier=size_tier,
    )

    # Marketplace FR par défaut
    deal.marketplace_recommandee = "FR"
    deal.roi_meilleur = roi_fr
    deal.gain_vs_fr = 0.0
    deal.score_deal = calculate_score(deal)
    return deal


def _enrich_multimarket(deal: Deal, api) -> Deal:
    """Fetch prix DE/IT/ES et recalcule métriques. Coût : 3 tokens."""
    try:
        fees_by_mp = {}
        for mp in EFN_DESTINATIONS:
            domain_code = KEEPA_DOMAINS.get(mp)
            if not domain_code:
                continue
            products = api.query(
                [deal.asin], domain=mp, history=False, stats=90, wait=False
            )
            if products:
                bb = get_buy_box_stats(products[0], mp)
                setattr(deal, f"buy_box_{mp.lower()}", bb["current"])
                sell_price = bb["current"] or deal.buy_box_90j_moy_fr
                fees_by_mp[mp] = calculate_total_fees(
                    sell_price, deal.categorie,
                    deal.size_tier or "large_standard_400",
                    deal.weight_g or 500, mp
                )

        if fees_by_mp:
            best_mp, best_roi, gain = recommend_marketplace(deal, fees_by_mp)
            deal.marketplace_recommandee = best_mp
            deal.roi_meilleur = best_roi
            deal.gain_vs_fr = gain
            alerte, ecart = detect_arbitrage(deal)
            deal.alerte_arbitrage = alerte
            deal.ecart_arbitrage = ecart
            deal.score_deal = calculate_score(deal)
    except Exception as e:
        print(f"[Agent 1] Erreur multimarket {deal.asin}: {e}")
    return deal


class AcquisitionAgent:
    def __init__(self):
        self.deals_saved = 0
        self.tokens_start = 0
        self.tokens_end = 0

    def run(self) -> list[Deal]:
        api = keepa_lib.Keepa(KEEPA_API_KEY)
        # keepa initialise tokens_left=0, on query directement et on override
        try:
            r = _req.get("https://api.keepa.com/token", params={"key": KEEPA_API_KEY}, timeout=10)
            self.tokens_start = int(r.json().get("tokensLeft", 0))
        except Exception:
            self.tokens_start = 0
        api.tokens_left = self.tokens_start  # Override pour que getattr fonctionne
        print(f"[Agent 1] Tokens disponibles : {self.tokens_start}")

        restrictions = _load_restrictions()
        restricted_asins = set(restrictions.get("restricted_asins", []))
        restricted_brands = {b.lower() for b in restrictions.get("restricted_brands", [])}
        already_scanned = _get_past_scanned_asins()

        # ── Traitement entrelacé : catégorie par catégorie ────────────────────
        all_deals = []
        done = False

        for cat_name, cat_id in KEEPA_CATEGORY_IDS.items():
            if done:
                break

            tokens_left = getattr(api, "tokens_left", 0)
            if tokens_left < 5:
                print(f"[Agent 1] Tokens insuffisants pour product_finder, stop.")
                break

            try:
                params = keepa_lib.ProductParams(
                    rootCategory=str(cat_id),
                    current_SALES_gte=BSR_MIN,
                    current_SALES_lte=BSR_MAX,
                    current_BUY_BOX_SHIPPING_gte=int(BUY_BOX_MIN * 100),
                    current_BUY_BOX_SHIPPING_lte=int(BUY_BOX_MAX * 100),
                )
                asins = list(api.product_finder(params, domain="FR", wait=False))
                print(f"[Agent 1] {cat_name} : {len(asins)} ASINs")
                time.sleep(0.2)
            except Exception as e:
                print(f"[Agent 1] product_finder {cat_name} : {e}")
                break

            for asin in asins:
                if asin in already_scanned or asin in restricted_asins:
                    continue

                tokens_left = getattr(api, "tokens_left", 0)
                if tokens_left < 4:
                    print("[Agent 1] Tokens épuisés — stop propre.")
                    done = True
                    break

                statut = check_eligibility(asin)
                print(f"  {asin} ({cat_name}) → {statut}")

                if statut in ("RESTRICTED", "HAZMAT"):
                    continue

                tokens_left = getattr(api, "tokens_left", 0)
                if tokens_left < 1:
                    print("[Agent 1] Tokens épuisés — stop propre.")
                    done = True
                    break

                try:
                    products = api.query(
                        [asin], domain="FR", history=False, offers=20, stats=90, wait=False
                    )
                except Exception as e:
                    print(f"  [Keepa] Erreur fetch FR {asin}: {e}")
                    done = True
                    break

                if not products:
                    continue

                brand = (products[0].get("brand") or "").lower()
                if brand and brand in restricted_brands:
                    continue

                deal = _product_to_deal(products[0], cat_name, statut, api)
                if not deal:
                    continue

                tokens_left = getattr(api, "tokens_left", 0)
                if tokens_left >= 3:
                    deal = _enrich_multimarket(deal, api)
                else:
                    print(f"  [Agent 1] Pas assez de tokens pour multimarket ({tokens_left})")

                save_deals([deal])
                all_deals.append(deal)
                self.deals_saved += 1
                print(f"  => Sauvegardé ({deal.statut}, ROI {deal.roi_meilleur}%)")

        self.tokens_end = getattr(api, "tokens_left", 0)
        tokens_used = self.tokens_start - self.tokens_end
        print(f"\n[Agent 1] Terminé — {self.deals_saved} deals sauvegardés | {tokens_used} tokens utilisés | {self.tokens_end} restants")
        return all_deals


