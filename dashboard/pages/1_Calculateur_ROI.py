import streamlit as st
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clients.supabase_client import get_today_deals, update_prix_achat
from utils.fees_calculator import calculate_roi
from datetime import date

st.set_page_config(page_title="Calculateur ROI — Nexyla", page_icon="🧮", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 0.5rem !important; padding-left: 2rem !important; padding-right: 2rem !important; }
    section[data-testid="stSidebar"] { display: none; }
    .stApp { background: #f8fafc; }

    .navbar {
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        padding: 0 32px;
        display: flex;
        align-items: center;
        height: 56px;
        gap: 32px;
        margin-bottom: 28px;
    }
    .nav-brand { font-size: 1.1rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 8px; }
    .nav-link { color: rgba(255,255,255,0.7); padding: 6px 16px; border-radius: 6px; font-size: 0.85rem; font-weight: 500; text-decoration: none; }
    .nav-link.active { background: rgba(255,255,255,0.2); color: #fff; }
    .nav-right { margin-left: auto; color: rgba(255,255,255,0.8); font-size: 0.82rem; }

    .page-title { font-size: 1.6rem; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
    .page-sub { font-size: 0.85rem; color: #64748b; margin-bottom: 24px; }

    .deal-block {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 22px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .deal-name { font-size: 1rem; font-weight: 700; color: #0f172a; margin-bottom: 6px; }
    .deal-meta { font-size: 0.78rem; color: #64748b; display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }

    .badge { display:inline-flex;align-items:center;border-radius:20px;padding:3px 10px;font-size:0.72rem;font-weight:700; }
    .b-green { background:#dcfce7;color:#15803d; }
    .b-yellow { background:#fef3c7;color:#b45309; }
    .b-red { background:#fee2e2;color:#dc2626; }
    .b-blue { background:#eff6ff;color:#2563eb;border-radius:5px;font-family:monospace;padding:2px 8px;font-size:0.72rem; }

    .divider { border: none; border-top: 1px solid #f1f5f9; margin: 16px 0; }

    .fee-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 18px; }
    .fee-row { display: flex; justify-content: space-between; padding: 7px 0; border-bottom: 1px solid #f1f5f9; font-size: 0.85rem; }
    .fee-row:last-child { border-bottom: none; }
    .fee-label { color: #64748b; }
    .fee-value { font-weight: 600; color: #0f172a; }
    .fee-total { color: #dc2626 !important; font-weight: 700 !important; }

    .roi-green { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 20px; text-align: center; }
    .roi-red { background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 20px; text-align: center; }
    .roi-num { font-size: 2rem; font-weight: 800; margin-bottom: 4px; }
    .roi-sub { font-size: 0.85rem; color: #64748b; }

    .shop-btn {
        display: inline-block;
        background: #4f46e5;
        color: white !important;
        padding: 9px 18px;
        border-radius: 8px;
        text-decoration: none !important;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 14px;
    }
    .price-big { font-size: 1.4rem; font-weight: 800; color: #0f172a; }
    .price-sub { font-size: 0.78rem; color: #94a3b8; }
    .empty-hint { color: #94a3b8; font-size: 0.85rem; border: 1px dashed #e2e8f0; border-radius: 10px; padding: 20px; text-align: center; margin-top: 12px; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="navbar">
    <div class="nav-brand">⚡ Nexyla</div>
    <a class="nav-link" href="/">📊 Dashboard OA</a>
    <a class="nav-link active" href="#">🧮 Calculateur ROI</a>
    <div class="nav-right">📅 {date.today().strftime('%d %B %Y')}</div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="page-title">🧮 Calculateur ROI</div>', unsafe_allow_html=True)
st.markdown('<div class="page-sub">Entre le prix fournisseur trouvé sur Google Shopping pour calculer ton profit réel.</div>', unsafe_allow_html=True)

deals = get_today_deals()

if not deals:
    st.info("🔍 Aucun deal éligible aujourd'hui. Lance `python main.py` sur ton PC.")
    st.stop()

MP_FLAGS = {"FR": "🇫🇷", "DE": "🇩🇪", "IT": "🇮🇹", "ES": "🇪🇸"}

for deal in deals:
    score  = deal.get("score_deal", 0) or 0
    mp     = deal.get("marketplace_recommandee", "FR") or "FR"
    flag   = MP_FLAGS.get(mp, "🌍")
    titre  = deal.get("titre", "")
    asin   = deal.get("asin", "")
    moy    = deal.get("buy_box_90j_moy_fr") or 0
    mini   = deal.get("buy_box_90j_min_fr") or 0
    frais  = deal.get("total_frais") or 0
    lien   = deal.get("lien_google_shopping", "")
    gain   = deal.get("gain_vs_fr") or 0
    alerte = deal.get("alerte_arbitrage", "") or ""

    if score >= 70:
        badge = f'<span class="badge b-green">● {score}/100</span>'
    elif score >= 40:
        badge = f'<span class="badge b-yellow">● {score}/100</span>'
    else:
        badge = f'<span class="badge b-red">● {score}/100</span>'

    st.markdown(f"""
    <div class="deal-block">
        <div class="deal-name">{titre[:80]}{"…" if len(titre)>80 else ""}</div>
        <div class="deal-meta">
            {badge}
            <span class="b-blue">{asin}</span>
            <span>{deal.get('categorie','')}</span>
            <span>{flag} {mp}</span>
            {"<span style='color:#16a34a;font-weight:600'>↑ +" + str(gain) + "€ vs FR</span>" if gain and gain > 0 else ""}
            {"<span style='color:#d97706'>⚡ " + alerte + "</span>" if alerte else ""}
        </div>
        <hr class="divider">
    </div>
    """, unsafe_allow_html=True)

    col_price, col_fees, col_calc = st.columns([1, 1.5, 1.5])

    with col_price:
        st.markdown(f"""
        <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px 20px;text-align:center">
            <div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Buy Box moy 90j</div>
            <div class="price-big">{moy}€</div>
            <div class="price-sub">min {mini}€</div>
        </div>
        """, unsafe_allow_html=True)
        if lien:
            st.markdown(f'<br><a href="{lien}" target="_blank" class="shop-btn">🔍 Vérifier prix fournisseur</a>', unsafe_allow_html=True)

    with col_fees:
        st.markdown(f"""
        <div class="fee-box">
            <div class="fee-row"><span class="fee-label">Referral Fee</span><span class="fee-value">{deal.get('referral_fee',0)}€</span></div>
            <div class="fee-row"><span class="fee-label">Frais FBA</span><span class="fee-value">{deal.get('frais_fba',0)}€</span></div>
            <div class="fee-row"><span class="fee-label">Envoi FBA</span><span class="fee-value">{deal.get('envoi_fba',0)}€</span></div>
            <div class="fee-row"><span class="fee-label">URSSAF (12.3%)</span><span class="fee-value">{deal.get('urssaf',0)}€</span></div>
            <div class="fee-row"><span class="fee-label"><strong>Total frais</strong></span><span class="fee-value fee-total">{frais}€</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_calc:
        prix_achat = st.number_input("Prix d'achat TTC (€)", min_value=0.0, step=0.5,
                                     key=f"prix_{deal['id']}", value=float(deal.get("prix_achat") or 0.0))
        if st.button("Calculer", key=f"calc_{deal['id']}"):
            update_prix_achat(deal["id"], prix_achat)
            st.rerun()

        if prix_achat > 0:
            result = calculate_roi(prix_achat, moy, frais)
            profit = result.get("profit_net")
            roi    = result.get("roi")
            if profit is not None and roi is not None:
                if roi >= 25:
                    st.markdown(f"""
                    <div class="roi-green">
                        <div class="roi-num" style="color:#16a34a">+{profit}€</div>
                        <div class="roi-sub">Profit net · ROI <strong style="color:#16a34a">{roi}%</strong> ✅</div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="roi-red">
                        <div class="roi-num" style="color:#dc2626">{profit}€</div>
                        <div class="roi-sub">ROI <strong style="color:#dc2626">{roi}%</strong> · sous seuil 25% ❌</div>
                    </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-hint">Entre le prix trouvé sur Google Shopping</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
