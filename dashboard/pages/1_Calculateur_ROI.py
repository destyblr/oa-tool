import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clients.supabase_client import get_today_deals, update_prix_achat
from utils.fees_calculator import calculate_roi

st.set_page_config(page_title="Calculateur ROI — Nexyla", page_icon="🧮", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #0f1117; color: #e2e8f0; }
    .page-title { font-size: 22px; font-weight: 800; color: #fff; margin-bottom: 4px; }
    .page-sub { font-size: 13px; color: #6b7a99; margin-bottom: 24px; }

    .deal-card {
        background: #1a1f2e;
        border: 1px solid #2d3561;
        border-radius: 14px;
        padding: 22px 26px;
        margin-bottom: 14px;
    }
    .deal-card-title { font-size: 15px; font-weight: 600; color: #fff; }
    .deal-card-meta { font-size: 12px; color: #6b7a99; margin-top: 4px; }
    .asin-code { font-family:monospace;font-size:12px;color:#5b8cff;background:#0d1627;padding:2px 7px;border-radius:4px; }

    .badge-green { background:#0d2818;color:#4ade80;border:1px solid #166534;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700; }
    .badge-yellow { background:#1c1a08;color:#fbbf24;border:1px solid #78350f;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700; }
    .badge-red { background:#1c0a0a;color:#f87171;border:1px solid #7f1d1d;border-radius:20px;padding:3px 10px;font-size:12px;font-weight:700; }

    .fee-block { background:#0f1117;border:1px solid #2d3561;border-radius:10px;padding:14px 16px; }
    .fee-row { display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e2438;font-size:13px; }
    .fee-row:last-child { border-bottom:none; }
    .fee-label { color:#9ca3af; }
    .fee-value { color:#fff;font-weight:500; }
    .fee-total { color:#f87171;font-weight:700; }

    .roi-success { background:linear-gradient(135deg,#0d2818,#0a1f12);border:1px solid #166534;border-radius:12px;padding:20px;text-align:center;margin-top:12px; }
    .roi-fail { background:linear-gradient(135deg,#1c0a0a,#150808);border:1px solid #7f1d1d;border-radius:12px;padding:20px;text-align:center;margin-top:12px; }
    .roi-num { font-size:30px;font-weight:800;margin-bottom:4px; }
    .roi-sub { font-size:13px;color:#9ca3af; }

    .divider { border:none;border-top:1px solid #2d3561;margin:14px 0; }
    .shop-btn { background:linear-gradient(135deg,#1e3a8a,#1d4ed8);color:white !important;padding:9px 18px;border-radius:8px;text-decoration:none !important;font-size:13px;font-weight:600;display:inline-block;margin-bottom:12px; }

    .stNumberInput input { background:#0f1117 !important;border-color:#2d3561 !important;color:#fff !important;border-radius:8px !important; }
    label { color:#9ca3af !important;font-size:12px !important; }
    .stButton button { background:linear-gradient(135deg,#2563eb,#1d4ed8) !important;color:white !important;border:none !important;border-radius:8px !important;font-weight:600 !important;width:100% !important; }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 24px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">🧮 Calculateur ROI</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Entre le prix fournisseur pour chaque deal et calcule ton profit réel.</div>', unsafe_allow_html=True)

deals = get_today_deals()

if not deals:
    st.markdown("""
    <div style="background:#1a1f2e;border:1px dashed #2d3561;border-radius:14px;padding:60px;text-align:center;">
        <div style="font-size:40px;margin-bottom:12px">🔍</div>
        <div style="font-size:18px;font-weight:600;color:#fff">Aucun deal éligible aujourd'hui</div>
        <div style="font-size:13px;color:#6b7a99;margin-top:8px">Retourne sur le Dashboard et lance main.py</div>
    </div>""", unsafe_allow_html=True)
    st.stop()

MP_FLAGS = {"FR": "🇫🇷", "DE": "🇩🇪", "IT": "🇮🇹", "ES": "🇪🇸"}

for deal in deals:
    score = deal.get("score_deal", 0) or 0
    mp    = deal.get("marketplace_recommandee", "FR") or "FR"
    flag  = MP_FLAGS.get(mp, "🌍")
    titre = deal.get("titre", "")
    asin  = deal.get("asin", "")
    moy   = deal.get("buy_box_90j_moy_fr") or 0
    mini  = deal.get("buy_box_90j_min_fr") or 0
    frais = deal.get("total_frais") or 0
    lien  = deal.get("lien_google_shopping", "")
    gain  = deal.get("gain_vs_fr") or 0
    alerte = deal.get("alerte_arbitrage", "") or ""

    if score >= 70:
        badge = f'<span class="badge-green">● {score}/100</span>'
    elif score >= 40:
        badge = f'<span class="badge-yellow">● {score}/100</span>'
    else:
        badge = f'<span class="badge-red">● {score}/100</span>'

    st.markdown(f"""
    <div class="deal-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
                <div class="deal-card-title">{titre[:70]}{"…" if len(titre)>70 else ""}</div>
                <div class="deal-card-meta" style="margin-top:6px">
                    {badge} &nbsp; <span class="asin-code">{asin}</span>
                    &nbsp; <span style="color:#6b7a99">{deal.get('categorie','')}</span>
                    &nbsp;&nbsp; {flag} <span style="color:#fff;font-weight:600">{mp}</span>
                    {"&nbsp;&nbsp; <span style='color:#4ade80;font-size:12px'>↑ +" + str(gain) + "€ vs FR</span>" if gain and gain > 0 else ""}
                    {"&nbsp;&nbsp; <span style='color:#fbbf24;font-size:12px'>⚡ " + alerte + "</span>" if alerte else ""}
                </div>
            </div>
            <div style="text-align:right">
                <div style="font-size:20px;font-weight:700;color:#fff">{moy}€</div>
                <div style="font-size:11px;color:#6b7a99">Buy Box moy 90j</div>
                <div style="font-size:11px;color:#6b7a99">min {mini}€</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_fees, col_calc = st.columns([1, 1])

    with col_fees:
        st.markdown(f"""
        <div class="fee-block">
            <div class="fee-row"><span class="fee-label">Referral Fee</span><span class="fee-value">{deal.get('referral_fee',0)}€</span></div>
            <div class="fee-row"><span class="fee-label">Frais FBA</span><span class="fee-value">{deal.get('frais_fba',0)}€</span></div>
            <div class="fee-row"><span class="fee-label">Envoi vers FBA</span><span class="fee-value">{deal.get('envoi_fba',0)}€</span></div>
            <div class="fee-row"><span class="fee-label">URSSAF (12.3%)</span><span class="fee-value">{deal.get('urssaf',0)}€</span></div>
            <div class="fee-row"><span class="fee-label"><strong>Total frais</strong></span><span class="fee-total">{frais}€</span></div>
        </div>
        """, unsafe_allow_html=True)
        if lien:
            st.markdown(f'<br><a href="{lien}" target="_blank" class="shop-btn">🔍 Vérifier prix fournisseur</a>', unsafe_allow_html=True)

    with col_calc:
        prix_achat = st.number_input(
            "Prix d'achat TTC (€)",
            min_value=0.0, step=0.5,
            key=f"prix_{deal['id']}",
            value=float(deal.get("prix_achat") or 0.0),
        )
        if st.button("Calculer le ROI", key=f"calc_{deal['id']}"):
            update_prix_achat(deal["id"], prix_achat)
            st.rerun()

        if prix_achat > 0:
            result = calculate_roi(prix_achat, moy, frais)
            profit = result.get("profit_net")
            roi    = result.get("roi")
            if profit is not None and roi is not None:
                if roi >= 25:
                    st.markdown(f"""
                    <div class="roi-success">
                        <div class="roi-num" style="color:#4ade80">+{profit}€</div>
                        <div class="roi-sub">Profit net · ROI <strong style="color:#4ade80">{roi}%</strong> ✅</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="roi-fail">
                        <div class="roi-num" style="color:#f87171">{profit}€</div>
                        <div class="roi-sub">ROI <strong style="color:#f87171">{roi}%</strong> · sous seuil 25% ❌</div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="margin-top:12px;padding:24px;text-align:center;border:1px dashed #2d3561;border-radius:10px;color:#6b7a99;font-size:13px">Entre ton prix d\'achat fournisseur</div>', unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
