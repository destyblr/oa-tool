import keepa
import time
from typing import List, Optional
from models.deal import Deal
from utils.fees_calculator import get_size_tier, calculate_total_fees
from config import (
    KEEPA_API_KEY,
    BSR_MIN, BSR_MAX,
    BUY_BOX_MIN, BUY_BOX_MAX, BUY_BOX_90J_MIN,
    FBA_SELLERS_MIN, FBA_SELLERS_MAX,
    EXCLURE_AMAZON_VENDEUR,
    MAX_ASINS_PER_RUN, CATEGORIES_TO_SCAN, ARBITRAGE_SPREAD_MIN,
    EFN_DESTINATIONS
)

# Mapping catégories → IDs Keepa réels (domain FR=4), récupérés via category_lookup
KEEPA_CATEGORY_IDS = {
    "Toys & Games":    322086011,   # Jeux et Jouets
    "Sports & Outdoors": 325614031, # Sports et Loisirs
    "Kitchen":         57004031,    # Cuisine et Maison
    "Home & Garden":   3557027031,  # Jardin
    "Electronics":     13921051,    # High-Tech
    "Pet Supplies":    1571268031,  # Animalerie
    "Office Products": 192419031,   # Fournitures de bureau
}

# Mapping domain Keepa → marketplace
KEEPA_DOMAINS = {
    "FR": 4,  # amazon.fr
    "DE": 3,  # amazon.de
    "IT": 8,  # amazon.it
    "ES": 9,  # amazon.es
}


def get_api():
    return keepa.Keepa(KEEPA_API_KEY)


def parse_price(csv_value) -> Optional[float]:
    """Convertit un prix Keepa (centimes) en euros."""
    if csv_value and csv_value > 0:
        return round(csv_value / 100, 2)
    return None


def get_buy_box_stats(product: dict, domain_key: str = "FR") -> dict:
    """Extrait Buy Box actuel et stats 90j depuis les données Keepa."""
    stats = product.get("stats", {})

    # Index 18 = Buy Box dans les stats Keepa
    buy_box_current = parse_price(stats.get("current", [None] * 20)[18])
    buy_box_avg90 = parse_price(stats.get("avg90", [None] * 20)[18])
    buy_box_min90 = parse_price(stats.get("min90", [None] * 20)[18])

    return {
        "current": buy_box_current,
        "avg90": buy_box_avg90,
        "min90": buy_box_min90,
    }


def amazon_in_stock(product: dict) -> bool:
    """Vérifie si Amazon est vendeur actif sur le listing."""
    stats = product.get("stats", {})
    amazon_price = stats.get("current", [None] * 5)[0]
    return amazon_price is not None and amazon_price > 0


def count_fba_sellers(product: dict) -> int:
    """Compte le nombre de vendeurs FBA depuis les offres."""
    offers = product.get("offers", []) or []
    fba_count = sum(
        1 for o in offers
        if o.get("isFBA") and o.get("condition") == 1
    )
    return fba_count


def get_bsr(product: dict) -> Optional[int]:
    """Récupère le BSR actuel."""
    stats = product.get("stats", {})
    current = stats.get("current", [])
    if len(current) > 3 and current[3] and current[3] > 0:
        return current[3]
    return None


def generate_shopping_link(titre: str, asin: str) -> str:
    """Génère un lien Google Shopping pour vérifier le prix fournisseur."""
    import urllib.parse
    query = urllib.parse.quote(f"{titre}")
    return f"https://www.google.com/search?q={query}&tbm=shop"


def calculate_score(deal: Deal) -> int:
    """Score de 0 à 100 basé sur BSR, ROI et nombre de vendeurs."""
    score = 0

    if deal.bsr_fr:
        if deal.bsr_fr < 5000:
            score += 40
        elif deal.bsr_fr < 20000:
            score += 30
        elif deal.bsr_fr < 50000:
            score += 20

    if deal.roi_meilleur:
        if deal.roi_meilleur >= 50:
            score += 40
        elif deal.roi_meilleur >= 35:
            score += 30
        elif deal.roi_meilleur >= 25:
            score += 20

    if deal.nb_vendeurs_fba:
        if deal.nb_vendeurs_fba <= 3:
            score += 20
        elif deal.nb_vendeurs_fba <= 8:
            score += 10

    return min(score, 100)


def detect_arbitrage(deal: Deal) -> tuple:
    """Détecte les opportunités d'arbitrage inter-marketplace."""
    alerts = []
    max_spread = 0.0

    ref_price = deal.buy_box_90j_moy_fr or deal.buy_box_fr
    if not ref_price:
        return "", 0.0

    for mp, price in [("DE", deal.buy_box_de), ("IT", deal.buy_box_it), ("ES", deal.buy_box_es)]:
        if price and price > 0:
            spread_pct = ((price - ref_price) / ref_price) * 100
            spread_eur = round(price - ref_price, 2)
            if spread_pct >= ARBITRAGE_SPREAD_MIN:
                alerts.append(f"{mp} +{spread_pct:.0f}%")
                if spread_eur > max_spread:
                    max_spread = spread_eur

    return " / ".join(alerts), round(max_spread, 2)


def recommend_marketplace(deal: Deal, fees_by_mp: dict) -> tuple:
    """Recommande la marketplace avec le meilleur ROI."""
    best_mp = "FR"
    best_roi = deal.roi_fr or -999

    for mp in EFN_DESTINATIONS:
        bb = getattr(deal, f"buy_box_{mp.lower()}")
        if not bb:
            continue
        fees = fees_by_mp.get(mp, {})
        total = fees.get("total_frais", 0)
        roi = round(((bb - total) / bb) * 100, 1) if bb > 0 else -999
        if roi > best_roi:
            best_roi = roi
            best_mp = mp

    gain_vs_fr = round(best_roi - (deal.roi_fr or 0), 1)
    return best_mp, best_roi, gain_vs_fr


