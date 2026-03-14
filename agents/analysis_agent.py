"""
Agent 3 — Analyseur IA des deals éligibles (Claude Haiku).

Flow :
  1. Lit les deals ELIGIBLE du jour sans verdict depuis Supabase
  2. Pour chaque deal : appelle Claude Haiku avec les données du deal
  3. Claude retourne verdict (BUY/RISKY/SKIP) + analyse en français
  4. Met à jour le deal dans Supabase

Coût : ~$0.001 par deal (Claude Haiku). Pas de token Keepa consommé.
"""
import json
import anthropic
from datetime import date

from config import ANTHROPIC_API_KEY
from clients.supabase_client import get_client

MODEL = "claude-haiku-4-5-20251001"
MAX_DEALS_PER_RUN = 20

PROMPT_SYSTEM = """Tu es un expert Amazon OA France (Online Arbitrage FBA).
Tu analyses des produits Amazon pour déterminer s'ils sont rentables à revendre en FBA.
Réponds UNIQUEMENT en JSON valide, sans markdown, sans texte autour."""


def _build_prompt(deal: dict) -> str:
    moy = deal.get("buy_box_90j_moy_fr") or 0
    min90 = deal.get("buy_box_90j_min_fr") or 0
    instabilite = round(((moy - min90) / moy * 100), 1) if moy > 0 else 0

    return f"""Analyse ce produit Amazon FBA France et donne ton verdict.

Données :
- Titre : {deal.get('titre', '?')}
- Catégorie : {deal.get('categorie', '?')}
- BSR FR : {deal.get('bsr_fr', '?')} (top produit si < 10 000)
- Buy Box actuel : {deal.get('buy_box_fr', '?')}€
- Buy Box moy 90j : {moy}€
- Buy Box min 90j : {min90}€ (instabilité prix : {instabilite}%)
- Vendeurs FBA : {deal.get('nb_vendeurs_fba', '?')}
- Amazon vendeur : {deal.get('amazon_en_stock', False)}
- ROI estimé FR : {deal.get('roi_fr', '?')}%
- Profit net estimé : {deal.get('profit_net_fr', '?')}€
- Marketplace recommandée : {deal.get('marketplace_recommandee', 'FR')}
- ROI meilleur : {deal.get('roi_meilleur', '?')}%
- Alerte arbitrage : {deal.get('alerte_arbitrage') or 'Aucune'}
- Score : {deal.get('score_deal', '?')}/100

Critères :
- BUY : ROI >= 25%, profit >= 3€, BSR < 50k, vendeurs FBA entre 2-10, prix stable (instabilité < 20%)
- RISKY : ROI 15-25%, ou instabilité prix > 20%, ou 1 seul vendeur FBA (PL possible), ou BSR > 80k
- SKIP : ROI < 15%, ou profit < 2€, ou Amazon vendeur, ou BSR > 120k

Réponds en JSON : {{"verdict": "BUY|RISKY|SKIP", "analyse": "1-2 phrases max en français expliquant pourquoi"}}"""


class AnalysisAgent:
    def __init__(self):
        self.deals_analysed = 0

    def run(self) -> int:
        if not ANTHROPIC_API_KEY:
            print("[Agent 3] ANTHROPIC_API_KEY manquant — skip.")
            return 0

        client_sb = get_client()
        today = date.today().isoformat()

        try:
            resp = (
                client_sb.table("deals")
                .select("*")
                .eq("statut", "ELIGIBLE")
                .gte("date_scan", today)
                .is_("verdict", "null")
                .order("score_deal", desc=True)
                .limit(MAX_DEALS_PER_RUN)
                .execute()
            )
            deals = resp.data or []
        except Exception as e:
            print(f"[Agent 3] Erreur lecture Supabase : {e}")
            return 0

        if not deals:
            print("[Agent 3] Aucun deal à analyser.")
            return 0

        print(f"[Agent 3] {len(deals)} deals à analyser...")
        ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        for deal in deals:
            asin = deal.get("asin", "?")
            try:
                msg = ai_client.messages.create(
                    model=MODEL,
                    max_tokens=200,
                    system=PROMPT_SYSTEM,
                    messages=[{"role": "user", "content": _build_prompt(deal)}],
                )
                raw = msg.content[0].text.strip()
                result = json.loads(raw)
                verdict = result.get("verdict", "RISKY")
                analyse = result.get("analyse", "")

                if verdict not in ("BUY", "RISKY", "SKIP"):
                    verdict = "RISKY"

                client_sb.table("deals").update({
                    "verdict": verdict,
                    "analyse_ia": analyse,
                }).eq("id", deal["id"]).execute()

                self.deals_analysed += 1
                icon = "✅" if verdict == "BUY" else "⚠️" if verdict == "RISKY" else "❌"
                print(f"  {icon} {asin} → {verdict} | {analyse[:70]}")

            except Exception as e:
                print(f"  [Agent 3] Erreur {asin} : {e}")
                continue

        print(f"\n[Agent 3] Terminé — {self.deals_analysed} deals analysés")
        return self.deals_analysed
