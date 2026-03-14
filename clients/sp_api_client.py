"""
Client Amazon SP API — Listings Restrictions.
Vérifie l'éligibilité d'un ASIN sans Playwright ni navigateur.
Retourne : ELIGIBLE / RESTRICTED / HAZMAT / UNKNOWN
"""
import time
import requests
from config import SP_CLIENT_ID, SP_CLIENT_SECRET, SP_REFRESH_TOKEN, SP_SELLER_ID, SP_MARKETPLACE_ID

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE   = "https://sellingpartnerapi-eu.amazon.com"


class SPAPIClient:
    def __init__(self):
        self._access_token  = None
        self._token_expiry  = 0

    def _get_access_token(self) -> str:
        """Échange le refresh token contre un access token (valide 1h, mis en cache)."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        resp = requests.post(LWA_TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": SP_REFRESH_TOKEN,
            "client_id":     SP_CLIENT_ID,
            "client_secret": SP_CLIENT_SECRET,
        }, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        return self._access_token

    def check_eligibility(self, asin: str) -> str:
        """
        Vérifie si l'ASIN est vendable sur Amazon FR.
        Retourne : ELIGIBLE / RESTRICTED / HAZMAT / UNKNOWN
        """
        try:
            token = self._get_access_token()
            resp = requests.get(
                f"{SP_API_BASE}/listings/2021-08-01/restrictions",
                params={
                    "asin":           asin,
                    "conditionType":  "new_new",
                    "sellerId":       SP_SELLER_ID,
                    "marketplaceIds": SP_MARKETPLACE_ID,
                },
                headers={"x-amz-access-token": token},
                timeout=10,
            )

            if resp.status_code == 200:
                restrictions = resp.json().get("restrictions", [])
                if not restrictions:
                    return "ELIGIBLE"
                # Analyse les raisons
                for r in restrictions:
                    for reason in r.get("reasons", []):
                        msg = reason.get("message", "").lower()
                        code = reason.get("reasonCode", "").lower()
                        if "hazmat" in msg or "dangerous" in msg:
                            return "HAZMAT"
                return "RESTRICTED"

            elif resp.status_code == 400:
                return "RESTRICTED"
            elif resp.status_code == 403:
                print(f"[SP API] 403 sur {asin} — vérifier les rôles de l'app")
                return "UNKNOWN"
            else:
                print(f"[SP API] HTTP {resp.status_code} sur {asin}")
                return "UNKNOWN"

        except Exception as e:
            print(f"[SP API] Erreur {asin} : {e}")
            return "UNKNOWN"


# Instance partagée (réutilise le token en cache)
_client = None

def check_eligibility(asin: str) -> str:
    """Fonction utilitaire — utilise une instance partagée."""
    global _client
    if _client is None:
        _client = SPAPIClient()
    return _client.check_eligibility(asin)
