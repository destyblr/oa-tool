import asyncio
import random
import time
import json
import os
from playwright.async_api import async_playwright
from models.deal import Deal
from config import (
    SELLERAMP_URL, SELLERAMP_SESSION_PATH,
    SELLERAMP_DELAY_MIN, SELLERAMP_DELAY_MAX
)


async def save_session(context):
    """Sauvegarde la session navigateur pour réutilisation."""
    os.makedirs("credentials", exist_ok=True)
    await context.storage_state(path=SELLERAMP_SESSION_PATH)
    print("Session SellerAmp sauvegardée.")


async def check_eligibility(asin: str, page) -> str:
    """
    Vérifie l'éligibilité d'un ASIN sur SellerAmp.
    Retourne : ELIGIBLE / RESTRICTED / HAZMAT / UNKNOWN
    """
    try:
        await page.goto(f"{SELLERAMP_URL}/sas/lookup?oq={asin}", timeout=15000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Délai aléatoire anti-détection
        await asyncio.sleep(random.uniform(SELLERAMP_DELAY_MIN, SELLERAMP_DELAY_MAX))

        content = await page.content()

        if "alert-danger" in content or "Restricted" in content:
            return "RESTRICTED"
        elif "Hazmat" in content or "hazmat" in content:
            return "HAZMAT"
        elif "alert-success" in content or "Eligible" in content or "eligible" in content:
            return "ELIGIBLE"
        else:
            return "UNKNOWN"

    except Exception as e:
        print(f"Erreur check ASIN {asin} : {e}")
        return "UNKNOWN"


async def check_deals(deals: list[Deal]) -> list[Deal]:
    """
    Vérifie l'éligibilité de tous les deals via SellerAmp.
    Première fois : ouvre le navigateur pour connexion manuelle.
    Fois suivantes : utilise la session sauvegardée.
    """
    session_exists = os.path.exists(SELLERAMP_SESSION_PATH)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=session_exists)

        if session_exists:
            context = await browser.new_context(storage_state=SELLERAMP_SESSION_PATH)
            print("Session SellerAmp chargée.")
        else:
            print("\n=== PREMIÈRE CONNEXION SELLERAMP ===")
            print("Le navigateur va s'ouvrir.")
            print("Connecte-toi avec Google, puis appuie sur Entrée ici.")
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(SELLERAMP_URL)
            input("Appuie sur Entrée une fois connecté à SellerAmp...")
            await save_session(context)

        page = await context.new_page()

        for deal in deals:
            print(f"Vérification éligibilité : {deal.asin} - {deal.titre[:40]}...")
            statut = await check_eligibility(deal.asin, page)
            deal.statut = statut
            print(f"  → {statut}")

        await browser.close()

    return deals
