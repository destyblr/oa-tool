# Nexyla OA Tool — Contexte & Plan

## C'est quoi ce projet

Outil d'Online Arbitrage Amazon FBA France/Europe.
Pipeline automatique : trouver des produits rentables sur Amazon, vérifier qu'on peut les vendre, les afficher dans un dashboard web.

---

## Architecture

```
OA/
├── oa_tool/          ← Backend Python (pipeline automatique)
└── fba-dashboard/    ← Frontend JS/HTML déployé sur Netlify
```

### oa_tool/ — Pipeline Python

**Flux principal (`main.py`) :**
1. TeamLeaderAgent → vérifie tokens Keepa, décide la stratégie (skip ou run)
2. Agent 1 (Claude AI) → choisit catégories (rotation 7 cats), cherche ASINs Keepa, collecte données FR
3. Agent 1 (Python, automatique) → `_enrich_multimarket()` : fetch prix réels DE/IT/ES, calcule meilleure MP, arbitrage, score (si tokens_left >= 3)
4. Seller Central (Playwright, headless=False) → vérifie éligibilité ASIN
5. Supabase → sauvegarde tous les deals Agent 1 (tableau Données brutes 100% complet)
6. Agent 2 EU (Claude AI, si tokens >= 250) → sourcing natif sur DE/IT/ES, trouve produits EU > FR + 15%, sauvegarde opportunités cross-border séparément
7. Le dashboard lit Supabase et affiche

**Fichiers clés :**
- `main.py` — point d'entrée, délègue au TeamLeaderAgent
- `agents/team_leader_agent.py` — orchestrateur Python : vérifie tokens, décide stratégie, orchestre les agents, écrit logs/run_log.json
- `config.py` — tous les paramètres (filtres, frais FBA/EFN, marketplaces)
- `restrictions.json` — profil compte + catégories/ASINs/marques interdits
- `approved_brands.json` — marques confirmées ELIGIBLE (apprentissage automatique)
- `agents/acquisition_agent.py` — Agent 1 : acquisition ASINs + enrichissement multimarket
- `agents/cross_border_agent.py` — Agent 2 : analyse opportunités EU sur toute la base Supabase
- `agents/agent_tools.py` — fonctions outils partagées entre agents
- `clients/keepa_client.py` — requêtes Keepa, calcul score/arbitrage, frais
- `clients/selleramp_checker.py` — Playwright → Seller Central, vérifie ELIGIBLE/RESTRICTED/HAZMAT
- `clients/supabase_client.py` — save_deals / get_today_deals / clear_today_deals
- `models/deal.py` — dataclass Deal (tous les champs)
- `utils/fees_calculator.py` — calcul frais FBA, EFN, URSSAF, referral, shipping

**Config actuelle (`config.py`) :**
- BSR : 1 000 – 50 000
- Buy Box : 15€ – 200€ (moy 90j min 15€)
- Vendeurs FBA : 1 – 15
- Exclure Amazon vendeur : OUI
- ROI min : 25%
- URSSAF : 12.3% (auto-entrepreneur)
- AGENT_TOKEN_BUDGET : 200 (env var)
- Catégories : définies dans restrictions.json
- Marketplaces EFN : FR, DE, IT, ES

**Profil compte (`restrictions.json`) :**
- is_new_account = true, 0 vente, 0 autorisation
- Catégories accessibles (non-gatées) : Toys & Games, Sports & Outdoors, Kitchen, Home & Garden, Electronics, Pet Supplies
- Catégories gatées interdites : Health & Beauty, Grocery, Baby, Jewelry, Watches, Clothing, Shoes, Handmade, Music, Video Games, Automotive, Industrial
- restricted_brands : ~40 marques connues gatées/génériques
- approved_brands : apprentissage automatique via selleramp_checker (marques confirmées ELIGIBLE)

**Modèle Deal — champs clés :**
- Identification : asin, titre, categorie, bsr_fr
- Statut : statut (ELIGIBLE/RESTRICTED/HAZMAT/UNKNOWN)
- Prix : buy_box_fr, buy_box_de, buy_box_it, buy_box_es, buy_box_90j_moy_fr, buy_box_90j_min_fr
- Frais : referral_fee, frais_fba, frais_efn (DE), envoi_fba, urssaf, total_frais
- Rentabilité : roi_fr, profit_net_fr (€), roi_meilleur, gain_vs_fr, marketplace_recommandee, score_deal
- Arbitrage : alerte_arbitrage, ecart_arbitrage
- Produit : weight_g, size_tier (sauvegardés en base)
- Liens : lien_google_shopping (généré depuis titre)
- Manuel : prix_achat (saisi dans dashboard)

