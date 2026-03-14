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


def get_unknown_deals_today() -> list[dict]:
    """Récupère les deals UNKNOWN du jour (id, asin, titre)."""
    client = get_client()
    today = date.today().isoformat()
    try:
        response = (
            client.table("deals")
            .select("id, asin, titre")
            .eq("statut", "UNKNOWN")
            .gte("date_scan", today)
            .execute()
        )
        return response.data or []
    except Exception as e:
        print(f"Erreur lecture UNKNOWN deals : {e}")
        return []


def update_deal_statut(asin: str, statut: str):
    """Met à jour le statut d'un deal par ASIN (deals du jour uniquement)."""
    client = get_client()
    today = date.today().isoformat()
    try:
        client.table("deals").update({"statut": statut}).eq("asin", asin).gte("date_scan", today).execute()
    except Exception as e:
        print(f"Erreur update statut {asin} : {e}")


def update_prix_achat(deal_id: str, prix_achat: float):
    """Met à jour le prix d'achat d'un deal."""
    client = get_client()
    try:
        client.table("deals").update({"prix_achat": prix_achat}).eq("id", deal_id).execute()
    except Exception as e:
        print(f"Erreur mise à jour prix achat : {e}")


def save_eligible_asin(asin: str, categorie: str, brand: str = "", titre: str = ""):
    """Sauvegarde ou met à jour un ASIN ELIGIBLE dans le pool persistant (sans filtres Keepa)."""
    client = get_client()
    try:
        client.table("eligible_pool").upsert(
            {"asin": asin, "categorie": categorie, "brand": brand, "titre": titre},
            on_conflict="asin"
        ).execute()
    except Exception as e:
        print(f"[eligible_pool] {asin}: {e}")


def clear_today_deals():
    """Supprime les deals du jour avant un nouveau run."""
    client = get_client()
    today = date.today().isoformat()
    try:
        client.table("deals").delete().gte("date_scan", today).execute()
        print("Deals du jour supprimés.")
    except Exception as e:
        print(f"Erreur suppression deals : {e}")



def save_run(entry: dict):
    """Sauvegarde un résumé de run dans la table Supabase 'runs'."""
    client = get_client()
    row = {
        "date":                entry.get("date"),
        "tokens_before":       entry.get("tokens_before"),
        "tokens_after":        entry.get("tokens_after"),
        "tokens_used":         entry.get("tokens_used"),
        "strategy":            entry.get("strategy"),
        "deals_found":         entry.get("deals_found", 0),
        "deals_eligible":      entry.get("deals_eligible", 0),
        "deals_cross_border":  entry.get("deals_cross_border", 0),
        "status":              entry.get("status"),
        "error":               entry.get("error"),
        "consignes_agent1":    entry.get("consignes_agent1"),
        "consignes_agent2":    entry.get("consignes_agent2"),
        "duree_secondes":      entry.get("duree_secondes"),
    }
    try:
        client.table("runs").insert(row).execute()
    except Exception as e:
        print(f"[Supabase] Erreur sauvegarde run : {e}")
