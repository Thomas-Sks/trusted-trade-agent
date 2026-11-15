# TTAP Phase 2 : approbation humaine et journal d'audit — plan d'implémentation

**Objectif :** une commande `PENDING_HUMAN` produit une **carte d'approbation factuelle** (règles déclenchées + écart à l'habitude + alertes d'assurance), envoyée sur **Telegram** à un approbateur appairé. Elle est **approuvée, modifiée ou rejetée** de façon sûre (compare-and-set, jetons à usage unique, vérification de qui clique), **expire en refus par défaut**, et chaque étape est inscrite dans un **journal chaîné et signé** vérifiable par `scripts/verify_audit.py`.

**Spec :** `SPEC.md` §6, §8, §13. Plan maître : phase 2.

**Contraintes héritées :** celles de la phase 1, plus :
- Le texte des explications vient de **gabarits** (`ttap/domain/explain.py`), jamais du LLM.
- Telegram est optionnel : sans `TELEGRAM_BOT_TOKEN`, le notifieur devient `LoggingNotifier` et tout le reste fonctionne (REST).
- La clé de signature est persistée (`TTAP_SIGNING_KEY`, par défaut `ttap_signing_key.json`, ignorée par git), pour que les offres et le journal restent vérifiables après un redémarrage.
- `AUTO_APPROVED` et `APPROVED` sont les états terminaux « prêt à transmettre ». `CONFIRMED` est réservé à la transmission réelle vers l'ERP, qui fait partie de la feuille de route.

## Tâches

### T1 : modèles et persistance de la clé
- `models.py` :
  - `UsualItem(product_id, median_qty)` ;
  - `Mandate` + `approval_timeout: timedelta = 2h`, `step_up_above_net: Decimal = 5000`, `usual_list: list[UsualItem] = []` ;
  - `Order` + `decided_at`, `approved_by`, `rejection_reason`, `mandate_version` ;
  - `AuditEvent` (enveloppe CloudEvents 1.0 + `org_id`, `step`, `actor`, `outcome`, `data`, `explanation`, `prev_hash`, `hash`, `signature`) ;
  - `ApprovalCard` / `CardLine`.
- `EcdsaSigner.load_or_create(path)` + `EcdsaSigner.verify_with_jwk(jwk, payload, token)`.
- Tests : la clé est rechargée identique (une signature reste vérifiable avec la nouvelle instance) ; vérification avec la seule clé publique JWK.

### T2 : explications par gabarit
- `ttap/domain/explain.py` : `RULE_TEXT` (un gabarit par `@id` Cedar) ; `explain_rules(rules, context) -> list[str]` ; `explain_decision(order) -> str` ; `explain_offer(offer) -> str`.
- Tests : `total_over_order_limit` → « Total 3030.00 € HT > plafond par commande 2000 € » ; règle inconnue → texte générique contenant l'id (jamais d'exception).

### T3 : carte d'approbation
- `ttap/domain/approval_card.py` : `build_card(order, offer, mandate, now) -> ApprovalCard` ; `render_card_text(card) -> str`.
- Écart à l'habitude : quantité / `median_qty` ≥ 1,5 ou ≤ 0,5 → « ×3.0 vs habitude » ; produit absent d'une `usual_list` non vide → « nouveau produit ».
- Alertes : stock fournisseur non vérifié (montant), origine contradictoire (sources), écarts `changes_vs_request`.
- `step_up_required = total_net > mandate.step_up_above_net` ; minutes avant l'heure limite (la plus proche des lignes sélectionnées).
- Tests : volume ×3, nouveau produit, alerte de stock non vérifié, vérification renforcée au-delà du seuil, et rendu qui contient « Bloqué par » plus chaque motif.

### T4 : journal d'audit chaîné et signé
- `ttap/adapters/outbound/jsonl_audit.py` : `JsonlAuditLog(path, signer)` avec `append(event) -> AuditEvent` (calcule `prev_hash` par organisation, `hash = sha256(JCS(event sans hash/signature))`, signe `{"hash": …}`), `list(org_id=None)`, chaîne relue au démarrage.
- `ttap/domain/audit_verify.py` : `verify_chain(events, jwk) -> list[str]` (problèmes : hash recalculé ≠, prev_hash ≠, signature invalide).
- `scripts/verify_audit.py <fichier.jsonl> <jwk.json>`.
- Tests : chaîne de 3 événements valide ; modification d'un champ détectée ; suppression d'une ligne détectée ; deux organisations ont deux chaînes indépendantes ; un redémarrage poursuit la chaîne.

