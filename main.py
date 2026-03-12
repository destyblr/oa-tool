"""
main.py — Point d'entrée du pipeline OA.
Délègue entièrement au TeamLeaderAgent qui gère la stratégie selon les tokens Keepa.
"""
import sys
import asyncio
sys.stdout.reconfigure(encoding='utf-8')
from agents.team_leader_agent import run

if __name__ == "__main__":
    asyncio.run(run())
