import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SELLERAMP_EMAIL = os.getenv("SELLERAMP_EMAIL")
SELLERAMP_PASSWORD = os.getenv("SELLERAMP_PASSWORD")

# Keepa — Filtres produits
BSR_MAX = 50000
FBA_SELLERS_MIN = 1
FBA_SELLERS_MAX = 15
PRICE_HISTORY_DAYS = 90
MIN_PRICE_DROP_PERCENT = 5
MAX_ASINS_PER_RUN = 50
CATEGORIES_TO_SCAN = ["Toys & Games", "Sports & Outdoors", "Kitchen"]

# Rentabilité
MIN_ROI_PERCENT = 25
REFERRAL_RATES = {
    "Toys & Games": 0.15,
    "Sports & Outdoors": 0.15,
    "Kitchen": 0.15,
    "Electronics": 0.08,
    "default": 0.15,
}
URSSAF_RATE = 0.123
UNITS_PER_CARTON = 10

# Frais FBA FR (grille Amazon 2024)
FBA_FEES = {
    "small_standard":      2.70,
    "large_standard_400":  3.40,
    "large_standard_900":  4.05,
    "large_standard_1400": 5.35,
    "extra_large":         7.50,
}

# Frais EFN par destination (depuis FR)
EFN_FEES = {
    "small_standard":      {"FR": 2.70, "DE": 3.75, "IT": 3.90, "ES": 3.90},
    "large_standard_400":  {"FR": 3.40, "DE": 4.75, "IT": 4.90, "ES": 4.90},
    "large_standard_900":  {"FR": 4.05, "DE": 5.65, "IT": 5.80, "ES": 5.80},
    "large_standard_1400": {"FR": 5.35, "DE": 7.45, "IT": 7.75, "ES": 7.75},
    "extra_large":         {"FR": 7.50, "DE": 10.70, "IT": 11.10, "ES": 11.10},
}

# Tarifs envoi vers FBA (Colissimo/UPS, par kg)
SHIPPING_RATES = {
    "0-1kg":  6.0,
    "1-2kg":  8.0,
    "2-5kg":  12.0,
    "5-10kg": 18.0,
}

# Marketplaces
MARKETPLACES = ["FR", "DE", "IT", "ES"]
EFN_DESTINATIONS = ["DE", "IT", "ES"]
ARBITRAGE_SPREAD_MIN = 15  # % écart minimum pour alerter

# SellerAmp
SELLERAMP_URL = "https://sas.selleramp.com"
SELLERAMP_SESSION_PATH = "./credentials/selleramp_session.json"
SELLERAMP_DELAY_MIN = 1.5
SELLERAMP_DELAY_MAX = 3.0
