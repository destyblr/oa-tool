from supabase import create_client
from models.deal import Deal
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import date


def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def save_deals(deals: list[Deal]):
    """Sauvegarde une liste de deals dans Supabase."""
    if not deals:
        print("Aucun deal à sauvegarder.")
        return

    client = get_client()
    rows = [deal.to_dict() for deal in deals]

    try:
        client.table("deals").insert(rows).execute()
        print(f"{len(rows)} deals sauvegardés dans Supabase.")
    except Exception as e:
        print(f"Erreur sauvegarde Supabase : {e}")


def get_today_deals() -> list[dict]:
    """Récupère les deals éligibles du jour."""
    client = get_client()
    today = date.today().isoformat()

    try:
        response = (
            client.table("deals")
            .select("*")
            .eq("statut", "ELIGIBLE")
            .gte("date_scan", today)
            .order("score_deal", desc=True)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Erreur lecture Supabase : {e}")
        return []


def update_prix_achat(deal_id: str, prix_achat: float):
    """Met à jour le prix d'achat d'un deal."""
    client = get_client()
    try:
        client.table("deals").update({"prix_achat": prix_achat}).eq("id", deal_id).execute()
    except Exception as e:
        print(f"Erreur mise à jour prix achat : {e}")


def clear_today_deals():
    """Supprime les deals du jour avant un nouveau run."""
    client = get_client()
    today = date.today().isoformat()
    try:
        client.table("deals").delete().gte("date_scan", today).execute()
        print("Deals du jour supprimés.")
    except Exception as e:
        print(f"Erreur suppression deals : {e}")
