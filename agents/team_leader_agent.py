"""
TeamLeaderAgent — Orchestrateur Python du pipeline OA.

Stratégie selon tokens Keepa disponibles :
  < 30    : skip total
  30-80   : Agent 1 réduit (pas multimarket)
  80-150  : Agent 1 standard (sans Agent 2)
  150-250 : Agent 1 full avec multimarket
  >= 250  : Agent 1 full + Agent 2 EU (cross-border actif)

Comportement :
  - Vérifie si un run récent a eu lieu (< 3h) → skip si oui
  - Si tokens >= 150 : envoie notif Telegram "Run dans 15min", attend 15min
  - Lance le pipeline, log les consignes envoyées à chaque agent
  - Sauvegarde le run dans Supabase (table 'runs') + run_log.json
  - Notif Telegram finale avec résumé
"""
import json
import time
import asyncio
import os
import requests as _requests
from datetime import datetime, timezone
from pathlib import Path

from config import KEEPA_API_KEY, AGENT_TOKEN_BUDGET, SC_SESSION_PATH, SC_URL
from notifier import send_telegram

LOG_PATH = Path(__file__).parent.parent / "logs" / "run_log.json"

# Délai minimum entre deux runs réussis (en heures)
MIN_RUN_INTERVAL_H = 3.0

# Délai d'attente après notif Telegram avant lancement (secondes)
NOTIF_DELAY_S = 15 * 60  # 15 minutes


# ── Log helpers ───────────────────────────────────────────────────────────────

def _load_log() -> list:
    try:
        if LOG_PATH.exists():
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def _append_run(entry: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_log()
    entries.append(entry)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries[-100:], f, ensure_ascii=False, indent=2, default=str)


# ── Tokens ────────────────────────────────────────────────────────────────────

def _check_tokens() -> int:
    """Lit le solde réel via l'endpoint Keepa /token (0 token consommé)."""
    try:
        r = _requests.get(
            "https://api.keepa.com/token",
            params={"key": KEEPA_API_KEY},
            timeout=10
        )
        data = r.json()
        tokens = data.get("tokensLeft", 0)
        return int(tokens)
    except Exception as e:
        print(f"[TeamLeader] Erreur lecture tokens : {e}")
        return AGENT_TOKEN_BUDGET


def _decide_strategy(tokens: int) -> dict:
    if tokens < 30:
        return {"name": "skip", "run_agent1": False, "run_agent2": False, "multimarket": False}
    elif tokens < 80:
        return {"name": "reduced", "run_agent1": True, "run_agent2": False, "multimarket": False}
    elif tokens < 150:
        return {"name": "standard", "run_agent1": True, "run_agent2": False, "multimarket": True}
    elif tokens < 250:
        return {"name": "full", "run_agent1": True, "run_agent2": False, "multimarket": True}
    else:
        return {"name": "full_eu", "run_agent1": True, "run_agent2": True, "multimarket": True}


def _should_run(tokens: int) -> tuple[bool, str]:
    """Vérifie si un run est nécessaire (délai min depuis dernier run réussi)."""
    entries = _load_log()
    recent = [e for e in entries if e.get("status") in ("success", "no_deals")]
    if recent:
        last = recent[-1]
        try:
            last_time = datetime.fromisoformat(last["date"])
            elapsed_h = (datetime.now(timezone.utc) - last_time).total_seconds() / 3600
            if elapsed_h < MIN_RUN_INTERVAL_H:
                return False, f"Run récent il y a {elapsed_h:.1f}h (minimum {MIN_RUN_INTERVAL_H}h entre runs)"
        except Exception:
            pass
    return True, "ok"


# ── Consignes agents ──────────────────────────────────────────────────────────

def _build_consignes_agent1(strategy: dict, tokens: int) -> str:
    multimarket = "OUI (DE / IT / ES)" if strategy["multimarket"] else "NON (stratégie réduite)"
    return (
        f"Stratégie : {strategy['name']} | Budget tokens : {tokens}\n"
        f"Multimarket : {multimarket}\n"
        f"Filtres : BSR 1k–50k, Buy Box 15€–200€, Amazon non vendeur\n"
        f"Catégories : Kitchen, Toys & Games, Sports & Outdoors, Home & Garden, Electronics, Pet Supplies, Office Products\n"
        f"Stop si tokens_left < 50"
    )


def _build_consignes_agent2(tokens_budget: int) -> str:
    return (
        f"Budget tokens : {tokens_budget} (solde réel après Agent 1)\n"
        f"Domaines : DE → IT → ES\n"
        f"Critères : prix EU > prix FR + 15%, BSR EU < 80k, Amazon non vendeur EU\n"
        f"Profit net EFN minimum : 5€\n"
        f"Stop si tokens_left < 50"
    )


