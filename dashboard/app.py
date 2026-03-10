import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.supabase_client import get_today_deals

st.set_page_config(
    page_title="Nexyla OA Tool",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* ── Base ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, .stApp { background: #080c14; font-family: 'Inter', sans-serif; color: #e2e8f0; }

    /* ── Header ── */
    .nx-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 0 28px 0; border-bottom: 1px solid #1e2438; margin-bottom: 28px;
    }
    .nx-brand { display: flex; align-items: center; gap: 12px; }
    .nx-icon { font-size: 28px; }
    .nx-name { font-size: 22px; font-weight: 800; color: #fff; letter-spacing: -0.5px; }
    .nx-name em { color: #4f8eff; font-style: normal; }
    .nx-tagline { font-size: 12px; color: #4b5675; margin-top: 1px; font-weight: 500; letter-spacing: 0.3px; }
    .nx-date { font-size: 12px; color: #4b5675; background: #111827; border: 1px solid #1e2438; padding: 6px 14px; border-radius: 20px; }

    /* ── KPI cards ── */
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 28px; }
    .kpi {
        background: #111827; border: 1px solid #1e2438;
        border-radius: 12px; padding: 18px 20px;
        transition: border-color 0.2s;
    }
    .kpi:hover { border-color: #2d3d6b; }
    .kpi-val { font-size: 30px; font-weight: 800; color: #fff; line-height: 1; }
    .kpi-label { font-size: 11px; font-weight: 600; color: #4b5675; text-transform: uppercase; letter-spacing: 1px; margin-top: 6px; }
    .kpi-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }

    /* ── Table ── */
    .nx-table-wrap { background: #111827; border: 1px solid #1e2438; border-radius: 14px; overflow: hidden; }
    .nx-table-header { padding: 16px 20px; border-bottom: 1px solid #1e2438; display: flex; align-items: center; justify-content: space-between; }
    .nx-table-title { font-size: 14px; font-weight: 700; color: #fff; }
    .nx-count { font-size: 12px; color: #4f8eff; background: #0d1b3e; border: 1px solid #1e3a8a; padding: 3px 10px; border-radius: 20px; }

    table.nx-table { width: 100%; border-collapse: collapse; }
    table.nx-table th {
        background: #0d1220; color: #4b5675; font-size: 10px;
        font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px;
        padding: 10px 16px; text-align: left; white-space: nowrap;
        border-bottom: 1px solid #1e2438;
    }
    table.nx-table td {
        padding: 13px 16px; border-bottom: 1px solid #131c2e;
        font-size: 13px; color: #cbd5e1; vertical-align: middle;
    }
    table.nx-table tr:last-child td { border-bottom: none; }
    table.nx-table tr:hover td { background: #0d1525; }

    /* ── Badges ── */
    .score { display:inline-flex;align-items:center;gap:5px;border-radius:20px;padding:3px 11px;font-size:12px;font-weight:700; }
    .s-green { background:#052e16;color:#4ade80;border:1px solid #166534; }
    .s-yellow { background:#1c1708;color:#fbbf24;border:1px solid #854d0e; }
    .s-red { background:#1c0505;color:#f87171;border:1px solid #991b1b; }

    .mp-badge { display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;color:#fff; }
    .gain-tag { font-size:11px;color:#4ade80;font-weight:600; }

    .asin { font-family:monospace;font-size:11px;color:#4f8eff;background:#0a1428;padding:2px 7px;border-radius:4px; }
    .prod-name { font-weight:600;color:#f1f5f9;font-size:13px;max-width:280px; }
    .prod-cat { font-size:11px;color:#4b5675;margin-top:2px; }

    .price-big { font-size:15px;font-weight:700;color:#fff; }
    .price-sm { font-size:11px;color:#4b5675; }
    .fees-val { color:#f87171;font-weight:600; }
    .roi-g { color:#4ade80;font-weight:700; }
    .roi-r { color:#f87171;font-weight:700; }

    .link-btn { color:#4f8eff !important;text-decoration:none;font-size:12px;font-weight:500; }
    .link-btn:hover { text-decoration:underline; }

    /* ── Footer note ── */
    .nx-note { font-size:11px;color:#4b5675;padding:12px 20px;border-top:1px solid #1e2438; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] { background: #0d1220 !important; }

    /* ── Hide Streamlit UI ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 24px; max-width: 1400px; }
</style>
""", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
from datetime import date
today_str = date.today().strftime("%d %B %Y")

st.markdown(f"""
<div class="nx-header">
    <div class="nx-brand">
        <div class="nx-icon">⚡</div>
        <div>
            <div class="nx-name"><em>Nexyla</em> OA Tool</div>
            <div class="nx-tagline">Sourcing automatique · Amazon FBA France</div>
        </div>
    </div>
    <div class="nx-date">📅 {today_str}</div>
</div>
""", unsafe_allow_html=True)

# ── DATA ──────────────────────────────────────────────────────────────────────
deals = get_today_deals()
total  = len(deals)
verts  = sum(1 for d in deals if (d.get("score_deal") or 0) >= 70)
jaunes = sum(1 for d in deals if 40 <= (d.get("score_deal") or 0) < 70)
rouges = sum(1 for d in deals if (d.get("score_deal") or 0) < 40)

# ── KPI ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi">
        <div class="kpi-val">{total}</div>
        <div class="kpi-label"><span class="kpi-dot" style="background:#4f8eff"></span>Deals éligibles</div>
    </div>
    <div class="kpi">
        <div class="kpi-val" style="color:#4ade80">{verts}</div>
        <div class="kpi-label"><span class="kpi-dot" style="background:#4ade80"></span>Score fort ≥ 70</div>
    </div>
    <div class="kpi">
        <div class="kpi-val" style="color:#fbbf24">{jaunes}</div>
        <div class="kpi-label"><span class="kpi-dot" style="background:#fbbf24"></span>Score moyen 40–69</div>
    </div>
    <div class="kpi">
        <div class="kpi-val" style="color:#f87171">{rouges}</div>
        <div class="kpi-label"><span class="kpi-dot" style="background:#f87171"></span>Score faible &lt; 40</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── EMPTY STATE ───────────────────────────────────────────────────────────────
if not deals:
    st.markdown("""
    <div style="background:#111827;border:1px dashed #1e2438;border-radius:14px;padding:80px;text-align:center;">
        <div style="font-size:44px;margin-bottom:14px">🔍</div>
        <div style="font-size:20px;font-weight:700;color:#fff">Aucun deal aujourd'hui</div>
        <div style="font-size:13px;color:#4b5675;margin-top:8px">Lance <code style="background:#0d1220;padding:2px 8px;border-radius:4px;color:#4f8eff">python main.py</code> pour démarrer le sourcing.</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── TABLE ─────────────────────────────────────────────────────────────────────
MP_FLAGS = {"FR": "🇫🇷", "DE": "🇩🇪", "IT": "🇮🇹", "ES": "🇪🇸"}

rows = ""
for deal in deals:
    score = deal.get("score_deal", 0) or 0
    mp    = deal.get("marketplace_recommandee", "FR") or "FR"
    flag  = MP_FLAGS.get(mp, "🌍")
    titre = deal.get("titre", "")
    asin  = deal.get("asin", "")
    cat   = deal.get("categorie", "")
    bsr   = f"{deal['bsr_fr']:,}" if deal.get("bsr_fr") else "—"
    fba   = deal.get("nb_vendeurs_fba", "—")
    moy   = deal.get("buy_box_90j_moy_fr") or 0
    mini  = deal.get("buy_box_90j_min_fr") or 0
    frais = deal.get("total_frais") or 0
    gain  = deal.get("gain_vs_fr") or 0
    lien  = deal.get("lien_google_shopping", "")
    alerte = deal.get("alerte_arbitrage", "") or ""

    # ROI estimé (prix achat = 70% buy box)
    if moy > 0:
        pa_e = round(moy * 0.7, 2)
        pf_e = round(moy - frais - pa_e, 2)
        roi_e = round((pf_e / pa_e) * 100, 1) if pa_e > 0 else 0
        roi_html = f'<span class="{"roi-g" if roi_e >= 25 else "roi-r"}">{roi_e}%</span>'
    else:
        roi_html = "—"

    if score >= 70:
        sc_html = f'<span class="score s-green">● {score}</span>'
    elif score >= 40:
        sc_html = f'<span class="score s-yellow">● {score}</span>'
    else:
        sc_html = f'<span class="score s-red">● {score}</span>'

    gain_html = f'<div class="gain-tag">+{gain}€</div>' if gain and gain > 0 else ""
    arb_html  = f'<div style="font-size:11px;color:#fbbf24">⚡ {alerte}</div>' if alerte else ""
    lien_html = f'<a href="{lien}" target="_blank" class="link-btn">🔍 Voir</a>' if lien else "—"

    rows += f"""
    <tr>
        <td>{sc_html}</td>
        <td>
            <div class="prod-name">{titre[:50]}{"…" if len(titre)>50 else ""}</div>
            <div style="margin-top:4px"><span class="asin">{asin}</span></div>
            <div class="prod-cat">{cat}</div>
        </td>
        <td>#{bsr}</td>
        <td style="color:#cbd5e1">{fba}</td>
        <td>
            <div class="price-big">{moy}€</div>
            <div class="price-sm">min {mini}€</div>
        </td>
        <td class="fees-val">{frais}€</td>
        <td>{roi_html}</td>
        <td>
            <div class="mp-badge">{flag} {mp}</div>
            {gain_html}
            {arb_html}
        </td>
        <td>{lien_html}</td>
    </tr>
    """

st.markdown(f"""
<div class="nx-table-wrap">
    <div class="nx-table-header">
        <span class="nx-table-title">Deals du jour</span>
        <span class="nx-count">{total} résultats</span>
    </div>
    <table class="nx-table">
    <thead><tr>
        <th>Score</th>
        <th>Produit</th>
        <th>BSR FR</th>
        <th>Vendeurs FBA</th>
        <th>Buy Box moy 90j</th>
        <th>Total frais</th>
        <th>ROI estimé*</th>
        <th>Marketplace</th>
        <th>Fournisseur</th>
    </tr></thead>
    <tbody>{rows}</tbody>
    </table>
    <div class="nx-note">* ROI estimé avec prix achat = 70% du Buy Box · Pour ton vrai ROI → <strong>Calculateur ROI</strong> dans le menu à gauche.</div>
</div>
""", unsafe_allow_html=True)