def fetch_candidates(category_name: str) -> List[Deal]:
    """Interroge Keepa et retourne une liste de deals candidats."""
    api = get_api()
    category_id = KEEPA_CATEGORY_IDS.get(category_name)
    if not category_id:
        print(f"Catégorie inconnue : {category_name}")
        return []

    print(f"Recherche Keepa pour : {category_name}...")

    try:
        import keepa as keepa_lib
        params = keepa_lib.ProductParams(
            categories_include=[category_id],
            current_SALES_gte=BSR_MIN,
            current_SALES_lte=BSR_MAX,
            current_BUY_BOX_SHIPPING_gte=int(BUY_BOX_MIN * 100),
            current_BUY_BOX_SHIPPING_lte=int(BUY_BOX_MAX * 100),
            availabilityAmazon=0,  # 0 = Amazon pas vendeur actuellement
        )
        asins = api.product_finder(params, domain="FR")
    except Exception as e:
        print(f"Erreur Keepa product_finder : {e}")
        return []

    if not asins:
        print(f"Aucun produit trouvé pour {category_name}")
        return []

    asins = list(asins[:MAX_ASINS_PER_RUN])
    print(f"{len(asins)} ASINs trouvés, récupération des détails...")

    try:
        detailed = api.query(
            asins,
            domain="FR",
            history=False,
            offers=20,
            stats=90,
        )
    except Exception as e:
        print(f"Erreur récupération détails : {e}")
        return []

    deals = []

    for product in detailed:
        try:
            asin = product.get("asin", "")
            titre = product.get("title", "")
            categorie = category_name

            bsr = get_bsr(product)
            if not bsr or bsr < BSR_MIN or bsr > BSR_MAX:
                continue

            amazon_stock = amazon_in_stock(product)
            if EXCLURE_AMAZON_VENDEUR and amazon_stock:
                continue  # Deal killer

            nb_fba = count_fba_sellers(product)
            if nb_fba < FBA_SELLERS_MIN or nb_fba > FBA_SELLERS_MAX:
                continue

            # Prix FR
            bb_stats_fr = get_buy_box_stats(product)
            buy_box_fr = bb_stats_fr["current"]
            buy_box_moy = bb_stats_fr["avg90"]
            buy_box_min = bb_stats_fr["min90"]

            if not buy_box_moy:
                continue
            if buy_box_moy < BUY_BOX_90J_MIN:
                continue
            if buy_box_fr and (buy_box_fr < BUY_BOX_MIN or buy_box_fr > BUY_BOX_MAX):
                continue

            # Poids et dimensions pour frais
            weight_g = product.get("packageWeight") or product.get("itemWeight") or 500
            length = product.get("packageLength") or 0
            width = product.get("packageWidth") or 0
            height = product.get("packageHeight") or 0
            size_tier = get_size_tier(weight_g, length, width, height)

            # Frais FR
            fees_fr = calculate_total_fees(buy_box_moy, categorie, size_tier, weight_g, "FR")

            deal = Deal(
                asin=asin,
                titre=titre,
                categorie=categorie,
                bsr_fr=bsr,
                nb_vendeurs_fba=nb_fba,
                amazon_en_stock=amazon_stock,
                buy_box_fr=buy_box_fr,
                buy_box_90j_moy_fr=buy_box_moy,
                buy_box_90j_min_fr=buy_box_min,
                referral_fee=fees_fr["referral_fee"],
                frais_fba=fees_fr["frais_fba"],
                envoi_fba=fees_fr["envoi_fba"],
                urssaf=fees_fr["urssaf"],
                total_frais=fees_fr["total_frais"],
                lien_google_shopping=generate_shopping_link(titre, asin),
            )

            # ROI FR estimé (sans prix achat = on prend 70% du buy box comme base)
            prix_achat_estimé = round(buy_box_moy * 0.7, 2)
            profit_fr = round(buy_box_moy - fees_fr["total_frais"] - prix_achat_estimé, 2)
            deal.roi_fr = round((profit_fr / prix_achat_estimé) * 100, 1) if prix_achat_estimé > 0 else 0

            # Frais et ROI par marketplace
            fees_by_mp = {}
            for mp in EFN_DESTINATIONS:
                fees_mp = calculate_total_fees(buy_box_moy, categorie, size_tier, weight_g, mp)
                fees_by_mp[mp] = fees_mp
                setattr(deal, f"buy_box_{mp.lower()}", None)  # Sera enrichi si dispo

            deal.frais_efn = fees_by_mp.get("DE", {}).get("total_frais")

            # Recommandation marketplace
            best_mp, best_roi, gain = recommend_marketplace(deal, fees_by_mp)
            deal.marketplace_recommandee = best_mp
            deal.roi_meilleur = best_roi
            deal.gain_vs_fr = gain

            # Arbitrage
            alerte, ecart = detect_arbitrage(deal)
            deal.alerte_arbitrage = alerte
            deal.ecart_arbitrage = ecart

            # Score
            deal.score_deal = calculate_score(deal)

            deals.append(deal)
            time.sleep(0.1)

        except Exception as e:
            print(f"Erreur traitement ASIN {product.get('asin', '?')} : {e}")
            continue

    print(f"{len(deals)} deals valides trouvés pour {category_name}")
    return deals
