"""
TeamLeaderAgent — Orchestrateur simplifié.

Logique :
  - Vérifie tokens Keepa (min 5 pour lancer)
  - Alternance Agent 1 / Agent 2 à chaque run
  - Chaque agent utilise les tokens disponibles
  - Telegram sur démarrage, succès et erreur
  - Sauvegarde run dans run_log.json + Supabase
"""
import json
import time
import requests as _requests
from datetime import datetime, timezone
from pathlib import Path

from config import KEEPA_API_KEY
from notifier import send_telegram

LOG_PATH = Path(__file__).parent.parent / "logs" / "run_log.json"
MIN_TOKENS = 60  # Lance uniquement quand le bucket est plein (60 max)


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
    try:
        r = _requests.get(
            "https://api.keepa.com/token",
            params={"key": KEEPA_API_KEY},
            timeout=10
        )
        return int(r.json().get("tokensLeft", 0))
    except Exception as e:
        print(f"[TeamLeader] Erreur lecture tokens : {e}")
        return 0


# ── Quel agent lancer ? ───────────────────────────────────────────────────────

def _next_agent() -> str:
    """Retourne toujours 'agent1' — Agent 2 (cross-border) désactivé temporairement."""
    return "agent1"


# ── Orchestrateur ─────────────────────────────────────────────────────────────

class TeamLeaderAgent:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.run_entry = {
            "date":               self.start_time.isoformat(),
            "agent":              None,
            "tokens_before":      None,
            "tokens_after":       None,
            "tokens_used":        None,
            "deals_found":        0,
            "deals_eligible":     0,
            "status":             "pending",
            "error":              None,
            "duree_secondes":     None,
        }

    def run(self):
        print("=== OA Tool — TeamLeaderAgent ===\n")

        # 1. Tokens
        tokens = _check_tokens()
        self.run_entry["tokens_before"] = tokens
        print(f"[TeamLeader] Tokens disponibles : {tokens}/60")

        # 2. Skip si tokens insuffisants
        if tokens < MIN_TOKENS:
            msg = f"[OA Tool] Skip — seulement {tokens} tokens disponibles (min {MIN_TOKENS})."
            print(msg)
            send_telegram(msg)
            self.run_entry["status"] = "skipped"
            self._save()
            return

        # 3. Quel agent lancer ?
        agent = _next_agent()
        self.run_entry["agent"] = agent
        print(f"[TeamLeader] Agent à lancer : {agent.upper()}")

        # 4. Si Agent 1 : pré-détermine la catégorie (sauvegardée même si erreur)
        if agent == "agent1":
            from agents.acquisition_agent import _get_next_category
            cat_name, _ = _get_next_category()
            self.run_entry["strategy"] = cat_name
            print(f"[TeamLeader] Catégorie : {cat_name}")

        # 5. Notif Telegram démarrage
        send_telegram(
            f"[OA Tool] Démarrage {agent.upper()}\n"
            f"Tokens : {tokens}/60"
        )

        try:
            if agent == "agent1":
                from agents.acquisition_agent import AcquisitionAgent
                a = AcquisitionAgent()
                deals = a.run()
                self.run_entry["deals_found"]    = a.deals_saved
                self.run_entry["deals_eligible"] = sum(1 for d in deals if d.statut == "ELIGIBLE")
                self.run_entry["tokens_after"]   = a.tokens_end
                self.run_entry["tokens_used"]    = tokens - a.tokens_end
                self.run_entry["strategy"]       = a.category_name  # confirme (peut différer si DB count a changé)

            # Agent 3 : analyse IA des deals éligibles sans verdict (0 token Keepa)
            from agents.analysis_agent import AnalysisAgent
            a3 = AnalysisAgent()
            nb_analysed = a3.run()
            self.run_entry["deals_analysed"] = nb_analysed

            self.run_entry["status"] = "success"

            # Notif succès
            analysed = self.run_entry.get("deals_analysed", 0)
            msg = (
                f"[OA Tool] Agent 1 termine\n"
                f"Deals : {self.run_entry['deals_found']} | "
                f"Eligibles : {self.run_entry['deals_eligible']} | "
                f"Analyses IA : {analysed}\n"
                f"Tokens : {tokens} -> {self.run_entry['tokens_after']}"
            )
            send_telegram(msg)
            print(f"\n[TeamLeader] {msg}")

        except Exception as e:
            self.run_entry["status"] = "error"
            self.run_entry["error"]  = str(e)
            print(f"[TeamLeader] ERREUR : {e}")
            send_telegram(f"[OA Tool] ERREUR {agent.upper()}\n{str(e)[:200]}")
            raise

        finally:
            elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            self.run_entry["duree_secondes"] = int(elapsed)
            self._save()

    def _save(self):
        _append_run(self.run_entry)
        print(f"[TeamLeader] Log : {LOG_PATH}")
        try:
            from clients.supabase_client import save_run
            save_run(self.run_entry)
        except Exception as e:
            print(f"[TeamLeader] Erreur save_run : {e}")


async def run():
    leader = TeamLeaderAgent()
    leader.run()


if __name__ == "__main__":
    leader = TeamLeaderAgent()
    leader.run()