### T5 : émission d'audit dans les cas d'usage
- `RequestService`, `LookupService`, `OrderService` reçoivent `audit: AuditLog`. Événements : `request.created`, `lookup.offer_issued`, `order.created`, `order.decided` (règles, contexte, explication).
- Tests : un parcours nominal produit 4 événements dans l'ordre, avec les bons `step` ; l'explication de la décision cite les motifs.

### T6 : service d'approbation (compare-and-set, refus par défaut)
- `ttap/application/approvals.py` : `ApprovalService(store, policy, mandates, clock, audit, notifier)` avec :
  - `approve(org, order_id, approver, expected_version=None)` → `APPROVED` ;
  - `reject(org, order_id, approver, reason, expected_version=None)` → `REJECTED` ;
  - `modify(org, order_id, approver, selected, expected_version=None)` → nouvelle évaluation (`AUTO_APPROVED` → `APPROVED` par l'approbateur ; `PENDING_HUMAN` → reste en attente avec une nouvelle version et une nouvelle carte ; `DENIED`) ;
  - `card(org, order_id)` ; `pending(org)` ; `async escalate(order)` (construit la carte et notifie) ; `expire_due() -> list[Order]` (`PENDING_HUMAN` au-delà de `approval_timeout` → `EXPIRED`).
- Erreurs : `Conflict` (409) si l'état ou la version ne correspond pas ; `OfferExpired` si l'offre est expirée au moment d'approuver.
- `Store` + `list_orders_by_state(state)`.
- Tests : approbation nominale ; double approbation → `Conflict` ; mauvaise version → `Conflict` ; offre expirée → `OfferExpired` ; rejet avec motif ; modification qui repasse dans le mandat → `APPROVED` ; délai dépassé → `EXPIRED` ; chaque action est dans le journal.

### T7 : logique Telegram (pure) + adaptateur python-telegram-bot
- `Store` + `link_approver(telegram_id, org, user)`, `approver_by_telegram(telegram_id)`, `approver_chats(org)`, `save_action_token(...)`, `consume_action_token(token_id)` (atomique, à usage unique, expiration).
- `ttap/adapters/inbound/telegram_logic.py` : `ApprovalBotLogic(store, approvals, pairing_codes, clock, new_id)` avec `link(telegram_id, code) -> str` ; `buttons(order, card, chat) -> list[tuple[str, str | None, str | None]]` ; `async handle(telegram_id, data) -> str`. Contrôles : jeton existant, non expiré, non utilisé ; **l'utilisateur qui clique est un approbateur appairé de l'organisation de la commande** ; si une vérification renforcée est requise, le bouton Approuver est remplacé par un lien vers la page web.
- `ttap/adapters/outbound/telegram_notifier.py` : `TelegramNotifier(bot_logic, token)` qui implémente `Notifier` (envoie la carte + le clavier), plus `start()` / `stop()` (polling dans la boucle asyncio de FastAPI). `LoggingNotifier` de repli.
- Tests (sans réseau) : appairage OK ou code inconnu ; clic d'un inconnu → refusé ; clic d'un approbateur d'une autre organisation → refusé ; jeton réutilisé → refusé ; jeton expiré → refusé ; approbation par clic → `APPROVED` ; vérification renforcée → aucun bouton d'approbation en `callback`.

### T8 : REST approbateur, audit et cycle de vie
- `APPROVER_KEYS=key:org:user`. Routes :
  - `GET /approvals` ;
  - `GET /orders/{id}/card` ;
  - `POST /orders/{id}/approve | reject | modify` (corps : `expected_version`, `reason`, `selected`) ;
  - `GET /audit` (chaîne de l'organisation) ;
  - `GET /audit/verify`.
- Une clé d'agent ne peut pas approuver (401).
- `POST /orders` appelle `escalate` si `PENDING_HUMAN`.
- Cycle de vie FastAPI : tâche d'expiration toutes les 30 s ; démarrage et arrêt du bot Telegram si un jeton est présent.
- Tests : parcours agent → escalade → approbation par l'approbateur → `APPROVED` ; une clé d'agent sur `/approve` → 401 ; `/audit/verify` → valide.

## Jalon
- `uv run pytest` au vert.
- Avec un jeton Telegram : commande de 3 000 L → carte reçue sur le téléphone → clic sur Approuver → `APPROVED` → `scripts/verify_audit.py` → « chain valid ».
