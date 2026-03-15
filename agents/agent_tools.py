"""
Implémentations des outils partagés entre les agents Claude AI.
Chaque fonction `tool_*` correspond à un outil exposé à un agent.
"""
import json
import time
from pathlib import Path
from datetime import date, timedelta
from typing import Optional

from clients.keepa_client import (
    get_api, get_buy_box_stats, KEEPA_CATEGORY_IDS, KEEPA_DOMAINS,
    amazon_in_stock, count_fba_sellers, get_bsr, generate_shopping_link,
)
from clients.supabase_client import get_client, get_category_page, set_category_page
from utils.fees_calculator import calculate_total_fees, calculate_roi, get_size_tier
from config import EFN_FEES

RESTRICTIONS_PATH = Path(__file__).parent.parent / "restrictions.json"
APPROVED_BRANDS_PATH = Path(__file__).parent.parent / "approved_brands.json"


# ── Agent 1 : outils d'acquisition ───────────────────────────────────────────

def tool_read_restrictions() -> dict:
    """Lit restrictions.json + approved_brands.json du compte."""
    try:
        with open(RESTRICTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {
            "restricted_categories": [],
            "restricted_asins": [],
            "restricted_brands": [],
            "low_value_categories": [],
        }
    try:
        if APPROVED_BRANDS_PATH.exists():
            with open(APPROVED_BRANDS_PATH, "r", encoding="utf-8") as f:
                ab = json.load(f)
                data["approved_brands"] = ab.get("approved_brands", [])
        else:
            data["approved_brands"] = []
    except Exception:
        data["approved_brands"] = []
    return data


def tool_query_past_scanned_asins(days_back: int = 7) -> list:
    """Retourne les ASINs déjà scannés dans les N derniers jours."""
    client = get_client()
    since = (date.today() - timedelta(days=days_back)).isoformat()
    try:
        response = (
            client.table("deals")
            .select("asin")
            .gte("date_scan", since)
            .execute()
        )
        return list({row["asin"] for row in (response.data or [])})
    except Exception as e:
        print(f"[agent_tools] Erreur Supabase past_asins: {e}")
        return []


def tool_get_available_categories() -> dict:
    """Retourne les catégories disponibles avec leurs IDs Keepa."""
    return {
        name: {"id": cat_id}
        for name, cat_id in KEEPA_CATEGORY_IDS.items()
    }


def tool_search_keepa_category(
    category_name: str,
    bsr_min: int,
    bsr_max: int,
    buy_box_min_cents: int,
    buy_box_max_cents: int,
    max_asins: int,
) -> dict:
    """Cherche des ASINs dans une catégorie Keepa selon les filtres donnés."""
    import keepa as keepa_lib

    category_id = KEEPA_CATEGORY_IDS.get(category_name)
    if not category_id:
        return {"error": f"Catégorie inconnue: {category_name}", "asins": [], "count": 0}

    api = get_api()
    page_key = f"FR/{category_name}"
    page_index = get_category_page(page_key)
    try:
        params = keepa_lib.ProductParams(
            rootCategory=str(category_id),
            current_SALES_gte=bsr_min,
            current_SALES_lte=bsr_max,
            current_BUY_BOX_SHIPPING_gte=buy_box_min_cents,
            current_BUY_BOX_SHIPPING_lte=buy_box_max_cents,
            page=page_index,
        )
        asins = api.product_finder(params, domain="FR")

        if not asins and page_index > 0:
            print(f"[agent_tools] Page {page_index} vide → retour page 0")
            page_index = 0
            params = keepa_lib.ProductParams(
                rootCategory=str(category_id),
                current_SALES_gte=bsr_min,
                current_SALES_lte=bsr_max,
                current_BUY_BOX_SHIPPING_gte=buy_box_min_cents,
                current_BUY_BOX_SHIPPING_lte=buy_box_max_cents,
                page=0,
            )
            asins = api.product_finder(params, domain="FR")

        if not asins:
            print(f"[agent_tools] Fallback sans rootCategory pour {category_name}...")
            params_fb = keepa_lib.ProductParams(
                current_SALES_gte=bsr_min,
                current_SALES_lte=bsr_max,
                current_BUY_BOX_SHIPPING_gte=buy_box_min_cents,
                current_BUY_BOX_SHIPPING_lte=buy_box_max_cents,
            )
            asins = api.product_finder(params_fb, domain="FR")

        set_category_page(page_key, page_index + 1)
        asins = list(asins[:max_asins])
        tokens_left = getattr(api, 'tokens_left', None)
        return {"asins": asins, "count": len(asins), "tokens_used": len(asins), "tokens_left": tokens_left}

    except Exception as e:
        return {"error": str(e), "asins": [], "count": 0}


def tool_get_asin_details_fr(asins: list, category_name: str = "Unknown") -> list:
    """Récupère les détails FR d'une liste d'ASINs depuis Keepa (1 token par ASIN)."""
    api = get_api()
    try:
        detailed = api.query(
            asins,
            domain="FR",
            history=False,
            offers=20,
            stats=90,
        )
    except Exception as e:
        return [{"error": str(e)}]

    tokens_left = getattr(api, 'tokens_left', None)
    results = []
    for product in detailed:
        try:
            asin = product.get("asin", "")
            titre = product.get("title", "") or ""
            brand = product.get("brand") or ""

            bsr = get_bsr(product)
            bb_stats = get_buy_box_stats(product)
            nb_fba = count_fba_sellers(product)
            amazon_stock = amazon_in_stock(product)

            weight_g = product.get("packageWeight") or product.get("itemWeight") or 500
            length = product.get("packageLength") or 0
            width = product.get("packageWidth") or 0
            height = product.get("packageHeight") or 0
            size_tier = get_size_tier(weight_g, length, width, height)

            results.append({
                "asin": asin,
                "titre": titre,
                "brand": brand,
                "categorie": category_name,
                "bsr_fr": bsr,
                "buy_box_fr": bb_stats["current"],
                "buy_box_90j_moy_fr": bb_stats["avg90"],
                "buy_box_90j_min_fr": bb_stats["min90"],
                "nb_vendeurs_fba": nb_fba,
                "amazon_en_stock": amazon_stock,
                "weight_g": weight_g,
                "size_tier": size_tier,
                "lien_google_shopping": generate_shopping_link(titre, asin),
            })
        except Exception as e:
            results.append({"asin": product.get("asin", "?"), "error": str(e)})
        time.sleep(0.1)

    if tokens_left is not None:
        results.append({"_tokens_left": tokens_left})
    return results


# ── Agent 2 : outils cross-border ────────────────────────────────────────────

def tool_fetch_multimarket_prices(asins: list, domains: list) -> dict:
    """Récupère les prix buy box sur DE/IT/ES pour une liste d'ASINs."""
    api = get_api()
    result = {asin: {d: None for d in domains} for asin in asins}

    for domain_name in domains:
        if domain_name not in KEEPA_DOMAINS:
            continue
        try:
            detailed = api.query(
                asins,
                domain=domain_name,
                history=False,
                stats=90,
            )
            for product in detailed:
                asin = product.get("asin", "")
                if asin in result:
                    bb = get_buy_box_stats(product, domain_name)
                    result[asin][domain_name] = bb["current"]
        except Exception as e:
            print(f"[agent_tools] Erreur Keepa domain {domain_name}: {e}")

    tokens_left = getattr(api, 'tokens_left', None)
    if tokens_left is not None:
        result["_tokens_left"] = tokens_left
    return result


def tool_calculate_efn_profitability(
    sell_price: float,
    buy_price: float,
    category: str,
    size_tier: str,
    weight_g: float,
    marketplace: str,
) -> dict:
    """Calcule la rentabilité EFN pour un deal sur une marketplace donnée."""
    fees = calculate_total_fees(sell_price, category, size_tier, weight_g, marketplace)
    roi_result = calculate_roi(buy_price, sell_price, fees["total_frais"])
    return {
        "marketplace": marketplace,
        "sell_price": sell_price,
        "buy_price": buy_price,
        "total_frais": fees["total_frais"],
        "detail_frais": fees,
        "profit_net": roi_result["profit_net"],
        "roi": roi_result["roi"],
    }


def tool_get_efn_fee_table() -> dict:
    """Retourne la table des frais EFN depuis config."""
    return EFN_FEES


# ── Agent 2 EU : outils de sourcing cross-border ─────────────────────────────

# Category IDs Keepa par domaine EU (stables, issus de category_lookup)
_EU_CATEGORY_IDS = {
    "DE": {
        "Kitchen":           3167641,
        "Auto & Moto":       78191031,    # Auto & Motorrad
        "Toys & Games":      12950651,
        "Hygiène & Santé":   64187031,    # Drogerie & Körperpflege
        "Luminaires":        213083031,   # Beleuchtung
    },
    "IT": {
        "Kitchen":           524018031,
        "Auto & Moto":       2454170031,  # Auto e Moto
        "Hygiène & Santé":   1571286031,  # Salute e cura della persona
        "Luminaires":        1571292031,  # Illuminazione
    },
    "ES": {
        "Kitchen":           599392031,
        "Auto & Moto":       1951051031,  # Coche y moto
    },
}


def tool_search_keepa_eu(
    domain: str,
    bsr_min: int,
    bsr_max: int,
    buy_box_min_cents: int,
    buy_box_max_cents: int,
    max_asins: int,
    category_name: str = None,
) -> dict:
    """
    Cherche des ASINs directement sur un domaine EU (DE/IT/ES) via Keepa product_finder.
    Coût : ~2-5 tokens. Fallback sans catégorie si ID inconnu.
    """
    if domain not in KEEPA_DOMAINS:
        return {"error": f"Domaine inconnu: {domain}", "asins": [], "count": 0}

    api = get_api()
    category_id = _EU_CATEGORY_IDS.get(domain, {}).get(category_name) if category_name else None
    page_key = f"{domain}/{category_name}" if category_name else f"{domain}/_all"
    page_index = get_category_page(page_key)

    try:
        params = {
            "current_BUY_BOX_SHIPPING_gte": buy_box_min_cents,
            "current_BUY_BOX_SHIPPING_lte": buy_box_max_cents,
            "current_SALES_gte": bsr_min,
            "current_SALES_lte": bsr_max,
            "page": page_index,
        }
        if category_id:
            params["rootCategory"] = str(category_id)

        asins = list(api.product_finder(params, domain=domain))[:max_asins]

        if not asins and page_index > 0:
            print(f"[agent_tools] EU page {page_index} vide → retour page 0")
            page_index = 0
            params["page"] = 0
            asins = list(api.product_finder(params, domain=domain))[:max_asins]

        set_category_page(page_key, page_index + 1)
        tokens_left = getattr(api, "tokens_left", None)
        return {
            "domain": domain,
            "asins": asins,
            "count": len(asins),
            "tokens_left": tokens_left,
            "category_used": category_name if category_id else None,
        }
    except Exception as e:
        return {"error": str(e), "asins": [], "count": 0, "domain": domain}


def tool_get_asin_details_eu(asins: list, domain: str) -> list:
    """
    Récupère prix buy box, BSR, vendeurs FBA, poids pour des ASINs sur un domaine EU.
    Coût : 1 token/ASIN.
    """
    if domain not in KEEPA_DOMAINS:
        return [{"error": f"Domaine inconnu: {domain}"}]

    api = get_api()
    try:
        detailed = api.query(asins, domain=domain, history=False, offers=10, stats=90)
    except Exception as e:
        return [{"error": str(e)}]

    results = []
    for product in detailed:
        try:
            asin = product.get("asin", "")
            titre = (product.get("title") or "")[:80]
            weight_g = product.get("packageWeight") or product.get("itemWeight") or 500
            length = product.get("packageLength") or 0
            width = product.get("packageWidth") or 0
            height = product.get("packageHeight") or 0
            size_tier = get_size_tier(weight_g, length, width, height)
            bb = get_buy_box_stats(product, domain)
            results.append({
                "asin": asin,
                "domain": domain,
                "titre": titre,
                "bsr": get_bsr(product),
                "buy_box_current": bb["current"],
                "buy_box_avg90": bb["avg90"],
                "nb_vendeurs_fba": count_fba_sellers(product),
                "amazon_en_stock": amazon_in_stock(product),
                "weight_g": weight_g,
                "size_tier": size_tier,
            })
        except Exception as e:
            results.append({"asin": product.get("asin", "?"), "error": str(e)})

    tokens_left = getattr(api, "tokens_left", None)
    if tokens_left is not None:
        results.append({"_tokens_left": tokens_left})
    return results


def tool_get_fr_prices_for_asins(asins: list) -> dict:
    """
    Récupère les prix buy box FR pour une liste d'ASINs trouvés sur EU.
    Coût : 1 token/ASIN.
    """
    api = get_api()
    result = {}
    try:
        detailed = api.query(asins, domain="FR", history=False, stats=90)
        for product in detailed:
            asin = product.get("asin", "")
            bb = get_buy_box_stats(product, "FR")
            result[asin] = {
                "buy_box_fr": bb["current"],
                "buy_box_fr_avg90": bb["avg90"],
                "bsr_fr": get_bsr(product),
                "amazon_en_stock_fr": amazon_in_stock(product),
            }
    except Exception as e:
        print(f"[agent_tools] Erreur get_fr_prices: {e}")

    tokens_left = getattr(api, "tokens_left", None)
    if tokens_left is not None:
        result["_tokens_left"] = tokens_left
    return result


def tool_save_cross_border_opportunity(
    asin: str,
    titre: str,
    domain_source: str,
    buy_box_eu: float,
    buy_box_fr: float,
    size_tier: str,
    weight_g: float,
    categorie: str,
    profit_net: float,
    roi: float,
    bsr_eu: int = None,
    alerte_arbitrage: str = None,
    ecart_arbitrage: float = None,
) -> dict:
    """
    Sauvegarde une opportunité cross-border dans Supabase (source='cross_border').
    """
    from datetime import datetime, timezone
    client = get_client()

    ecart = ecart_arbitrage or round(buy_box_eu - buy_box_fr, 2)
    ecart_pct = round(((buy_box_eu - buy_box_fr) / buy_box_fr) * 100) if buy_box_fr else 0
    alerte = alerte_arbitrage or f"{domain_source} +{ecart_pct}%"

    row = {
        "asin": asin,
        "titre": titre,
        "categorie": categorie,
        "statut": "CROSS_BORDER",
        "source": "cross_border",
        "buy_box_fr": buy_box_fr,
        "size_tier": size_tier,
        "weight_g": weight_g,
        "marketplace_recommandee": domain_source,
        "alerte_arbitrage": alerte,
        "ecart_arbitrage": ecart,
        "roi_meilleur": roi,
        "profit_net_fr": profit_net,
        "date_scan": datetime.now(timezone.utc).isoformat(),
    }

    domain_field = {"DE": "buy_box_de", "IT": "buy_box_it", "ES": "buy_box_es"}.get(domain_source)
    if domain_field:
        row[domain_field] = buy_box_eu

    try:
        client.table("deals").insert(row).execute()
        return {"status": "ok", "asin": asin}
    except Exception as e:
        print(f"[agent_tools] Erreur save_cross_border {asin}: {e}")
        return {"status": "error", "error": str(e)}
