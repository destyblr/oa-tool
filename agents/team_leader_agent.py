"""
TeamLeaderAgent — Orchestrateur simplifié.

Logique :
  - Vérifie tokens Keepa (max 60)
  - < 5 tokens → skip
  - Regarde le dernier run réussi :
      → dernier = agent1 → lance Agent 2
      → sinon → lance Agent 1
  - Chaque agent utilise tous les tokens jusqu'à 0
  - clear_today_deals() seulement si Agent 1 tourne (début de cycle)
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
MIN_TOKENS = 55  # Attend bucket quasi-plein (60 max) avant de lancer


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
    """Retourne 'agent1' ou 'agent2' selon le dernier run réussi."""
    entries = _load_log()
    successful = [e for e in entries if e.get("status") in ("success", "no_deals")]
    if successful:
        last = successful[-1]
        if last.get("agent") == "agent1":
            return "agent2"
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
            "deals_cross_border": 0,
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

        # 4. Si Agent 1 : efface les deals du jour (nouveau cycle)
        if agent == "agent1":
            from clients.supabase_client import clear_today_deals
            clear_today_deals()

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
                self.run_entry["strategy"]       = a.category_name

                # Agent 3 : analyse IA des deals éligibles (0 token Keepa)
                if self.run_entry["deals_eligible"] > 0:
                    from agents.analysis_agent import AnalysisAgent
                    a3 = AnalysisAgent()
                    self.run_entry["deals_analysed"] = a3.run()
                else:
                    self.run_entry["deals_analysed"] = 0

            else:
                from agents.cross_border_agent import CrossBorderAgent
                a = CrossBorderAgent()
                a.run()
                self.run_entry["deals_cross_border"] = a.opportunities_saved
                self.run_entry["tokens_after"]       = a.tokens_end
                self.run_entry["tokens_used"]        = tokens - a.tokens_end

            self.run_entry["status"] = "success"

            # Notif succès
            if agent == "agent1":
                analysed = self.run_entry.get("deals_analysed", 0)
                msg = (
                    f"[OA Tool] Agent 1 termine\n"
                    f"Deals : {self.run_entry['deals_found']} | "
                    f"Eligibles : {self.run_entry['deals_eligible']} | "
                    f"Analyses IA : {analysed}\n"
                    f"Tokens : {tokens} -> {self.run_entry['tokens_after']}"
                )
            else:
                msg = (
                    f"[OA Tool] Agent 2 termine\n"
                    f"Opportunites cross-border : {self.run_entry['deals_cross_border']}\n"
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