# ── Re-check deals UNKNOWN ────────────────────────────────────────────────────

async def _retry_unknown_deals() -> int:
    """Re-vérifie les deals UNKNOWN du jour via SC. Coût : 0 token Keepa."""
    from clients.supabase_client import get_unknown_deals_today, update_deal_statut
    from clients.selleramp_checker import check_eligibility
    from playwright.async_api import async_playwright

    unknown = get_unknown_deals_today()
    if not unknown:
        return 0

    print(f"\n[TeamLeader] Re-vérification {len(unknown)} deals UNKNOWN...")
    updated = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=SC_SESSION_PATH)
        page = await context.new_page()

        for row in unknown:
            asin = row["asin"]
            titre = (row.get("titre") or "")[:40]
            print(f"  Re-check : {asin} - {titre}...")
            statut = await check_eligibility(asin, page)
            if statut != "UNKNOWN":
                update_deal_statut(asin, statut)
                print(f"  => {statut} ✓")
                updated += 1
            else:
                print(f"  => toujours UNKNOWN")

        await browser.close()

    print(f"[TeamLeader] UNKNOWN re-check terminé : {updated}/{len(unknown)} mis à jour")
    return updated


# ── Vérification session SC ───────────────────────────────────────────────────

async def _check_sc_session() -> bool:
    """Vérifie si la session Seller Central est encore valide (0 token Keepa)."""
    if not os.path.exists(SC_SESSION_PATH):
        return False
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=SC_SESSION_PATH)
            page = await context.new_page()
            await page.goto(f"{SC_URL}/home", timeout=20000)
            await page.wait_for_load_state("networkidle", timeout=15000)
            url = page.url
            await browser.close()
            return "sellercentral.amazon" in url and "/ap/" not in url and "signin" not in url
    except Exception as e:
        print(f"[TeamLeader] Erreur vérification session SC : {e}")
        return False


# ── Orchestrateur ─────────────────────────────────────────────────────────────

