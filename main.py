import asyncio
from clients.keepa_client import fetch_candidates
from clients.selleramp_checker import check_deals
from clients.supabase_client import save_deals, clear_today_deals
from config import CATEGORIES_TO_SCAN


async def run():
    print("=== OA Tool — Démarrage ===\n")

    # Supprime les deals du jour avant nouveau run
    clear_today_deals()

    all_deals = []

    # Étape 1 — Keepa : trouver les candidats
    for category in CATEGORIES_TO_SCAN:
        deals = fetch_candidates(category)
        all_deals.extend(deals)

    print(f"\nTotal candidats Keepa : {len(all_deals)}")

    if not all_deals:
        print("Aucun candidat trouvé. Fin du run.")
        return

    # Étape 2 — SellerAmp : vérifier l'éligibilité
    print("\nVérification éligibilité via SellerAmp...")
    all_deals = await check_deals(all_deals)

    eligible = [d for d in all_deals if d.statut == "ELIGIBLE"]
    print(f"\nDeals éligibles : {len(eligible)} / {len(all_deals)}")

    # Étape 3 — Supabase : sauvegarder tous les deals
    save_deals(all_deals)

    print("\n=== Run terminé ===")
    print(f"✓ {len(eligible)} deals éligibles disponibles dans l'interface.")


if __name__ == "__main__":
    asyncio.run(run())
