# TTAP Phase 3 : exceptions, substitutions et concurrence — plan d'implémentation

**Objectif :** quand la demande exacte ne peut pas être servie, le Lookup propose de façon **déterministe et générique** soit un plan mixte (quantité partielle + substitut officiel + reliquat), soit un good / better / best complet qui intègre la fiabilité et le carbone. La commande produit une **réponse de type Peppol** (`AP` / `CA` / `RE`). Le stock connu et le budget de la période sont **réservés atomiquement**, pour empêcher la survente et le contournement du budget. Des scénarios simulés (rupture, heure limite, hausse de prix, panne) sont injectables et **marqués comme simulés**.

**Spec :** `SPEC.md` §4, §5.6–5.8, §9, §10, §11, §12. Cas limites : `edge-cases.md` C, D, E, F, G2, I4, J.

**Scénario de démo réel (données vérifiées le 15/11) :** l'hôtel A demande 2 500 kg de `462545` (tomates cerises 4 kg, stock vérifié de 546 cartons, origine MA). Le substitut officiel `465239` (tomates prunes 4 kg, 306 cartons, origine TN) donne le plan suivant : 546 cartons du produit demandé, plus le complément en substitut, plus un reliquat éventuel. Résultat : `CA` + changement d'origine + escalade.

## Tâches

### T1 : fiabilité et carbone dans le catalogue, « best » complet
- `CatalogProduct` + `reliability: Decimal | None`, `carbon_kg_per_kg: Decimal | None` ; `JsonCatalog.from_files(product_json, reliability_csv=None, carbon_csv=None)`.
- `Candidate` + `reliability`, `carbon_kg_per_kg`, `is_substitute`.
- `best` = parmi les candidats qui respectent les préférences, tri lexicographique : labels demandés satisfaits (décroissant), fiabilité (décroissante, `None` = 0,9), carbone (croissant, `None` en dernier), prix.
- Tests : la fiabilité départage deux produits au même prix ; le carbone départage ensuite ; une valeur absente ne gagne jamais.

### T2 : substituts officiels, dispo partielle et plan mixte (`split`)
- Candidats : si `need.product_id` est fourni, le produit demandé + ses substituts officiels (`is_substitute=True`, `changes_vs_request` + `substitute:<id>` + l'origine si elle diffère du produit demandé).
- Stock vérifié insuffisant : le candidat est **conservé** avec `partial=True`, `qty_sales_units` = stock disponible arrondi au lot inférieur, `missing_qty` (dans l'unité demandée).
- Les niveaux good / better / best ne considèrent que les candidats complets.
- `OfferLine.split: list[Candidate]` + `backorder_qty` : si la demande porte sur un produit précis et qu'il est partiel, le plan contient le produit partiel, puis les compléments (substituts, puis autres candidats complets, du moins cher au plus cher), puis un reliquat si le complément ne suffit pas. Avec `substitution == "no_substitute"`, le plan se limite au partiel + reliquat.
- `SelectedLine.tier` accepte `"split"` ; `resolve_selection` aplatit le plan.
- Exceptions de ligne : `PARTIAL_AVAILABILITY`, `SUBSTITUTED`, `BACKORDER`.
- Tests : plan partiel + substitut + reliquat ; `no_substitute` → pas de substitut ; produit complet → pas de plan ; changement d'origine marqué.

### T3 : réponse de commande alignée sur Peppol
- `OrderResponse(code: AP|CA|RE, lines: [OrderResponseLine(line_id, status: 5|3|1|7, product_id, quantity, sales_unit, substituted_for, backorder_qty, reason)])`.
- Règles : un produit identique à la demande, complet, sans écart → ligne `5`. Un produit partiel → ligne `3` (quantité réduite). Un substitut → ligne `1` avec `substituted_for`. Une ligne sans produit → `7`. En-tête : `AP` si tout est `5`, `RE` si DENIED ou REJECTED, sinon `CA`.
- Calculée à la décision, et recalculée après une modification ou un rejet.
- Tests : `AP` nominal ; `CA` avec 3 + 1 + reliquat ; `RE` sur rejet.

### T4 : réservations (stock connu) et budget de la période, de façon atomique
- `Store` : table `reservations` ; `reserved_qty(product_id, date)` ; `reserve(org, order, items) -> list[shortages]` (tout ou rien, sous verrou) ; `set_reservation_status(order, status)` ; `committed_spend(org, since)`.
- Lookup : quantité promettable = disponible − réservé (avant l'évaluation).
- Order : réservation `HELD` au passage en `PENDING_DECISION` ; un manque → `StockChanged` (409, « relancez le lookup »). `FIRM` sur `AUTO_APPROVED` / `APPROVED` ; `RELEASED` sur `DENIED` / `REJECTED` / `EXPIRED`.
- Budget : `Mandate.period_budget_net` + `period_window` ; contexte `period_spend_net` (engagé + cette commande), calculé sous un verrou par organisation ; règle Cedar `period_budget_exceeded`.
- Anti-fractionnement : `Mandate.max_orders_per_hour` ; contexte `orders_last_hour` ; règle `order_velocity_exceeded`.
- Tests : deux organisations se disputent les 24 derniers cartons, la seconde reçoit `StockChanged` puis un lookup partiel ; une libération rend le stock disponible ; deux commandes, chacune sous le budget, déclenchent l'escalade sur la seconde ; 3 commandes dans l'heure pour un maximum de 2 → escalade.

### T5 : heure limite, injecteur de scénarios et cache amont
- Le classement reçoit `now` : `order_cutoff < now` → exclusion `CUTOFF_PASSED`.
- `ScenarioGateway(inner)` : `stock_override[pid]`, `price_increase_pct[pid]`, `outage`. Chaque réponse modifiée est marquée et `Offer.simulated` liste les scénarios actifs.
- `ShiftedClock.advance(minutes)`.
- Routes `seller_admin` (`ADMIN_KEY`) : `PUT/DELETE /admin/scenarios`, `POST /admin/clock/advance`.
- `CachingGateway(inner, availability_ttl=60 s, price_ttl=600 s)` ; en cas de panne amont, on sert le cache marqué `STALE` → règle `stale_data` → escalade.
- Tests : heure limite dépassée → exclusion ; injection de stock → partiel + offre marquée simulée ; panne + cache → `STALE` + escalade ; panne sans cache → 503.

## Jalon
- `uv run pytest` vert.
- Scénario réel des tomates : plan mixte, `CA`, escalade Telegram avec « substitut » et « origine TN » sur la carte, puis approbation.
- Course de 2 agents (organisations A et B) sur un produit au stock limité : la seconde obtient un partiel.