class TeamLeaderAgent:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.run_entry = {
            "date":               self.start_time.isoformat(),
            "tokens_before":      None,
            "tokens_after":       None,
            "tokens_used":        None,
            "strategy":           None,
            "deals_found":        0,
            "deals_eligible":     0,
            "deals_cross_border": 0,
            "status":             "pending",
            "error":              None,
            "consignes_agent1":   None,
            "consignes_agent2":   None,
            "duree_secondes":     None,
        }

    async def run(self):
        print("=== OA Tool — TeamLeaderAgent ===\n")

        # 1. Tokens
        tokens = _check_tokens()
        self.run_entry["tokens_before"] = tokens
        print(f"[TeamLeader] Tokens Keepa disponibles : {tokens}")

        strategy = _decide_strategy(tokens)
        self.run_entry["strategy"] = strategy["name"]
        print(f"[TeamLeader] Stratégie retenue : {strategy['name']}")

        # 2. Vérification session Seller Central (en premier — nécessaire pour tout)
        print("[TeamLeader] Vérification session Seller Central...")
        sc_ok = await _check_sc_session()
        if not sc_ok:
            msg = (
                "⚠️ <b>Session Seller Central expirée</b>\n\n"
                "Lance <b>refresh_session.bat</b> sur ton PC pour te reconnecter.\n"
                "Le prochain run reprendra automatiquement ensuite."
            )
            print("[TeamLeader] Session SC expirée — run annulé.")
            send_telegram(msg)
            self.run_entry["status"] = "skipped"
            self.run_entry["error"] = "Session Seller Central expirée"
            _append_run(self.run_entry)
            return
        print("[TeamLeader] Session SC valide ✓")

        # 3. Skip si tokens insuffisants → re-check UNKNOWN quand même
        if not strategy["run_agent1"]:
            hours = max(1, (80 - tokens) // 10 + 1)
            msg = f"[OA Tool] ⏭ Skip — tokens insuffisants ({tokens} < 30). Prochain run dans ~{hours}h."
            print(msg)
            send_telegram(msg)
            self.run_entry["status"] = "skipped"
            await _retry_unknown_deals()
            _append_run(self.run_entry)
            return

        # 4. Skip si run récent → re-check UNKNOWN quand même
        should, reason = _should_run(tokens)
        if not should:
            print(f"[TeamLeader] Skip : {reason}")
            self.run_entry["status"] = "skipped"
            self.run_entry["error"] = reason
            await _retry_unknown_deals()
            _append_run(self.run_entry)
            return

        # 5. Notif Telegram + attente 15min (seulement si tokens >= 150)
        if tokens >= 150:
            notif_msg = (
                f"[OA Tool] 🔔 Run dans 15min\n"
                f"Stratégie : <b>{strategy['name']}</b> | Tokens : <b>{tokens}</b>\n"
                f"Laisse le PC allumé ☕"
            )
            send_telegram(notif_msg)
            print(f"[TeamLeader] Notif Telegram envoyée. Attente 15min...")
            time.sleep(NOTIF_DELAY_S)

        tokens_final = tokens
        all_deals = []

        try:
            # 5. Nettoyage
            from clients.supabase_client import clear_today_deals
            clear_today_deals()

            # 6. Consignes Agent 1
            consignes1 = _build_consignes_agent1(strategy, tokens)
            self.run_entry["consignes_agent1"] = consignes1
            print(f"\n[TeamLeader → Agent 1] {consignes1}")

            # 7. Agent 1
            from agents.acquisition_agent import AcquisitionAgent
            print(f"\n[TeamLeader] Lancement Agent 1 (stratégie={strategy['name']})...")
            agent1 = AcquisitionAgent()
            if not strategy["multimarket"]:
                agent1._skip_multimarket = True

            all_deals = agent1.run(token_budget=tokens)
            if agent1.last_tokens_left is not None:
                tokens_final = agent1.last_tokens_left
                print(f"[Keepa] Tokens après Agent 1 : {tokens_final}")

            self.run_entry["deals_found"] = len(all_deals)
            print(f"\n[TeamLeader] Candidats Keepa : {len(all_deals)}")

            if not all_deals:
                print("[TeamLeader] Aucun candidat. Fin du run.")
                self.run_entry["status"] = "no_deals"
                await _retry_unknown_deals()
                _append_run(self.run_entry)
                return

            # 8. Seller Central
            from clients.selleramp_checker import check_deals
            print("\n[TeamLeader] Vérification éligibilité Seller Central...")
            all_deals = await check_deals(all_deals)

            eligible = [d for d in all_deals if d.statut == "ELIGIBLE"]
            non_eligible = [d for d in all_deals if d.statut != "ELIGIBLE"]
            print(f"[TeamLeader] Éligibles : {len(eligible)} / {len(all_deals)}")
            self.run_entry["deals_eligible"] = len(eligible)

            # 9. Agent 2 EU — re-lit tokens réels (rechargés pendant Agent 1)
            if strategy["run_agent2"]:
                tokens_real = _check_tokens()
                print(f"[TeamLeader] Tokens réels après Agent 1 : {tokens_real} (estimation : {tokens_final})")
                tokens_final = tokens_real

            if strategy["run_agent2"] and tokens_final >= 80:
                consignes2 = _build_consignes_agent2(tokens_final)
                self.run_entry["consignes_agent2"] = consignes2
                print(f"\n[TeamLeader → Agent 2] {consignes2}")

                from agents.cross_border_agent import CrossBorderAgent
                print("\n[TeamLeader] Lancement Agent 2 EU (cross-border sourcing)...")
                agent2 = CrossBorderAgent()
                agent2.run(token_budget=tokens_final)
                if agent2.last_tokens_left is not None:
                    tokens_final = agent2.last_tokens_left
                    print(f"[Keepa] Tokens après Agent 2 : {tokens_final}")
                self.run_entry["deals_cross_border"] = agent2.opportunities_saved
            else:
                print(f"[TeamLeader] Agent 2 EU non activé (stratégie={strategy['name']}).")

            # 10. Sauvegarde Supabase (deals Agent 1)
            from clients.supabase_client import save_deals
            save_deals(non_eligible + eligible)

            # 11. Re-check deals UNKNOWN du run précédent (0 token Keepa)
            await _retry_unknown_deals()

            # 12. Stats finales
            self.run_entry["tokens_after"] = tokens_final
            self.run_entry["tokens_used"] = tokens - tokens_final
            self.run_entry["status"] = "success"

            print(f"\n=== Run terminé ({strategy['name']}) ===")
            print(f"  {len(eligible)} deals éligibles | {self.run_entry['deals_cross_border']} cross-border")
            print(f"  Tokens utilisés : {tokens} → {tokens_final} = {tokens - tokens_final} consommés")

        except Exception as e:
            self.run_entry["status"] = "error"
            self.run_entry["error"] = str(e)
            print(f"[TeamLeader] ERREUR : {e}")
            raise
        finally:
            # Durée du run
            elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            self.run_entry["duree_secondes"] = int(elapsed)

            _append_run(self.run_entry)
            print(f"[TeamLeader] Log : {LOG_PATH}")

            # Sauvegarde dans Supabase
            try:
                from clients.supabase_client import save_run
                save_run(self.run_entry)
            except Exception as e:
                print(f"[TeamLeader] Erreur save_run Supabase : {e}")


async def run():
    leader = TeamLeaderAgent()
    await leader.run()


if __name__ == "__main__":
    asyncio.run(run())
