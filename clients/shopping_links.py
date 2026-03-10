import urllib.parse


def generate_link(titre: str) -> str:
    """Génère un lien Google Shopping pour vérifier le prix fournisseur."""
    query = urllib.parse.quote(titre)
    return f"https://www.google.com/search?q={query}&tbm=shop"