**Score deal (0-100) :**
- BSR < 5k → +40 | < 20k → +30 | < 50k → +20
- ROI ≥ 50% → +40 | ≥ 35% → +30 | ≥ 25% → +20
- FBA ≤ 3 vendeurs → +20 | ≤ 8 → +10

---

## Rôle des Agents

### Agent 1 — AcquisitionAgent (`acquisition_agent.py`)
**Responsable de : tableau Données brutes 100% complet**

Étapes (LLM) :
1. Lit restrictions.json (profil compte, marques interdites/approuvées)
2. Évite les ASINs déjà scannés récemment (Supabase)
3. Choisit catégories selon profil compte (non-gatées uniquement)
4. search_keepa_category → ASINs candidats
5. get_asin_details_fr → données FR complètes (BSR, Buy Box, vendeurs, poids, tier)
6. Répond "ACQUISITION TERMINÉE"

Étapes (Python automatique, après LLM) :
7. `_products_to_deals()` : filtrage + création Deal + calcul frais + ROI FR + profit_net_fr
8. `_enrich_multimarket()` : fetch prix réels DE/IT/ES via Keepa, recalcul recommend_marketplace / detect_arbitrage / score

Résultat : deals avec TOUS les champs remplis → Seller Central → Supabase

### TeamLeaderAgent (`team_leader_agent.py`)
**Orchestrateur Python (non-LLM) — remplace la logique de main.py**

Stratégie selon tokens Keepa :
- < 30 : skip (affiche prochain run estimé)
- >= 30 : Agent 1 (catégorie en rotation parmi 7 cats)
- >= 250 : Agent 1 + Agent 2 EU
Pas de stratégie "reduced" — `_enrich_multimarket` tourne toujours si tokens_left >= 3.
Écrit `logs/run_log.json` (historique 100 derniers runs)

### Agent 2 — CrossBorderAgent v2 (`cross_border_agent.py`)
**Responsable de : sourcing EU natif → onglet Cross Border**

- Agent indépendant, ne reçoit PAS les deals Agent 1
- Cherche directement des ASINs sur DE/IT/ES via Keepa product_finder
- Compare prix EU vs prix FR pour trouver : prix EU > prix FR + 15%
- Calcule rentabilité EFN (profit net, ROI)
- Sauvegarde en base avec source='cross_border' et statut='CROSS_BORDER'
- Activé uniquement si tokens >= 250 (stratégie full_eu)

---

### fba-dashboard/ — Frontend Netlify

- HTML/JS pur + Tailwind CSS + Chart.js
- Se connecte directement à Supabase (clé publique dans `oa-supabase.js`)
- Auth : écran login → appel `auth-check.js` (Netlify Function) → token localStorage

**Onglet Analyse — 3 sous-onglets :**
- **Deals** : vue synthétique avec prix achat manuel, profit net réel, ROI réel
- **Cross Border** : tous les ASINs en base avec prix EU, triés par roi_meilleur (requête séparée, pas filtré par date)
- **Données brutes** : tableau complet, toutes colonnes remplies par Agent 1

