"""
refresh_session.py — Renouvelle la session Seller Central.

Lance ce script quand tu reçois une notif Telegram de session expirée :
  → Double-clic sur refresh_session.bat
  → Connecte-toi sur la page Amazon qui s'ouvre
  → Appuie sur Entrée dans ce terminal
  → Session sauvegardée, le prochain run OA fonctionnera normalement.
"""
import asyncio
import os
from playwright.async_api import async_playwright
from config import SC_URL, SC_SESSION_PATH


async def main():
    print("=== Renouvellement session Seller Central ===\n")
    print("Le navigateur va s'ouvrir sur Seller Central.")
    print("1. Connecte-toi (email + mot de passe + code SMS)")
    print("2. Attends d'être sur le tableau de bord SC")
    print("3. Reviens ici et appuie sur Entrée\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(f"{SC_URL}/home")
        print("En attente de connexion (max 5 min)...")
        # Attend d'etre sur SC proper (hors pages d'auth /ap/)
        await page.wait_for_url(
            lambda url: "sellercentral.amazon" in url and "/ap/" not in url and "signin" not in url,
            timeout=300000
        )
        await page.wait_for_load_state("networkidle", timeout=15000)
        print("\n>>> Sélectionne ton compte France si ce n'est pas fait.")
        print(">>> Session sauvegardée dans 15 secondes...")
        await asyncio.sleep(15)
        os.makedirs("credentials", exist_ok=True)
        await context.storage_state(path=SC_SESSION_PATH)
        await browser.close()

    print("\nSession sauvegardee. Le prochain run OA fonctionnera normalement.")


if __name__ == "__main__":
    asyncio.run(main())
