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
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    #MainMenu, footer {visibility: hidden;}
    .block-container {padding-top: 1.5rem;}

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #1e293b !important;
        border-right: 1px solid #334155;
    }
    section[data-testid="stSidebar"] * {color: #e2e8f0 !important;}
    section[data-testid="stSidebar"] hr {border-color: #334155;}

    /* Header band */
    .nx-header {
        background: linear-gradient(90deg, #1e40af, #2563eb);
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .nx-title {font-size: 1.6rem; font-weight: 800; color: #fff; margin: 0;}
    .nx-sub {font-size: 0.85rem; color: #bfdbfe; margin-top: 2px;}
    .nx-date {background: rgba(255,255,255,0.15); color: #fff; border-radius: 20px; padding: 6px 16px; font-size: 0.8rem;}

    /* KPI */
    .kpi {
        background: #fff;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.07);
    }
    .kpi-num {font-size: 2.2rem; font-weight: 800; line-height: 1.1; color: #0f172a;}
    .kpi-lbl {font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;}

    /* Table header */
    .th {font-size: 0.68rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.8px; padding: 8px 0; border-bottom: 2px solid #e2e8f0;}

    /* Deal row */
    .deal-card {
        background: #fff;
        border-radius: 10px;
        border: 1px solid #e2e8f0;
        padding: 14px 18px;
        margin-bottom: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        transition: box-shadow 0.15s;
    }
    .deal-card:hover {box-shadow: 0 4px 12px rgba(37,99,235,0.1); border-color: #93c5fd;}

    .score-green {background:#dcfce7;color:#15803d;border-radius:20px;padding:3px 10px;font-size:0.72rem;font-weight:700;}
    .score-yellow {background:#fef9c3;color:#a16207;border-radius:20px;padding:3px 10px;font-size:0.72rem;font-weight:700;}
    .score-red {background:#fee2e2;color:#dc2626;border-radius:20px;padding:3px 10px;font-size:0.72rem;font-weight:700;}
    .asin {background:#eff6ff;color:#2563eb;border-radius:5px;padding:2px 7px;font-size:0.72rem;font-family:monospace;}

    .val {font-size:0.95rem;font-weight:600;color:#0f172a;}
    .sub {font-size:0.75rem;color:#94a3b8;}
    .red {color:#dc2626;font-weight:600;}
    .green {color:#16a34a;font-weight:600;}

    /* Sidebar nav */
    .nav-label {font-size:0.65rem;color:#64748b !important;text-transform:uppercase;letter-spacing:1.5px;padding:0 8px;margin-top:16px;}
    .nav-item {display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;font-size:0.88rem;font-weight:500;cursor:pointer;margin:2px 0;}
    .nav-item.active {background:rgba(37,99,235,0.2) !important;color:#93c5fd !important;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ Nexyla")
    st.markdown("**OA Tool** — Sourcing FBA")
    st.divider()
    st.markdown("**Navigation**")
    st.page_link("app.py", label="📊 Dashboard", icon=None)
    st.page_link("pages/1_Calculateur_ROI.py", label="🧮 Calculateur ROI", icon=None)
    st.divider()
    st.markdown("**Statut**")
    deals_count = 0
    try:
        from clients.supabase_client import get_today_deals as _g
        deals_count = len(_g())
    except:
        pass
    st.metric("Deals aujourd'hui", deals_count)
    st.caption(f"Mis à jour le {date.today().strftime('%d/%m/%Y')}")
    st.divider()
    st.caption("Lance `python main.py` sur ton PC pour scanner les deals.")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="nx-header">
    <div>
        <div class="nx-title">⚡ Nexyla OA Tool</div>
        <div class="nx-sub">Sourcing automatique · Amazon FBA France</div>
    </div>
    <div class="nx-date">📅 {date.today().strftime('%d %B %Y')}</div>
</div>
""", unsafe_allow_html=True)

deals = get_today_deals()
total  = len(deals)
verts  = sum(1 for d in deals if (d.get("score_deal") or 0) >= 70)
jaunes = sum(1 for d in deals if 40 <= (d.get("score_deal") or 0) < 70)
rouges = sum(1 for d in deals if (d.get("score_deal") or 0) < 40)

# ── KPIs ──────────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi"><div class="kpi-num" style="color:#2563eb">{total}</div><div class="kpi-lbl">Deals éligibles</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi"><div class="kpi-num" style="color:#16a34a">{verts}</div><div class="kpi-lbl">Score fort ≥ 70</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi"><div class="kpi-num" style="color:#d97706">{jaunes}</div><div class="kpi-lbl">Score moyen 40–69</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi"><div class="kpi-num" style="color:#dc2626">{rouges}</div><div class="kpi-lbl">Score faible &lt; 40</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if not deals:
    st.info("🔍 Aucun deal aujourd'hui. Lance `python main.py` sur ton PC pour démarrer le sourcing.")
    st.stop()

# ── En-têtes ──────────────────────────────────────────────────────────────────
h = st.columns([1, 3.5, 1.2, 1, 1.5, 1.2, 1.2, 1.5])
headers = ["Score", "Produit", "Catégorie", "BSR", "Buy Box moy 90j", "Total frais", "ROI*", "Marketplace"]
for col, label in zip(h, headers):
    col.markdown(f'<div class="th">{label}</div>', unsafe_allow_html=True)

MP_FLAGS = {"FR": "🇫🇷", "DE": "🇩🇪", "IT": "🇮🇹", "ES": "🇪🇸"}

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

    if score >= 70:
        badge = f'<span class="score-green">● {score}/100</span>'
    elif score >= 40:
        badge = f'<span class="score-yellow">● {score}/100</span>'
    else:
        badge = f'<span class="score-red">● {score}/100</span>'

    if moy > 0:
        pa_e  = round(moy * 0.7, 2)
        pf_e  = round(moy - frais - pa_e, 2)
        roi_e = round((pf_e / pa_e) * 100, 1) if pa_e > 0 else 0
        roi_html = f'<span class="{"green" if roi_e >= 25 else "red"}">{roi_e}%</span>'
    else:
        roi_html = "—"

    gain_str = f'<br><span class="green" style="font-size:0.75rem">↑ +{gain}€ vs FR</span>' if gain and gain > 0 else ""

    c = st.columns([1, 3.5, 1.2, 1, 1.5, 1.2, 1.2, 1.5])
    with c[0]: st.markdown(badge, unsafe_allow_html=True)
    with c[1]: st.markdown(f'<div class="val" style="font-size:0.85rem">{titre[:48]}{"…" if len(titre)>48 else ""}</div><div class="sub"><span class="asin">{asin}</span></div>', unsafe_allow_html=True)
    with c[2]: st.markdown(f'<div class="sub">{cat}</div>', unsafe_allow_html=True)
    with c[3]: st.markdown(f'<div class="val" style="font-size:0.85rem">#{bsr}</div><div class="sub">{fba} vendeurs</div>', unsafe_allow_html=True)
    with c[4]: st.markdown(f'<div class="val">{moy}€</div><div class="sub">min {mini}€</div>', unsafe_allow_html=True)
    with c[5]: st.markdown(f'<div class="red">{frais}€</div>', unsafe_allow_html=True)
    with c[6]: st.markdown(roi_html, unsafe_allow_html=True)
    with c[7]: st.markdown(f'<div class="val">{flag} {mp}</div>{gain_str}', unsafe_allow_html=True)

st.caption("\\* ROI estimé avec prix achat = 70% du Buy Box · Calcul précis → **Calculateur ROI** dans le menu à gauche")
