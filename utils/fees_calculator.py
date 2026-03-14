from config import (
    FBA_FEES, EFN_FEES, SHIPPING_RATES,
    URSSAF_RATE, UNITS_PER_CARTON, REFERRAL_RATES
)


def get_size_tier(weight_g: float, length_cm=0, width_cm=0, height_cm=0) -> str:
    """Détermine le size tier Amazon selon poids et dimensions."""
    dims = sorted([length_cm, width_cm, height_cm], reverse=True)
    if dims[0] > 45 or sum(dims) > 72:
        return "extra_large"
    if weight_g <= 400:
        return "small_standard"
    elif weight_g <= 900:
        return "large_standard_400"
    elif weight_g <= 1400:
        return "large_standard_900"
    elif weight_g <= 5000:
        return "large_standard_1400"
    else:
        return "extra_large"


def get_fba_fees(size_tier: str, marketplace: str = "FR") -> float:
    """Retourne les frais FBA/EFN selon le size tier et la marketplace."""
    return EFN_FEES.get(size_tier, EFN_FEES["large_standard_400"]).get(marketplace, 3.40)


def get_shipping_cost(weight_g: float) -> float:
    """Estime le coût d'envoi vers FBA par unité selon le poids."""
    weight_kg = weight_g / 1000
    carton_weight = weight_kg * UNITS_PER_CARTON

    if carton_weight <= 1:
        rate = SHIPPING_RATES["0-1kg"]
    elif carton_weight <= 2:
        rate = SHIPPING_RATES["1-2kg"]
    elif carton_weight <= 5:
        rate = SHIPPING_RATES["2-5kg"]
    else:
        rate = SHIPPING_RATES["5-10kg"]

    return round(rate / UNITS_PER_CARTON, 2)


def get_referral_fee(sell_price: float, category: str) -> float:
    """Calcule la commission Amazon selon la catégorie."""
    rate = REFERRAL_RATES.get(category, REFERRAL_RATES["default"])
    return round(sell_price * rate, 2)


def get_urssaf(sell_price: float) -> float:
    """Calcule la cotisation URSSAF (12.3% du CA pour auto-entrepreneur)."""
    return round(sell_price * URSSAF_RATE, 2)


def get_storage_fee(length_cm: float, width_cm: float, height_cm: float) -> float:
    """Calcule les frais de stockage FBA mensuels par unité.
    Grille Amazon 2024 : 26€/m³ (janv-sept), 36€/m³ (oct-déc).
    On utilise la moyenne annuelle : ~28.50€/m³."""
    if not length_cm or not width_cm or not height_cm:
        return 0.0
    volume_m3 = (length_cm / 100) * (width_cm / 100) * (height_cm / 100)
    avg_rate = 28.50  # €/m³/mois (moyenne annuelle)
    return round(volume_m3 * avg_rate, 2)


def calculate_total_fees(sell_price: float, category: str, size_tier: str,
                          weight_g: float, marketplace: str = "FR",
                          length_cm: float = 0, width_cm: float = 0,
                          height_cm: float = 0) -> dict:
    """Calcule tous les frais et retourne la décomposition complète."""
    referral = get_referral_fee(sell_price, category)
    fba = get_fba_fees(size_tier, marketplace)
    shipping = get_shipping_cost(weight_g)
    urssaf = get_urssaf(sell_price)
    stockage = get_storage_fee(length_cm, width_cm, height_cm)
    total = round(referral + fba + shipping + urssaf + stockage, 2)

    return {
        "referral_fee": referral,
        "frais_fba": fba,
        "envoi_fba": shipping,
        "urssaf": urssaf,
        "stockage_fba": stockage,
        "total_frais": total,
    }


def calculate_roi(buy_price: float, sell_price: float, total_fees: float) -> dict:
    """Calcule le profit net et le ROI."""
    if not buy_price or buy_price <= 0:
        return {"profit_net": None, "roi": None}

    profit = round(sell_price - total_fees - buy_price, 2)
    roi = round((profit / buy_price) * 100, 1) if buy_price > 0 else 0

    return {"profit_net": profit, "roi": roi}
