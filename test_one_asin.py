"""
Test rapide pipeline OA — 1 seul ASIN
Coût : ~1 token Keepa

Usage :
    cd oa_tool
    python test_one_asin.py
    python test_one_asin.py B09G4WNQMD   # ASIN personnalisé
"""
import sys
import asyncio
import json
sys.stdout.reconfigure(encoding='utf-8')

TEST_ASIN = sys.argv[1] if len(sys.argv) > 1 else None
TEST_CATEGORY = "Toys & Games"


async def main():
    global TEST_ASIN

    # ── Si pas d'ASIN fourni : chercher 1 ASIN valide via product_finder ─────
    if not TEST_ASIN:
        print("\n[0/4] Keepa — recherche 1 ASIN valide via product_finder...")
        from agents.agent_tools import tool_search_keepa_category
        search = tool_search_keepa_category(
            category_name=TEST_CATEGORY,
            bsr_min=1000, bsr_max=50000,
            buy_box_min_cents=1500, buy_box_max_cents=20000,
            max_asins=1,
        )
        if search.get("error") or not search.get("asins"):
            print(f"  ✗ Aucun ASIN trouvé : {search}")
            return
        TEST_ASIN = search["asins"][0]
        print(f"  ✓ ASIN trouvé : {TEST_ASIN} | Tokens restants : {search.get('tokens_left')}")

    print(f"\n{'='*50}")
    print(f"  Test pipeline OA — ASIN : {TEST_ASIN}")
    print(f"{'='*50}\n")

    # ── Étape 1 : Keepa — détails FR ─────────────────────────────────────────
    print("[1/4] Keepa — récupération détails FR...")
    from agents.agent_tools import tool_get_asin_details_fr
    results = tool_get_asin_details_fr([TEST_ASIN], TEST_CATEGORY)

    tokens_left = None
    products = []
    for r in results:
        if "_tokens_left" in r:
            tokens_left = r["_tokens_left"]
        elif r.get("asin"):
            products.append(r)

    if not products:
        print(f"  ✗ Aucun produit retourné. Résultat brut :\n{json.dumps(results, indent=2, default=str)}")
        return

    p = products[0]
    print(f"  ✓ Titre     : {p.get('titre', '?')[:60]}")
    print(f"  ✓ BSR FR    : {p.get('bsr_fr')}")
    print(f"  ✓ Buy Box   : {p.get('buy_box_fr')} € (moy 90j : {p.get('buy_box_90j_moy_fr')} €)")
    print(f"  ✓ FBA vend. : {p.get('nb_vendeurs_fba')}")
    print(f"  ✓ Poids     : {p.get('weight_g')} g | Tier : {p.get('size_tier')}")
    if tokens_left is not None:
        print(f"  ✓ Tokens Keepa restants : {tokens_left}")

    # ── Étape 2 : Conversion en Deal (filtres ignorés pour le test) ──────────
    print("\n[2/4] Conversion en Deal (mode test — filtres ignorés)...")
    from models.deal import Deal
    from utils.fees_calculator import calculate_total_fees
    buy_box = p.get('buy_box_90j_moy_fr') or p.get('buy_box_fr') or 30.0
    category = p.get('categorie', TEST_CATEGORY)
    size_tier = p.get('size_tier', 'large_standard_400')
    weight_g = p.get('weight_g') or 500
    fees = calculate_total_fees(buy_box, category, size_tier, weight_g, 'FR')
    deal = Deal(
        asin=p.get('asin', TEST_ASIN),
        titre=p.get('titre', ''),
        categorie=category,
        bsr_fr=p.get('bsr_fr') or 0,
        nb_vendeurs_fba=p.get('nb_vendeurs_fba', 0),
        amazon_en_stock=p.get('amazon_en_stock', False),
        buy_box_fr=p.get('buy_box_fr'),
        buy_box_90j_moy_fr=buy_box,
        buy_box_90j_min_fr=p.get('buy_box_90j_min_fr'),
        referral_fee=fees['referral_fee'],
        frais_fba=fees['frais_fba'],
        envoi_fba=fees['envoi_fba'],
        urssaf=fees['urssaf'],
        total_frais=fees['total_frais'],
        weight_g=weight_g,
        size_tier=size_tier,
        lien_google_shopping=p.get('lien_google_shopping'),
    )
    from clients.keepa_client import detect_arbitrage, calculate_score, recommend_marketplace
    from config import EFN_DESTINATIONS
    prix_achat_estime = round(buy_box * 0.7, 2)
    profit_fr = round(buy_box - fees['total_frais'] - prix_achat_estime, 2)
    deal.roi_fr = round((profit_fr / prix_achat_estime) * 100, 1) if prix_achat_estime > 0 else 0
    deal.profit_net_fr = profit_fr
    # Fetch prix réels DE/IT/ES (comme Agent 1 _enrich_multimarket)
    print("\n[2b/4] Keepa — enrichissement multimarket DE/IT/ES...")
    from agents.agent_tools import tool_fetch_multimarket_prices
    mp_prices = tool_fetch_multimarket_prices([deal.asin], list(EFN_DESTINATIONS))
    mp_tokens = mp_prices.pop('_tokens_left', None)
    asin_prices = mp_prices.get(deal.asin, {})
    deal.buy_box_de = asin_prices.get('DE')
    deal.buy_box_it = asin_prices.get('IT')
    deal.buy_box_es = asin_prices.get('ES')
    print(f"  ✓ DE: {deal.buy_box_de} € | IT: {deal.buy_box_it} € | ES: {deal.buy_box_es} €")
    if mp_tokens is not None:
        print(f"  ✓ Tokens restants : {mp_tokens}")

    fees_by_mp = {}
    for mp in EFN_DESTINATIONS:
        sell_price = getattr(deal, f'buy_box_{mp.lower()}') or buy_box
        fees_by_mp[mp] = calculate_total_fees(sell_price, category, size_tier, weight_g, mp)
    deal.frais_efn = fees_by_mp.get('DE', {}).get('total_frais')
    best_mp, best_roi, gain = recommend_marketplace(deal, fees_by_mp)
    deal.marketplace_recommandee = best_mp
    deal.roi_meilleur = best_roi
    deal.gain_vs_fr = gain
    alerte, ecart = detect_arbitrage(deal)
    deal.alerte_arbitrage = alerte
    deal.ecart_arbitrage = ecart
    deal.score_deal = calculate_score(deal)

    print(f"  ✓ Buy Box utilisé : {buy_box} € | Total frais : {fees['total_frais']} €")
    print(f"  ✓ ROI FR estimé   : {deal.roi_fr} %")
    print(f"  ✓ Score           : {deal.score_deal}")
    print(f"  ✓ MP recommandée  : {deal.marketplace_recommandee} | ROI meilleur : {deal.roi_meilleur} %")
    print(f"  ✓ Alerte arb.     : {deal.alerte_arbitrage}")

    # ── Étape 3 : SellerAmp — éligibilité ────────────────────────────────────
    print("\n[3/4] SellerAmp — vérification éligibilité...")
    try:
        from clients.selleramp_checker import check_deals
        checked = await check_deals([deal])
        deal = checked[0]
        print(f"  ✓ Statut : {deal.statut}")
    except Exception as e:
        print(f"  ⚠ SellerAmp ignoré ({e})")
        deal.statut = "ELIGIBLE"  # forcer pour tester Supabase

    # ── Étape 4 : Supabase — sauvegarde ──────────────────────────────────────
    print("\n[4/4] Supabase — sauvegarde...")
    try:
        from clients.supabase_client import save_deals
        save_deals([deal])
        print(f"  ✓ Deal sauvegardé en base")
    except Exception as e:
        print(f"  ✗ Erreur Supabase : {e}")

    print(f"\n{'='*50}")
    print(f"  Test terminé — 1 deal traité : {TEST_ASIN}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(main())
