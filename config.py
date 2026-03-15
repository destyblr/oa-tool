import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SELLERAMP_EMAIL = os.getenv("SELLERAMP_EMAIL")
SELLERAMP_PASSWORD = os.getenv("SELLERAMP_PASSWORD")

# ── Keepa — Filtres produits (onglet Auto) ────────────────────────────────────

# Catégories scannées
CATEGORIES_TO_SCAN = [
    "Kitchen", "Home & Garden", "Auto & Moto", "Office Products",
    "Hygiène & Santé", "Luminaires",
]

# Nombre max d'ASINs récupérés par catégorie (1 token Keepa ≈ 1 ASIN)
MAX_ASINS_PER_RUN = 50

# --- BSR (classement des ventes) ---
BSR_MIN = 1_000        # Minimum : évite produits ultra-compétitifs (trop de concurrence)
BSR_MAX = 80_000       # Maximum : produits qui se vendent suffisamment

# --- Buy Box prix (€) ---
BUY_BOX_MIN = 15.0     # Min : évite les produits trop bas de gamme (marges trop faibles)
BUY_BOX_MAX = 200.0    # Max : budget achat raisonnable

# --- Buy Box moyenne 90 jours (€) ---
BUY_BOX_90J_MIN = 15.0 # Stabilité du prix : évite produits dont le prix s'effondre

# --- Vendeurs FBA ---
FBA_SELLERS_MIN = 1    # Min : au moins 1 FBA (produit actif sur Amazon)
FBA_SELLERS_MAX = 15   # Max : pas trop de concurrence

# --- Amazon comme vendeur ---
EXCLURE_AMAZON_VENDEUR = True  # True = exclure si Amazon est vendeur (deal killer)

# Rentabilité
MIN_ROI_PERCENT = 25
REFERRAL_RATES = {
    "Kitchen": 0.15,
    "Home & Garden": 0.15,
    "Auto & Moto": 0.15,
    "Office Products": 0.15,
    "Hygiène & Santé": 0.15,
    "Luminaires": 0.15,
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
ARBITRAGE_SPREAD_MIN = 10  # % écart minimum pour alerter

# Seller Central
SC_SESSION_PATH = "./credentials/sc_session.json"
SC_URL = "https://sellercentral.amazon.fr"
SELLERAMP_DELAY_MIN = 1.5
SELLERAMP_DELAY_MAX = 3.0

# Anthropic / Agents Claude AI
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AGENT_TOKEN_BUDGET = int(os.getenv("AGENT_TOKEN_BUDGET", "200"))
AGENT_MAX_ITERATIONS = 10

# Amazon SP API
SP_CLIENT_ID = os.getenv("SP_CLIENT_ID")
SP_CLIENT_SECRET = os.getenv("SP_CLIENT_SECRET")
SP_REFRESH_TOKEN = os.getenv("SP_REFRESH_TOKEN")
SP_SELLER_ID = os.getenv("SP_SELLER_ID")
SP_MARKETPLACE_ID = os.getenv("SP_MARKETPLACE_ID", "A13V1IB3VIYZZH")
