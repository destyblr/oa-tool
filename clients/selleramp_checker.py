import asyncio
import random
import os
import json
from pathlib import Path
from playwright.async_api import async_playwright
from models.deal import Deal
from config import (
    SC_URL, SC_SESSION_PATH,
    SELLERAMP_DELAY_MIN, SELLERAMP_DELAY_MAX
)

APPROVED_BRANDS_PATH = Path(__file__).parent.parent / "approved_brands.json"


def _save_approved_brand(brand: str):
    """Sauvegarde une marque confirmée ELIGIBLE pour les runs futurs."""
    if not brand or brand.lower() in ("", "générique", "generic"):
        return
    brand_low = brand.lower().strip()
    try:
        if APPROVED_BRANDS_PATH.exists():
            with open(APPROVED_BRANDS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"approved_brands": [], "notes": "Marques confirmées ELIGIBLE via Seller Central"}
        if brand_low not in [b.lower() for b in data["approved_brands"]]:
            data["approved_brands"].append(brand)
            with open(APPROVED_BRANDS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  [+] Marque approuvée sauvegardée : {brand}")
    except Exception as e:
        print(f"  [WARN] Impossible de sauvegarder la marque {brand}: {e}")


async def save_sc_session(context):
    """Sauvegarde la session Seller Central."""
    os.makedirs("credentials", exist_ok=True)
    await context.storage_state(path=SC_SESSION_PATH)
    print("Session Seller Central sauvegardee.")


async def check_eligibility(asin: str, page) -> str:
    """
    Verifie l'eligibilite d'un ASIN via SC product-search.
    Retourne : ELIGIBLE / RESTRICTED / HAZMAT / UNKNOWN

    Indicateurs SC (kat-badge label) :
    - "Non disponible"      -> RESTRICTED
    - "Approbation requise" -> RESTRICTED
    - "Eligible" / absent   -> ELIGIBLE
    """
    try:
        await page.goto(f"{SC_URL}/product-search", timeout=20000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)

        # Verifier qu'on est bien sur SC (pas redirige vers login)
        current_url = page.url
        if "signin" in current_url or "ap/signin" in current_url:
            print(f"  [WARN] Session expiree - redirige vers login ({current_url})")
            return "UNKNOWN"

        # Clic sur l'onglet Identifiants de produits
        tab = page.locator("text=Identifiants de produits").first
        await tab.wait_for(timeout=10000)
        await tab.click()
        await asyncio.sleep(2)

        textarea = await page.query_selector("textarea")
        if not textarea:
            print(f"  [WARN] Textarea introuvable pour {asin} (URL: {page.url})")
            return "UNKNOWN"
        await textarea.fill(asin)

        await page.locator('button:has-text("Soumettre")').first.click()

        # Attendre le chargement de la page de resultats
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(8)

        content = await page.content()
        content_low = content.lower()

        # Erreurs génériques Amazon (popup modale)
        if "5886" in content or "générique soumis à des restrictions" in content_low or "generic" in content_low and "restriction" in content_low:
            return "RESTRICTED"

        # Lecture des badges kat-badge (indicateurs d'eligibilite SC)
        import re
        badges = re.findall(r'kat-badge\s+label="([^"]+)"', content)
        for label in badges:
            label_low = label.lower()
            if "non disponible" in label_low:
                return "RESTRICTED"
            if "approbation" in label_low or "approval" in label_low:
                return "RESTRICTED"
            if "dangereux" in label_low or "hazmat" in label_low:
                return "HAZMAT"
            if label_low in ("eligible", "eligible", "disponible"):
                return "ELIGIBLE"

        # Fallback si aucun badge mais produit trouvé
        if "correspondance trouvée" in content_low and not badges:
            return "ELIGIBLE"

        print(f"  [DEBUG] Badges trouves: {badges} | URL: {page.url}")
        return "UNKNOWN"

    except Exception as e:
        print(f"  [ERR] check ASIN {asin} : {type(e).__name__}: {e}")
        return "UNKNOWN"


async def check_deals(deals: list[Deal]) -> list[Deal]:
    """
    Verifie l'eligibilite de tous les deals via Seller Central directement.
    Premiere fois : ouvre le navigateur pour connexion SC manuelle.
    Fois suivantes : utilise la session sauvegardee.
    """
    session_exists = os.path.exists(SC_SESSION_PATH)

    async with async_playwright() as p:
        # headless=False : SC bloque les browsers headless (detection bot)
        browser = await p.chromium.launch(headless=False)

        if session_exists:
            context = await browser.new_context(storage_state=SC_SESSION_PATH)
            print("Session Seller Central chargee.")
        else:
            print("\n=== PREMIERE CONNEXION SELLER CENTRAL ===")
            print("Le navigateur va s'ouvrir sur Seller Central.")
            print("1. Connecte-toi a Seller Central (email + SMS)")
            print("2. Attends d'etre sur le tableau de bord SC")
            print("3. Appuie sur Entree ici.")
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(f"{SC_URL}/home")
            input("\nAppuie sur Entree une fois connecte a Seller Central...")
            await save_sc_session(context)

        page = await context.new_page()

        for deal in deals:
            print(f"Verification eligibilite : {deal.asin} - {deal.titre[:40]}...")
            statut = await check_eligibility(deal.asin, page)
            deal.statut = statut
            print(f"  => {statut}")
            if statut == "ELIGIBLE" and getattr(deal, "brand", None):
                _save_approved_brand(deal.brand)
            await asyncio.sleep(random.uniform(SELLERAMP_DELAY_MIN, SELLERAMP_DELAY_MAX))

        await browser.close()

    return deals
