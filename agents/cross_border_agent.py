"""
Agent 2 — Cross-border EU natif (pur Python, sans Claude AI).

Flow entrelacé (domaine/catégorie par catégorie) :
  Pour chaque domaine EU (DE, IT, ES) et chaque catégorie :
    1. product_finder (tokens_left >= 5 requis)
    2. Pour chaque ASIN retourné immédiatement :
       a. check_eligibility SP API FR (0 token) → RESTRICTED/HAZMAT → skip
       b. Fetch prix EU (1 token, wait=False)
       c. Fetch prix FR (1 token, wait=False)
       d. prix EU > prix FR + 15% ? → sinon skip
       e. Calcule frais EFN + ROI
       f. profit_net >= 5€ ? → sauvegarde Supabase
       g. tokens < 3 → stop tout
"""
import time
import requests as _req
from datetime import datetime, timezone

import keepa as keepa_lib
from clients.sp_api_client import check_eligibility

from config import (
    KEEPA_API_KEY,
    BSR_MIN, BUY_BOX_MIN, BUY_BOX_MAX, ARBITRAGE_SPREAD_MIN,
)
from clients.keepa_client import (
    get_buy_box_stats, amazon_in_stock, count_fba_sellers, get_bsr,
    KEEPA_DOMAINS,
)
from utils.fees_calculator import calculate_total_fees, get_size_tier
from clients.supabase_client import get_client, get_category_page, set_category_page

# IDs catégories Keepa par domaine EU
EU_CATEGORY_IDS = {
    "DE": {
        "Kitchen":           3167641,
        "Auto & Moto":       78191031,    # Auto & Motorrad
        "Office Products":   192416031,
        "Hygiène & Santé":   64187031,    # Drogerie & Körperpflege
        "Luminaires":        213083031,   # Beleuchtung
    },
}

MIN_PROFIT_NET = 5.0   # €
BSR_MAX_EU     = 80_000