**Colonnes Données brutes :**
Score | Statut | Titre | ASIN | Catégorie | BSR | Vend. FBA | Amazon | Buy Box FR | Moy 90j | Min 90j | Arbitrage | Sourcing
(Profit net, ROI FR, Meilleure MP, ROI meilleur supprimés — sans prix achat réel ces valeurs n'ont pas de sens)

**Fichiers dashboard :**
- `oa-supabase.js` — lecture deals Supabase, mapping, affichage tableau OA + Cross Border
- `oa-scanner.js` — scanner OA cross-border, scan Dealabs RSS
- `app.js` — dashboard principal FBA

**Netlify Functions actives :**
- `auth-check.js` — vérifie mot de passe, retourne token
- `retailers-save.js` — CRUD retailers dans Netlify Blobs
- `catalog-read.js` — lecture catalogue depuis Netlify Blobs

---

## Tokens Keepa

- 1 token = 1 ASIN analysé (query FR ou multi-domain)
- product_finder (search_keepa_category) ≈ 1-5 tokens
- get_asin_details_fr : 1 token/ASIN
- _enrich_multimarket : 1 token/ASIN × 3 domaines = 3 tokens/ASIN
- Budget recommandé : 200 tokens/run (env var AGENT_TOKEN_BUDGET)
- tokens_left exposé dans tous les retours outils Keepa → agent s'adapte

---

## État actuel

- Pipeline Agent 1 complet : acquisition + enrichissement multimarket en Python
- Seller Central : Playwright, session sauvegardée (sc_session.json)
- Supabase table `deals` : tous les champs présents (frais_efn, weight_g, size_tier, profit_net_fr, lien_google_shopping, source)
- TeamLeaderAgent : orchestre tout, écrit run_log.json, adapte stratégie selon tokens
- Agent 2 EU : sourcing natif DE/IT/ES, sauvegarde source='cross_border'
- Dashboard : tooltips calcul au survol, Cross Border = requête séparée (deals source='cross_border' OU buy_box_de/it/es non null)
- ROI FR = estimé (prix achat = 70% buy box moy 90j) | Profit net réel = saisi dans Deals tab

## Automatisation & Notifications

**Scheduler :** Windows Task Scheduler — lance `python main.py` toutes les 2h
- Tâche : `NexylOA_Run`
- PC doit être allumé (ou sortir de veille via option "Wake to run")

**TeamLeader — logique autonome :**
1. Vérifie tokens Keepa réels au démarrage
2. Vérifie session Seller Central (Playwright headless=False, 0 token)
   - Session morte → Telegram "⚠️ Session SC expirée — lance refresh_session.bat" → run annulé
3. Vérifie `run_log.json` → skip si run réussi il y a < 3h
4. Si tokens < 30 : skip pipeline principal (mais re-check UNKNOWN quand même)
5. Si tokens >= 150 : envoie Telegram "🔔 Run dans 15min", attend 15min, puis lance
6. Re-lit tokens réels avant Agent 2 (compensation recharge)
7. Re-check deals UNKNOWN du jour (0 token Keepa) — tourne toujours si SC valide
8. Sauvegarde run dans Supabase table `runs` + `logs/run_log.json`
- Rapport visible dans onglet Rapport du dashboard

**Session SC — gestion :**
- `credentials/sc_session.json` — cookies Playwright sauvegardés
- Expire de façon imprévisible (Amazon peut couper la session à tout moment)
- `refresh_session.py` / `refresh_session.bat` — à lancer manuellement pour renouveler
  - Ouvre navigateur → tu te connectes → 15s pour sélectionner compte France → session sauvegardée

**Re-check UNKNOWN (0 token Keepa) :**
- Deals dont statut=UNKNOWN du jour → re-vérifiés via SC Playwright
- Tourne à chaque run où SC est valide (même si pipeline principal skippé)
- Met à jour statut dans Supabase directement

**Comportement si tokens faibles pendant un run :**
- Agent 1 s'arrête seul à tokens_left < 50 (consigne)
- Si Keepa est temporairement à 0 : attend automatiquement la recharge (peut prendre ~10min)
- SC check tourne quand même sur les deals déjà trouvés
- Le run se termine normalement avec les deals partiels

**Telegram bot :**
- Config dans `.env` : `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `notifier.py` — fonction `send_telegram(message)`
- Même bot réutilisable sur d'autres projets (envoi seulement, pas de conflit)

## Supabase tables

**`deals`** — colonnes : frais_efn, weight_g, size_tier, profit_net_fr, source
**`runs`** — historique des runs (créer via SQL) :
```sql
CREATE TABLE IF NOT EXISTS runs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  date timestamptz, tokens_before int, tokens_after int, tokens_used int,
  strategy text, deals_found int DEFAULT 0, deals_eligible int DEFAULT 0,
  deals_cross_border int DEFAULT 0, status text, error text,
  consignes_agent1 text, consignes_agent2 text, duree_secondes int
);
```

## Dashboard — onglet Analyse

4 sous-onglets : **Deals** | **Cross Border** | **Données brutes** | **📋 Rapport**

**Rapport :**
- Encart "Dernier run" : statut, stratégie, deals, tokens, durée
- Barre visuelle tokens (X/60 max — bucket Keepa = 60, recharge 1/min)
- Tableau 30 derniers runs, cliquable → détail (consignes Agent 1 + Agent 2 + erreur si applicable)

**Toggles frais :**
- Les boutons "Avec URSSAF" et "Avec prep" ont été supprimés de l'interface OA
- La logique reste en place (localStorage) mais sans bouton visible

## Ce qui est supprimé / mort

- `oa_tool/dashboard/` (Streamlit) — supprimé
- `fba-dashboard/firebase-config.js` + `auth.js` — supprimés
- Tous les anciens agents Netlify (catalog-cron, enricher-cron, sourcing-cron...) — supprimés

---

## Stack technique

| Composant | Techno |
|---|---|
| Pipeline | Python 3.x, asyncio |
| Agent IA | Anthropic SDK (claude-sonnet-4-6) |
| Données produits | Keepa API (lib `keepa`) |
| Éligibilité SC | Playwright (Chromium, non-headless) |
| Base de données | Supabase (PostgreSQL) |
| Frontend | HTML/JS + Tailwind + Chart.js |
| Déploiement frontend | Netlify |
| Credentials | `.env` local (non commité) |
