"""
main.py — Point d'entrée du pipeline OA.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from agents.team_leader_agent import TeamLeaderAgent

if __name__ == "__main__":
    TeamLeaderAgent().run()
