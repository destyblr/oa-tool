import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.supabase_client import get_today_deals
from datetime import date

st.set_page_config(
    page_title="Nexyla OA Tool",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif !important; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding: 0 !important; max-width: 100% !important; }
    section[data-testid="stSidebar"] { display: none; }

    /* ── NAVBAR ── */
    .navbar {
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        padding: 0 32px;
        display: flex;
        align-items: center;
        height: 56px;
        gap: 32px;
        position: sticky;
        top: 0;
        z-index: 999;
    }
    .nav-brand { font-size: 1.1rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 8px; }
    .nav-links { display: flex; gap: 4px; flex: 1; }
    .nav-link {
        color: rgba(255,255,255,0.7);
        padding: 6px 16px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        text-decoration: none;
    }
    .nav-link.active { background: rgba(255,255,255,0.2); color: #fff; }
    .nav-right { margin-left: auto; color: rgba(255,255,255,0.8); font-size: 0.82rem; }

    /* ── CONTENT ── */
    .content { padding: 28px 36px; background: #f8fafc; min-height: 100vh; }

    /* ── PAGE TITLE ── */
    .page-title { font-size: 1.6rem; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
    .page-sub { font-size: 0.85rem; color: #64748b; margin-bottom: 24px; }

    /* ── KPI CARDS ── */
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }
    .kpi {
        background: #fff;
        border-radius: 12px;
        padding: 20px 22px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .kpi-label { font-size: 0.7rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
    .kpi-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .kpi-num { font-size: 2rem; font-weight: 800; color: #0f172a; line-height: 1; }

    /* ── TABLE ── */
    .table-card { background: #fff; border-radius: 14px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.06); overflow: hidden; }
    .table-header { padding: 18px 22px; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; justify-content: space-between; }
    .table-title { font-size: 0.95rem; font-weight: 700; color: #0f172a; }
    .table-count { background: #eff6ff; color: #2563eb; border-radius: 20px; padding: 3px 12px; font-size: 0.75rem; font-weight: 600; }

    table.deals { width: 100%; border-collapse: collapse; }
    table.deals th {
        background: #f8fafc;
        color: #64748b;
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 11px 18px;
        text-align: left;
        border-bottom: 1px solid #e2e8f0;
        white-space: nowrap;
    }
    table.deals td {
        padding: 14px 18px;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.85rem;
        color: #334155;
        vertical-align: middle;
    }
    table.deals tr:last-child td { border-bottom: none; }
    table.deals tr:hover td { background: #fafbff; }

    /* ── BADGES ── */
    .badge { display:inline-flex;align-items:center;gap:4px;border-radius:20px;padding:3px 10px;font-size:0.72rem;font-weight:700; }
    .b-green { background:#dcfce7;color:#15803d; }
    .b-yellow { background:#fef3c7;color:#b45309; }
    .b-red { background:#fee2e2;color:#dc2626; }
    .b-blue { background:#eff6ff;color:#2563eb;border-radius:5px;font-family:monospace;font-size:0.72rem;padding:2px 8px; }

    .txt-main { font-weight: 600; color: #0f172a; }
    .txt-sub { font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }
    .txt-price { font-size: 1rem; font-weight: 700; color: #0f172a; }
    .txt-red { color: #dc2626; font-weight: 600; }
    .txt-green { color: #16a34a; font-weight: 700; }
    .txt-orange { color: #d97706; font-weight: 700; }

    .mp-cell { display:flex;align-items:center;gap:6px;font-weight:600;color:#0f172a; }
    .gain { font-size:0.75rem;color:#16a34a;font-weight:600; }

    /* ── EMPTY ── */
    .empty { text-align:center;padding:60px 20px; }
    .empty-icon { font-size: 2.5rem; margin-bottom: 12px; }
    .empty-title { font-size: 1.1rem; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
    .empty-sub { font-size: 0.85rem; color: #64748b; }
    code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; color: #4f46e5; font-size: 0.82rem; }
</style>
""", unsafe_allow_html=True)

deals = get_today_deals()
total  = len(deals)
verts  = sum(1 for d in deals if (d.get("score_deal") or 0) >= 70)
jaunes = sum(1 for d in deals if 40 <= (d.get("score_deal") or 0) < 70)
rouges = sum(1 for d in deals if (d.get("score_deal") or 0) < 40)

# ── NAVBAR ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="navbar">
    <div class="nav-brand">⚡ Nexyla</div>
    <div class="nav-links">
        <a class="nav-link active" href="#">📊 Dashboard OA</a>
        <a class="nav-link" href="#calculateur">🧮 Calculateur ROI</a>
    </div>
    <div class="nav-right">📅 {date.today().strftime('%d %B %Y')}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="content">', unsafe_allow_html=True)

# ── TITRE ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="page-title">📊 Online Arbitrage</div>
<div class="page-sub">Deals du jour — triés par score · sourcing automatique Amazon FBA France</div>
""", unsafe_allow_html=True)

# ── KPI ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi">
        <div class="kpi-label"><span class="kpi-dot" style="background:#4f46e5"></span>Deals éligibles</div>
        <div class="kpi-num" style="color:#4f46e5">{total}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label"><span class="kpi-dot" style="background:#16a34a"></span>Score fort ≥ 70</div>
        <div class="kpi-num" style="color:#16a34a">{verts}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label"><span class="kpi-dot" style="background:#d97706"></span>Score moyen 40–69</div>
        <div class="kpi-num" style="color:#d97706">{jaunes}</div>
    </div>
    <div class="kpi">
        <div class="kpi-label"><span class="kpi-dot" style="background:#dc2626"></span>Score faible &lt; 40</div>
        <div class="kpi-num" style="color:#dc2626">{rouges}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── TABLEAU ───────────────────────────────────────────────────────────────────
MP_FLAGS = {"FR": "🇫🇷", "DE": "🇩🇪", "IT": "🇮🇹", "ES": "🇪🇸"}

if not deals:
    st.markdown(f"""
    <div class="table-card">
        <div class="table-header">
            <span class="table-title">Deals du jour</span>
            <span class="table-count">0 résultat</span>
        </div>
        <div class="empty">
            <div class="empty-icon">🔍</div>
            <div class="empty-title">Aucun deal aujourd'hui</div>
            <div class="empty-sub">Lance <code>python main.py</code> sur ton PC pour démarrer le sourcing automatique.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
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

        if score >= 70:
            badge = f'<span class="badge b-green">● {score}/100</span>'
        elif score >= 40:
            badge = f'<span class="badge b-yellow">● {score}/100</span>'
        else:
            badge = f'<span class="badge b-red">● {score}/100</span>'

        if moy > 0:
            pa_e  = round(moy * 0.7, 2)
            pf_e  = round(moy - frais - pa_e, 2)
            roi_e = round((pf_e / pa_e) * 100, 1) if pa_e > 0 else 0
            roi_html = f'<span class="{"txt-green" if roi_e >= 25 else "txt-red"}">{roi_e}%</span>'
        else:
            roi_html = "—"

        gain_str = f'<div class="gain">↑ +{gain}€ vs FR</div>' if gain and gain > 0 else ""
        lien_html = f'<a href="{lien}" target="_blank" style="color:#4f46e5;font-size:0.78rem;font-weight:600;text-decoration:none">🔍 Voir</a>' if lien else "—"

        rows += f"""
        <tr>
            <td>{badge}</td>
            <td>
                <div class="txt-main">{titre[:50]}{"…" if len(titre)>50 else ""}</div>
                <div class="txt-sub"><span class="b-blue">{asin}</span> · {cat}</div>
            </td>
            <td>
                <div>#{bsr}</div>
                <div class="txt-sub">{fba} vendeurs FBA</div>
            </td>
            <td>
                <div class="txt-price">{moy}€</div>
                <div class="txt-sub">min {mini}€</div>
            </td>
            <td class="txt-red">{frais}€</td>
            <td>{roi_html}</td>
            <td>
                <div class="mp-cell">{flag} {mp}</div>
                {gain_str}
            </td>
            <td>{lien_html}</td>
        </tr>
        """

    st.markdown(f"""
    <div class="table-card">
        <div class="table-header">
            <span class="table-title">Deals du jour</span>
            <span class="table-count">{total} résultats</span>
        </div>
        <table class="deals">
            <thead><tr>
                <th>Score</th>
                <th>Produit</th>
                <th>BSR · Vendeurs</th>
                <th>Buy Box moy 90j</th>
                <th>Total frais</th>
                <th>ROI estimé*</th>
                <th>Marketplace</th>
                <th>Fournisseur</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    <div style="font-size:0.75rem;color:#94a3b8;margin-top:10px;padding:0 4px">
        * ROI estimé avec prix achat = 70% du Buy Box · Pour ton vrai ROI, utilise le <strong>Calculateur ROI</strong> ci-dessous.
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
