# TTAP : plan maître d'implémentation (20 h, 2 développeurs)

> **Pour les agents qui exécutent :** chaque phase a (ou aura) son plan détaillé dans ce dossier. Seule la **phase 1** est détaillée maintenant (`2026-11-15-ttap-phase1-walking-skeleton.md`). Les phases 2 à 7 seront écrites juste avant d'être exécutées, à partir des interfaces réellement produites, pour éviter un plan qui dérive du code.

**Objectif :** prototype de démo du *Trusted Trade Agent Protocol* : un agent d'achat externe déroule `Request → Lookup → Order → Approval` contre l'API mock Valio Aimo, avec des offres signées, un mandat évalué par Cedar, une approbation humaine via Telegram et un journal d'audit vérifiable.

**Architecture :** hexagonale légère, en un seul processus Python. Le domaine est pur (aucune I/O). Les cas d'usage n'utilisent que des ports (`typing.Protocol`). Les adaptateurs d'entrée (REST, MCP, bot Telegram) et de sortie (API Valio, Cedar, SQLite, Telegram, JWS, LLM, horloge) sont assemblés dans `bootstrap.py`. L'agent acheteur de référence est **hors** de l'hexagone : c'est un simple client du protocole.

**Stack (versions PyPI au 15/11/2026) :** Python 3.12 · fastapi 0.163 · uvicorn 0.54 · pydantic 2.14 · httpx 0.28 · cedarpy 4.12.2 · joserfc 1.8 · rfc8785 0.1.4 · pycountry · python-telegram-bot 22.8 · mcp 2.3 · anthropic 2.8 · jinja2 3.1 · pytest 9.2 · pytest-asyncio 1.5 · respx 0.23 · schemathesis 4.33. Gestionnaire de paquets : `uv`.

**Spec :** `SPEC.md` (v0.1). Les compléments sont dans `features.md`, `edge-cases.md` et `brainstorm.md`.