class CrossBorderAgent:
    def __init__(self):
        self.opportunities_saved = 0
        self.tokens_start = 0
        self.tokens_end = 0

    def run(self) -> int:
        api = keepa_lib.Keepa(KEEPA_API_KEY)
        # keepa initialise tokens_left=0, on query directement et on override
        try:
            r = _req.get("https://api.keepa.com/token", params={"key": KEEPA_API_KEY}, timeout=10)
            self.tokens_start = int(r.json().get("tokensLeft", 0))
        except Exception:
            self.tokens_start = 0
        api.tokens_left = self.tokens_start
        print(f"[Agent 2] Tokens disponibles : {self.tokens_start}")

        done = False

        for domain in ["DE", "IT", "ES"]:
            if done:
                break

            for cat_name, cat_id in EU_CATEGORY_IDS.get(domain, {}).items():
                if done:
                    break

                tokens_left = getattr(api, "tokens_left", 0)
                if tokens_left < 5:
                    print(f"[Agent 2] Tokens insuffisants pour product_finder {domain}, stop.")
                    done = True
                    break

                page_key = f"{domain}/{cat_name}"
                page_index = get_category_page(page_key)
                try:
                    params = keepa_lib.ProductParams(
                        rootCategory=str(cat_id),
                        current_SALES_gte=BSR_MIN,
                        current_SALES_lte=BSR_MAX_EU,
                        current_BUY_BOX_SHIPPING_gte=int(BUY_BOX_MIN * 100),
                        current_BUY_BOX_SHIPPING_lte=int(BUY_BOX_MAX * 100),
                        page=page_index,
                    )
                    asins = list(api.product_finder(params, domain=domain, wait=False))
                    print(f"[Agent 2] {domain}/{cat_name} page {page_index} : {len(asins)} ASINs")
                    time.sleep(0.2)

                    if not asins and page_index > 0:
                        print(f"[Agent 2] Page {page_index} vide → retour page 0")
                        page_index = 0
                        params = keepa_lib.ProductParams(
                            rootCategory=str(cat_id),
                            current_SALES_gte=BSR_MIN,
                            current_SALES_lte=BSR_MAX_EU,
                            current_BUY_BOX_SHIPPING_gte=int(BUY_BOX_MIN * 100),
                            current_BUY_BOX_SHIPPING_lte=int(BUY_BOX_MAX * 100),
                            page=0,
                        )
                        asins = list(api.product_finder(params, domain=domain, wait=False))
                        print(f"[Agent 2] {domain}/{cat_name} page 0 : {len(asins)} ASINs")
                        time.sleep(0.2)

                    set_category_page(page_key, page_index + 1)
                except Exception as e:
                    print(f"[Agent 2] product_finder {domain}/{cat_name} : {e}")
                    break

                for asin in asins:
                    tokens_left = getattr(api, "tokens_left", 0)
                    if tokens_left < 3:
                        print("[Agent 2] Tokens épuisés — stop propre.")
                        done = True
                        break

                    # Check eligibility FR (0 token) — on source sur FR via EFN
                    statut = check_eligibility(asin)
                    if statut in ("RESTRICTED", "HAZMAT"):
                        continue

                    # Fetch prix EU (1 token)
                    try:
                        products_eu = api.query(
                            [asin], domain=domain, history=False, stats=90, wait=False
                        )
                    except Exception as e:
                        print(f"  [Keepa] Erreur fetch EU {asin}: {e}")
                        done = True
                        break

                    if not products_eu:
                        continue

                    bb_eu = get_buy_box_stats(products_eu[0], domain)
                    buy_box_eu = bb_eu["current"]
                    if not buy_box_eu or buy_box_eu <= 0:
                        continue

                    bsr_eu = get_bsr(products_eu[0])
                    if not bsr_eu or bsr_eu > BSR_MAX_EU:
                        continue

                    if amazon_in_stock(products_eu[0]):
                        continue

                    weight_g = products_eu[0].get("packageWeight") or products_eu[0].get("itemWeight") or 500
                    length = products_eu[0].get("packageLength") or 0
                    width  = products_eu[0].get("packageWidth") or 0
                    height = products_eu[0].get("packageHeight") or 0
                    size_tier = get_size_tier(weight_g, length, width, height)
                    titre = (products_eu[0].get("title") or "")[:100]

                    # Fetch prix FR (1 token)
                    tokens_left = getattr(api, "tokens_left", 0)
                    if tokens_left < 1:
                        print("[Agent 2] Tokens épuisés — stop propre.")
                        done = True
                        break

                    try:
                        products_fr = api.query(
                            [asin], domain="FR", history=False, stats=90, wait=False
                        )
                    except Exception as e:
                        print(f"  [Keepa] Erreur fetch FR {asin}: {e}")
                        done = True
                        break

                    if not products_fr:
                        continue

                    bb_fr = get_buy_box_stats(products_fr[0], "FR")
                    buy_box_fr_avg90 = bb_fr["avg90"]
                    buy_box_fr = bb_fr["current"]

                    if not buy_box_fr_avg90 or buy_box_fr_avg90 <= 0:
                        continue

                    if amazon_in_stock(products_fr[0]):
                        continue

                    ecart_pct = ((buy_box_eu - buy_box_fr_avg90) / buy_box_fr_avg90) * 100
                    if ecart_pct < ARBITRAGE_SPREAD_MIN:
                        continue

                    buy_price = round(buy_box_fr_avg90 * 0.7, 2)
                    fees = calculate_total_fees(buy_box_eu, "Kitchen", size_tier, weight_g, domain,
                                                length, width, height)
                    profit_net = round(buy_box_eu - fees["total_frais"] - buy_price, 2)
                    roi = round((profit_net / buy_price) * 100, 1) if buy_price > 0 else 0

                    if profit_net < MIN_PROFIT_NET:
                        continue

                    alerte = f"{domain} +{ecart_pct:.0f}%"
                    ecart_eur = round(buy_box_eu - buy_box_fr_avg90, 2)

                    domain_field = {"DE": "buy_box_de", "IT": "buy_box_it", "ES": "buy_box_es"}.get(domain)
                    row = {
                        "asin":                    asin,
                        "titre":                   titre,
                        "categorie":               "Cross-Border",
                        "statut":                  "CROSS_BORDER",
                        "source":                  "cross_border",
                        "buy_box_fr":              buy_box_fr,
                        "marketplace_recommandee": domain,
                        "alerte_arbitrage":        alerte,
                        "ecart_arbitrage":         ecart_eur,
                        "roi_meilleur":            roi,
                        "profit_net_fr":           profit_net,
                        "size_tier":               size_tier,
                        "weight_g":                weight_g,
                        "date_scan":               datetime.now(timezone.utc).isoformat(),
                    }
                    if domain_field:
                        row[domain_field] = buy_box_eu

                    try:
                        get_client().table("deals").insert(row).execute()
                        self.opportunities_saved += 1
                        print(f"  {asin} ({domain}) → {alerte} | profit {profit_net}€ | ROI {roi}%")
                    except Exception as e:
                        print(f"  [Supabase] Erreur save {asin}: {e}")

        self.tokens_end = getattr(api, "tokens_left", 0)
        tokens_used = self.tokens_start - self.tokens_end
        print(f"\n[Agent 2] Terminé — {self.opportunities_saved} opportunités | {tokens_used} tokens utilisés | {self.tokens_end} restants")
        return self.opportunities_saved
