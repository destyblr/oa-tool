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
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem;}

    .kpi-box {
        background: #1a1f2e;
        border-radius: 12px;
        padding: 20px 16px;
        text-align: center;
        border: 1px solid #2d3561;
    }
    .kpi-num {font-size: 2rem; font-weight: 800; line-height: 1.1;}
    .kpi-lbl {font-size: 0.7rem; color: #6b7a99; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;}

    .deal-row {
        background: #1a1f2e;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 8px;
        border-left: 4px solid #2d3561;
    }
    .deal-row.green {border-left-color: #4ade80;}
    .deal-row.yellow {border-left-color: #fbbf24;}
    .deal-row.red {border-left-color: #f87171;}

    .tag {display:inline-block; border-radius:6px; padding:2px 8px; font-size:0.72rem; font-weight:600;}
    .tag-green {background:#052e16;color:#4ade80;}
    .tag-yellow {background:#1c1a08;color:#fbbf24;}
    .tag-red {background:#1c0505;color:#f87171;}
    .tag-blue {background:#0a1428;color:#4f8eff;}

    .col-header {font-size:0.65rem; color:#6b7a99; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;}
    .col-val {font-size:1rem; font-weight:600; color:#fff;}
    .col-sub {font-size:0.75rem; color:#6b7a99;}
    .red-val {color:#f87171;}
    .green-val {color:#4ade80;}
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
col_t, col_d = st.columns([4, 1])
with col_t:
    st.markdown("## ⚡ Nexyla OA Tool")
    st.caption("Sourcing automatique · Amazon FBA France")
with col_d:
    st.markdown(f"<div style='text-align:right;color:#6b7a99;padding-top:16px'>{date.today().strftime('%d %B %Y')}</div>", unsafe_allow_html=True)

st.divider()

deals = get_today_deals()
total  = len(deals)
verts  = sum(1 for d in deals if (d.get("score_deal") or 0) >= 70)
jaunes = sum(1 for d in deals if 40 <= (d.get("score_deal") or 0) < 70)
rouges = sum(1 for d in deals if (d.get("score_deal") or 0) < 40)

# ── KPIs ─────────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#4f8eff">{total}</div><div class="kpi-lbl">Deals éligibles</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#4ade80">{verts}</div><div class="kpi-lbl">Score fort ≥ 70</div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#fbbf24">{jaunes}</div><div class="kpi-lbl">Score moyen 40-69</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi-box"><div class="kpi-num" style="color:#f87171">{rouges}</div><div class="kpi-lbl">Score faible &lt; 40</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Empty state ───────────────────────────────────────────────────────────────
if not deals:
    st.info("🔍 Aucun deal aujourd'hui — Lance `python main.py` sur ton PC pour démarrer le sourcing.")
    st.stop()

# ── En-têtes colonnes ─────────────────────────────────────────────────────────
h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1, 3, 1.2, 1, 1.5, 1.2, 1.2, 1.2])
with h1: st.markdown('<div class="col-header">Score</div>', unsafe_allow_html=True)
with h2: st.markdown('<div class="col-header">Produit</div>', unsafe_allow_html=True)
with h3: st.markdown('<div class="col-header">Catégorie</div>', unsafe_allow_html=True)
with h4: st.markdown('<div class="col-header">BSR</div>', unsafe_allow_html=True)
with h5: st.markdown('<div class="col-header">Buy Box moy 90j</div>', unsafe_allow_html=True)
with h6: st.markdown('<div class="col-header">Total frais</div>', unsafe_allow_html=True)
with h7: st.markdown('<div class="col-header">ROI estimé*</div>', unsafe_allow_html=True)
with h8: st.markdown('<div class="col-header">Marketplace</div>', unsafe_allow_html=True)

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
    lien  = deal.get("lien_google_shopping", "")

    if score >= 70:
        score_tag = f'<span class="tag tag-green">● {score}/100</span>'
        color_class = "green"
    elif score >= 40:
        score_tag = f'<span class="tag tag-yellow">● {score}/100</span>'
        color_class = "yellow"
    else:
        score_tag = f'<span class="tag tag-red">● {score}/100</span>'
        color_class = "red"

    if moy > 0:
        pa_e  = round(moy * 0.7, 2)
        pf_e  = round(moy - frais - pa_e, 2)
        roi_e = round((pf_e / pa_e) * 100, 1) if pa_e > 0 else 0
        roi_color = "green-val" if roi_e >= 25 else "red-val"
        roi_html = f'<span class="{roi_color}">{roi_e}%</span>'
    else:
        roi_html = "—"

    gain_html = f'<span class="green-val" style="font-size:0.75rem">+{gain}€</span>' if gain and gain > 0 else ""

    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1, 3, 1.2, 1, 1.5, 1.2, 1.2, 1.2])
    with c1:
        st.markdown(score_tag, unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="col-val" style="font-size:0.85rem">{titre[:45]}{"…" if len(titre)>45 else ""}</div><div class="col-sub"><span class="tag tag-blue">{asin}</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="col-sub">{cat}</div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="col-val" style="font-size:0.85rem">#{bsr}</div><div class="col-sub">{fba} FBA</div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="col-val">{moy}€</div><div class="col-sub">min {mini}€</div>', unsafe_allow_html=True)
    with c6:
        st.markdown(f'<div class="col-val red-val">{frais}€</div>', unsafe_allow_html=True)
    with c7:
        st.markdown(roi_html, unsafe_allow_html=True)
    with c8:
        st.markdown(f'<div class="col-val" style="font-size:0.9rem">{flag} {mp}</div>{gain_html}', unsafe_allow_html=True)

    st.markdown("---")

st.caption("\\* ROI estimé avec prix achat = 70% du Buy Box · Calcul précis → page **Calculateur ROI**")