## Contraintes globales (valables pour toutes les tâches)
- **Aucun identifiant produit, nom ou code catégorie dans le code ni dans les règles** (SPEC §0.3). Les tests utilisent des **produits fabriqués**.
- **Le LLM ne décide jamais.** Il est confiné à l'adaptateur `Interpreter` (étape 0) et au classement optionnel. Tout le reste est déterministe.
- **Montants en `Decimal`**, jamais en `float` (le `float` n'est toléré que pour `score`).
- **`org_id` est toujours déduit de l'identifiant de l'appelant**, jamais lu dans le corps de la requête.
- **La clé API Valio vient de la variable d'environnement `VALIO_API_KEY`.** Jamais dans le code, jamais commitée.
- **Appels amont : ≤ 8 req/s, pause de 30 s sur un 429, ≤ 1 000 produits par appel.**
- **Horloge de démo par défaut : `2026-11-12T08:00:00+02:00`** (Europe/Helsinki), qui rend cohérentes les heures limites figées du mock. Hypothèse documentée dans `ASSUMPTIONS.md`.
- **Fuseau** : stockage en datetime avec fuseau. Affichage en Europe/Helsinki.
- **Langue du code** : anglais. Documents et messages de l'interface : fr/en.

---

## Structure des fichiers (cible)
```
pyproject.toml  .env.example  ASSUMPTIONS.md  README.md  docker-compose.yml
policies/base.cedar
ttap/
  ports.py
  bootstrap.py
  domain/   models.py quantities.py assurance.py ranking.py offer.py decision.py
            order_state.py approval_card.py reservations.py usual.py
  application/ requests.py lookup.py orders.py approvals.py mandates.py audit.py errors.py
  adapters/inbound/  rest_api.py mcp_server.py telegram_bot.py web_ui.py
  adapters/outbound/ catalog_json.py valio_gateway.py scenario_injector.py cedar_engine.py
                     sqlite_store.py memory_mandates.py telegram_notifier.py jsonl_audit.py
                     jws_signer.py claude_interpreter.py clocks.py
buyer_agent/   reference_agent.py  script_agent.py
conformance/   test_must.py test_should.py conftest.py
eval/          cases.yaml run_eval.py
scripts/       smoke_milk.py verify_audit.py
tests/         (miroir de ttap/)
docs/adr/      0001-hexagonal.md 0002-cedar.md …
```

## Ports (contrat partagé : à figer ensemble à H0)
```python
class CatalogRepository(Protocol):
    @property
    def version(self) -> str: ...
    def get(self, product_id: str) -> CatalogProduct | None: ...
    def search(self, text: str, limit: int = 200) -> list[CatalogProduct]: ...

class SupplierGateway(Protocol):
    async def prices(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamPrice]: ...
    async def availability(self, product_ids: list[str], delivery: date) -> dict[str, UpstreamAvailability]: ...

class PolicyEngine(Protocol):
    def decide(self, context: dict) -> Decision: ...

class Signer(Protocol):
    def sign(self, payload: dict) -> str: ...
    def verify(self, payload: dict, token: str) -> bool: ...
    def public_jwk(self) -> dict: ...

class Clock(Protocol):
    def now(self) -> datetime: ...

class MandateRepository(Protocol):
    def get(self, org_id: str) -> Mandate | None: ...

class Store(Protocol):            # requests, offers, orders ; transactions atomiques
    def save_request(self, req: PurchaseRequest) -> None: ...
    def get_request(self, org_id: str, request_id: str) -> PurchaseRequest | None: ...
    def save_offer(self, offer: Offer) -> None: ...
    def get_offer(self, org_id: str, offer_id: str) -> Offer | None: ...
    def claim_offer(self, org_id: str, offer_id: str) -> bool: ...
    def insert_order(self, order: Order) -> None: ...
    def get_order(self, org_id: str, order_id: str) -> Order | None: ...
    def get_order_by_idempotency_key(self, org_id: str, key: str) -> Order | None: ...
    def transition(self, org_id: str, order_id: str, expected_state: OrderState,
                   expected_version: int, updated: Order) -> bool: ...

# Phase 2+
class AuditLog(Protocol):
    def append(self, event: AuditEvent) -> AuditEvent: ...
class Notifier(Protocol):
    async def request_approval(self, order: Order, card: ApprovalCard) -> None: ...
class Interpreter(Protocol):
    async def interpret(self, text: str, profile: BuyerProfile) -> PurchaseRequest: ...
```

---

## Phases, jalons et répartition
**A** = toi · **C** = Claude. Les deux codent ; C écrit la majorité du code, A relit, lance, teste en vrai et pilote les parties qui demandent des comptes ou de l'humain (Telegram, démo, pitch, stand Valio).

| Phase | Créneau | Contenu | Qui | Jalon à valider (sinon on ne passe pas à la suite) |
|---|---|---|---|---|
| **0 Cadrage** | H0–H0:45 | `git init`, `uv`, ports et modèles relus **ensemble**, `.env`, création du bot Telegram (BotFather) | A+C | `pytest` vert sur les modèles ; bot Telegram créé |
| **1 Fil complet** | H0:45–H5 | Catalogue → passerelle Valio → lookup (filtres obligatoires, quantités, good / better / best simple) → offre signée → commande → décision Cedar à 3 issues → API REST → test de fumée réel sur le lait | C (code) / A (relecture, test réel) | **`scripts/smoke_milk.py` donne AUTO_APPROVED sur l'API réelle** ; une commande à plus de 2 000 € donne PENDING_HUMAN |
| **2 Humain et audit** | H5–H8 | approve / reject / modify (compare-and-set, nouvelle évaluation) · carte d'approbation (règles + écart à l'habitude) · Telegram (appairage, boutons signés, vérification de qui clique, lien de vérification renforcée) · délai → secours → EXPIRED · journal JSONL CloudEvents chaîné + `verify_audit.py` · boîte d'envoi | C : cœur + audit ; A : bot Telegram de bout en bout | Escalade reçue sur le téléphone, approbation → CONFIRMED, chaîne vérifiée |
| **3 Exceptions et concurrence** | H8–H11 | Registre de réservations (stock + budget, atomique) · dispo partielle (partiel + substitut / répartition / reliquat) · substitutions officielles + good / better / best complet (fiabilité, carbone) · préférence de substitution par ligne · horloge et heure limite · injecteur de scénarios · cache, regroupement, données périmées · réponse de commande Peppol (`AP` / `CA` / `RE`) | C | Scénario « produits frais » : CA + substitut + escalade ; course de 2 agents sur les 24 derniers cartons |
| **4 Agents et canaux** | H11–H14 | `Interpreter` Claude (étape 0) · serveur MCP · agent de référence (Claude via MCP) · 2ᵉ agent différent (script REST) · **interface web en 3 volets** (Jinja + htmx, indicateur des 4 étapes, flux d'audit en direct, boîte d'approbation) · demande via Telegram | C : MCP / agents ; A : interface web | Démo complète jouable depuis l'interface et Telegram |
| **5 Précision et sécurité** | H14–H16 | Liste habituelle (repère) · jeu d'évaluation (30 cas, fr/en/fi) + indicateurs touchless / first-time-right / pass^k · produit piégé (`untrusted_text`) · anti-fractionnement et vitesse · `/pause` · 2 organisations (isolation) | C : évaluation / règles ; A : rédaction des cas d'évaluation | Tableau des indicateurs affiché ; red-team refusé en direct |
| **6 Ouverture** | H16–H17:30 | Export OpenAPI · kit de conformité pytest MUST / SHOULD · conformité MCP officielle + Schemathesis · ADR · `ASSUMPTIONS.md` · docker compose · déploiement | C : kit / ADR ; A : déploiement | `docker compose up` ; rapport de conformité vert |
| **7 Rendu** | H17:30–H20 | **Gel des fonctionnalités à H17:30.** Mode démo rejouable · script de démo répété 3 fois · vidéo · slides · README | A (pitch / vidéo) + C (slides / README) | Vidéo envoyée |

**Règle de coupe en cas de retard** (on coupe dans cet ordre) : demande via Telegram → 2ᵉ agent différent → Schemathesis → répartition sur plusieurs produits → pass^k → vérification renforcée par mini-app Telegram (repli : lien web signé) → élargissement du mandat suggéré (n'est pas dans le plan de base).
**On ne coupe jamais** : le fil complet, l'escalade Telegram, le journal vérifiable, la dispo partielle + substitution, la spec + les hypothèses, la vidéo.

## Scénarios de démo (tests d'acceptation finaux)
1. **Nominal** : « 1 000 L de lait sans lactose pour lundi » (hôtel A) → offre signée → AUTO_APPROVED → CONFIRMED → journal.
2. **Exceptions** : panier de produits frais (hôtel A) → dispo partielle + substitut qui change l'origine + total > plafond → PENDING_HUMAN → carte Telegram → l'approbateur modifie → nouvelle évaluation → APPROVED → réponse `CA`.
3. **Sécurité** : l'agent du restaurant B tente de lire la commande de A (404) ; offre falsifiée (rejetée) ; produit piégé (sans effet) ; 3 commandes à 1 900 € en une heure (anti-fractionnement → escalade).
4. **Concurrence** : A et B veulent les 24 derniers cartons → l'un obtient 24, l'autre une dispo partielle + good / better / best.
