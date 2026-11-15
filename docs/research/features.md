# Fonctionnalités vues par les critères du jury

Légende de priorité : **P0** obligatoire pour la démo · **P1** différenciant · **P2** si on a le temps
Chaque fonctionnalité s'appuie sur un fait vérifié dans l'API ou les données (voir `resources/NOTES.md`).

---

## 1. Démo complète de bout en bout (30 %)
*« Demande → recherche → commande ou approbation, dans l'environnement mock, pas des morceaux isolés »*

| # | Fonctionnalité | Prio |
|---|---|---|
| E1 | **Le parcours complet tourne en direct contre la vraie API mock** : demande en langage naturel → intention structurée → recherche dans le catalogue local → prix et dispo par lots → offre → évaluation du mandat → approbation automatique **ou** boîte d'approbation humaine → bon de commande → journal d'audit | P0 |
| E2 | **Un écran en 3 volets** : (1) demande de l'acheteur, (2) trace de l'agent en direct (étapes, appels API, décisions), (3) boîte d'approbation et journal. Le jury voit tout le parcours sans changer d'outil | P0 |
| E3 | **Scénarios en un clic** (lait = cas nominal, produits frais = exceptions, gros montant = escalade), avec la possibilité de saisir une demande libre | P0 |
| E4 | **Client API robuste** : maximum 8 requêtes/s, attente de 30 s sur un 429, cache prix/dispo avec horodatage, repli sur le cache (marqué « périmé ») si l'API tombe pendant la démo | P0 |
| E5 | **Même cœur exposé deux fois** : REST/OpenAPI (pour l'interface) et serveur MCP (pour que n'importe quel agent, Claude ou autre, puisse l'utiliser). On montre un agent tiers qui s'y branche | P1 |
| E6 | **Vue côté Valio** : quels agents ont commandé quoi, sous quel mandat, quelles escalades. Le brief demande un audit « pour l'acheteur et pour Valio » | P1 |

## 2. Résoudre le problème et le besoin (20 %)
*« Correspondre précisément à ce que l'acheteur a demandé, avec le moins de corrections manuelles »*

| # | Fonctionnalité | Prio |
|---|---|---|
| N1 | **Intention structurée** (`BuyerIntent`) : type de produit, quantité et unité (1 000 **L**), date limite (« lundi » → 16/11), contraintes **obligatoires** et préférences **souples**. On l'affiche à l'acheteur avec les hypothèses faites | P0 |
| N2 | **Conversion d'unités exacte** : litres → unités de vente via le prix unitaire / prix au litre de l'API et `units[]`, arrondi au lot minimum (`allowedLotSize`, 0,01 compté comme 1). Exemple : 1 000 L = 50 cartons Novobox 2×10 L | P0 |
| N3 | **Filtre d'équivalence produit** : écarter le lait de café, le lait fermenté et les laits aromatisés même s'ils sont moins chers au litre (piège réel du dataset). On combine catégorie, mentions GS1 et analyse du nom | P0 |
| N4 | **Allégations précises, pas approximatives** : `FREE_FROM_LACTOSE` ≠ `LOW_LACTOSE`. « Sans lactose » est une contrainte stricte. C'est un excellent exemple de précision pour le jury | P0 |
| N5 | **Profil acheteur** : origine préférée (FI), bio, marques, **format préféré** (une cuisine d'hôtel veut des Novobox de 10 L plutôt que 1 000 briques de 1 L), centre de coût. Il sert de valeur par défaut, donc moins de questions | P1 |
| N6 | **Optimisation des conditionnements** : mélanger les formats pour atteindre la quantité avec le minimum de surplus, de coût et de manutention | P2 |
| N7 | **Question de clarification seulement si la réponse change le résultat** (ex. % de matière grasse quand les prix diffèrent de plus de 10 %). Sinon, on applique la valeur par défaut du profil et on affiche l'hypothèse | P1 |
| N8 | **Explication du choix** : « Choisi X parce que… ; écarté Y (lait de café), Z (sans lactose non garanti) ». Les 2 ou 3 alternatives sont classées | P0 |

## 3. Autonomie et contrôles (20 %)
*« Ce que l'agent décide seul, ce qui demande une validation humaine, comment c'est journalisé et auditable »*

| # | Fonctionnalité | Prio |
|---|---|---|
| A1 | **Mandat d'achat** déclaratif, versionné et signé : plafond par commande, budget par période et par site, catégories, contraintes AP2 (`amount_range`, `budget`, `execution_date`, `allowed_merchants`) + extensions B2B (`substitution_policy`, `required_claims`, `min_reliability`, `max_unverified_value`) | P0 |
| A2 | **Moteur de règles à 3 issues** : `AUTO_APPROVE` / `NEEDS_APPROVAL(raisons)` / `DENY`. **Moteur Cedar (`cedarpy` 4.12.2)** : règles `permit`/`forbid` lisibles, montants en `decimal`. Les décisions donnent les `@id` des règles appliquées, qui servent de motifs. 3 issues obtenues avec 2 actions évaluées (`submit_order`, `auto_approve`) : refus = DENY ; `auto_approve` refusé = NEEDS_APPROVAL avec les motifs. Les totaux, l'indicateur « tout le stock est vérifié » et la valeur non vérifiée sont précalculés en Python (Cedar n'a pas de `forall`). Point de décision exposé au format **OpenID AuthZEN 1.0**. Choix justifié : c'est le moteur des garde-fous d'agents d'AWS (AgentCore Policy) | P0 |
| A3 | **Déclencheurs d'escalade réalistes** : montant au-dessus du seuil · stock inconnu (Terminal) au-dessus de X € · substitution hors préférences (changement d'origine) · prix au-dessus de l'historique ou du prix catalogue · **quantité anormale par rapport à l'habitude** (erreur de saisie : 1 000 au lieu de 100) · produit jamais commandé · heure limite de commande proche ou dépassée · coût de consigne inconnu | P0 |
| A4 | **Interface d'approbation** : approuver / modifier / rejeter avec un motif ; le devis reste bloqué jusqu'à `validUntil` (lié au `validTo` réel des prix) ; l'approbation expire | P0 |
| A5 | **Séparation des droits** : lecture (catalogue, devis) ≠ engagement (commande) ; simulation par défaut ; clé d'idempotence sur la commande | P1 |
| A6 | **Interrupteur d'arrêt et révocation du mandat** (AI Act art. 14 : annuler, arrêter) | P1 |
| A7 | **Journal d'audit à hash chaîné** : chaque événement est relié à la version du mandat, à la règle déclenchée, aux données vues (horodatage de la réponse API) et à l'humain qui a validé. **Format** : JSONL avec une enveloppe **CloudEvents 1.0.2** + JSON Schema publié. Champs repris du draft IETF *agent-audit-trail* (`action_type`, `outcome=escalated`, `prev_hash`). Hash `SHA-256(JCS RFC 8785)` chaîné + signature **JWS** par enregistrement + `verify.py`. **Récit lisible généré par gabarit** (pas par le LLM, pour rester fidèle au journal) | P0 |
| A7b | Bloc **W3C PROV-JSON** par décision (`actedOnBehalfOf`, `wasDerivedFrom`) affiché en graphe SVG (lib `prov` 3.3.0) · spans **OpenTelemetry GenAI** (`invoke_agent`/`execute_tool`, statut *Development*) vers Jaeger ou Langfuse, reliés par `traceparent` | P2 |
| A8 | **Niveaux d'autonomie par catégorie** (échelle SAP) : signaler / proposer / exécuter. Exemple : lait = exécuter, viande = proposer | P2 |

## 4. Robustesse aux exceptions (15 %)
*« Dispo partielle, substitutions, contraintes de livraison, hors cas nominal »*

| # | Fonctionnalité | Prio |
|---|---|---|
| X1 | **Dispo partielle** (produits Stock à quantité limitée) → options : quantité partielle + complément par substitut · répartition sur plusieurs produits équivalents · reliquat → selon le mandat | P0 |
| X2 | **Substitutions good / better / best** : d'abord les substitutions officielles Valio, puis même catégorie + mêmes allégations obligatoires ; classement par prix au litre ou au kg, fiabilité, labels, origine. **On signale ce que le substitut change** (origine, marque, format) | P0 |
| X3 | **Stock inconnu (999999)** : marqué `UNKNOWN_SUPPLIER_STOCK` + fiabilité historique ; jamais présenté comme « en stock » | P0 |
| X4 | **Contraintes de livraison** : heure limite de commande (`closingTime`) dépassée → prochaine date ; si elle tombe après la date voulue → escalade ou alternative en stock. `salesBlock`, `scheduleLines` vide | P0 |
| X5 | **Produit inconnu ≠ produit indisponible** : validation contre le catalogue avant l'appel API (l'API ne fait pas la différence) | P0 |
| X6 | **Devis expiré ou prix changé** → nouveau devis + nouvelle évaluation du mandat | P1 |
| X7 | **Taille de lot non entière** (1,5 / 2 / 10 kg) et **consignes sans prix** → avertissement « coût total incomplet » | P1 |
| X8 | **Injecteur de scénarios** : le mock est figé (même dispo quelle que soit la date). On simule rupture, heure limite et hausse de prix, **clairement marqués comme simulés** dans l'interface et dans les hypothèses | P1 |
| X9 | **Pannes API** : 429, timeout, 422 → reprise automatique, dégradation propre, et traçage dans l'audit | P0 |

## 5. Ouverture et chemin crédible vers la production (15 %)
*« Standards ouverts et documentés, hypothèses visibles, choix justifiés, prochaines étapes crédibles »*

| # | Fonctionnalité | Prio |
|---|---|---|
| O1 | **Spec OpenAPI 3.1 + JSON Schemas publiés** pour toutes les opérations (recherche, devis, commande, approbation, audit) | P0 |
| O2 | **Vocabulaires existants plutôt qu'un format maison** : codes GS1 (allégations, labels, allergènes, GTIN), sémantique de la réponse de commande Peppol (AP/CA/RE, lignes 1/3/5/7, ligne substituée), contraintes de mandat AP2, signature des devis en JWS | P0 |
| O3 | **Niveau d'assurance par affirmation** (prix signé, stock vérifié ou inconnu, historique observé, label auto-déclaré ou attesté, carbone = moyenne de catégorie) : c'est notre « trust protocol » | P0 |
| O4 | **`ASSUMPTIONS.md` visible** dans l'interface et le README : 999999 = inconnu, mock figé, 0,01 = 1, consignes sans prix, carbone par catégorie, attestation tierce simulée… | P0 |
| O5 | **Décisions d'architecture courtes (ADR)** pour justifier chaque choix technique (pourquoi MCP + REST, pourquoi Peppol, pourquoi tel moteur de règles, pourquoi pas de blockchain ni x402) | P1 |
| O6 | **Feuille de route vers la production** : authentification OAuth par client (prix réellement personnalisés) → export Peppol / EDI ORDERS → attestations de labels par des tiers (UNTP / European Business Wallet) → publication dans le registre MCP | P1 |
| O8 | **Architecture asynchrone et montée en charge (chemin vers la production)** : Order asynchrone (`202` + suivi par interrogation, webhook CloudEvents ou tâche MCP) ; file d'attente bornée avec `429 Retry-After` plutôt qu'un crash ; limite de débit par organisation ; **une seule porte vers l'API Valio** (régulateur ~8 req/s, pause de 30 s sur 429, regroupement des appels ≤ 1 000 produits toutes les ~50 ms, cache dispo 30–60 s / prix jusqu'à `validTo`, données `STALE` → escalade) ; **boîte d'envoi transactionnelle** pour Telegram et webhooks ; réservations atomiques (stock + budget), idempotence, compare-and-set sur `(state, version)`. **Prototype** : FastAPI asynchrone + file asyncio + SQLite WAL / Postgres. **Production** (fiche de décision + schéma) : Postgres + Redis/RabbitMQ, passerelle sans état sur plusieurs instances, régulateur amont partagé, endpoint de réservation côté Valio | P0 |
| O7 | **Découverte** : `/.well-known` (fiche d'agent, `server.json`) + workflow Arazzo | P2 |

---

## Décisions (15/11)
- **Périmètre** : on fait tout (2 développeurs, ~20 h). On construit d'abord un **fil complet très simple qui fonctionne**, puis on enrichit chaque étape, pour avoir à tout moment une démo montrable.
- **Good / better / best** (générique, validé) :
  - **good** = toutes les contraintes obligatoires, au meilleur prix ;
  - **better** = good + les préférences (origine, marque, format) ;
  - **best** = better + les préférences de qualité (labels, fiabilité, carbone).
  Chaque niveau affiche ce qu'il change par rapport à la demande.
- **Cas limites** : voir `edge-cases.md` (EC-A… à EC-J…), qui servent de base aux tests G6 et au jeu d'évaluation G5.

## Arbitrage initial (obsolète, gardé pour l'historique)
- **Tous les P0** = un parcours démontrable qui couvre les 5 critères.
- **Les P1 qui rapportent le plus de points** : E5 (MCP), N5 (profil), A5/A6, X6/X8, O5/O6.
- **Deux scénarios scénarisés** :
  1. *Lait sans lactose 1 000 L* → équivalence produit, conversion d'unités, approbation automatique (~1 010 €).
  2. *Produits frais en stock limité* → dispo partielle + substitution qui change l'origine + montant au-dessus du seuil → escalade, approbation humaine, audit.

---

## Lacunes identifiées (revue du 15/11, à intégrer)

### Principes transverses (décidés)
- **Le LLM propose, le moteur déterministe décide.** Le LLM sert uniquement à transformer la demande libre en intention structurée et à proposer des candidats. Filtres, conversions, score, devis, mandat (Cedar) et journal sont déterministes et ne dépendent d'aucune catégorie de produit. Même entrée + même mandat = même décision, rejouable.
- **Le serveur fait foi** : le devis est calculé côté passerelle à partir des réponses de l'API ; ce que l'agent déclare n'est jamais repris.
- **Multi-clients** : le numéro client est déduit de l'identification de l'agent, jamais lu dans la requête (le mock accepte n'importe quel `customer`, ce qui serait un risque d'accès aux données d'un autre client s'il était exposé). Prix nets, devis, mandats, commandes et journal sont isolés par organisation, avec les rôles agent / approbateur / Valio. La clé API Valio n'est jamais donnée aux agents.
- **Les scénarios de démo sont des cas de test**, pas des règles métier.

### Fonctionnalités manquantes
| # | Lacune | Critère | Prio |
|---|---|---|---|
| G1 | **Agent acheteur de référence séparé de la passerelle** : deux côtés distincts. Démontrer qu'un **agent tiers non modifié** (Claude Desktop ou Claude Code via MCP) utilise le même protocole, ce qui prouve qu'il ne dépend d'aucun agent en particulier | E2E, Ouverture, Impact | P0 |
| G2 | **Vérification côté acheteur** : l'agent vérifie la signature, l'expiration et le niveau d'assurance du devis, et **rejette un devis falsifié ou expiré**. Sans ce vérificateur, la « confiance » n'est pas démontrée | Trust protocol | P0 |
| G3 | **Spécification du protocole lisible et versionnée** (`SPEC.md` v0.1) : objets, machine à états, niveaux d'assurance, erreurs. C'est elle, le livrable « interface et modèle opérationnel » | Ouverture | P0 |
| G4 | **Paniers à plusieurs lignes** (« commande de la semaine : lait, beurre, œufs… ») : le mandat et les exceptions s'évaluent par ligne et sur le total | Besoin utilisateur, Exceptions | P0 |
| G5 | **Jeu d'évaluation** : 20 à 30 demandes types (FR/EN/FI) avec le résultat attendu, et un score affiché (bon produit, bonne quantité, décision correcte, nombre de corrections manuelles). Ça répond directement au critère « least manual correction » | Besoin utilisateur | P0 |
| G6 | **Tests automatisés des exceptions** (dispo partielle, heure limite, stock inconnu, produit inconnu, 429, devis expiré, falsification) lancés en direct | Exceptions, crédibilité | P1 |
| G7 | **Éditeur de mandat + simulateur « et si ? »** : un humain modifie une règle et voit l'effet sur les commandes passées. L'agent ne peut **jamais** modifier son propre mandat | Contrôles | P0 |
| G8 | **Comparaison délai de livraison et durabilité** : fiabilité, labels, carbone en **fourchette de catégorie** (objectif bonus). C'est l'une des directions optionnelles | Besoin utilisateur | P0 |
| G9 | **Origine contradictoire** : 463 produits ont un `countryOfOrigin` Valio ≠ origine fabricant Synkka (ex. chips « gb » contre NL ; serviettes « de » contre PL). On expose les deux sources et le conflit. **Exemple concret de trust protocol** sur « l'origine », explicitement citée dans le brief | Trust protocol | P0 |
| G10 | **Données manquantes signalées** : 3 068 produits sans données fabricant complètes (GTIN Synkka), 284 sans allégations, labels ni allergènes. **Une donnée absente ≠ la propriété est absente** (pas d'allergène déclaré ≠ sans allergène) → niveau d'assurance `MISSING` ; une contrainte stricte non vérifiable déclenche une escalade | Trust, sécurité | P0 |
| G11 | **Dimension multilingue** : demandes et noms produits en fi/sv/en | Besoin utilisateur | P1 |
| G12 | **Valeur pour Valio** : signaux de demande, demandes non satisfaites, ruptures vues par les agents, part des commandes automatisées. Le « pourquoi Valio l'adopterait » | Production | P0 |
| G13 | **Livrables du rendu** : repo public sous licence ouverte, README, lancement en une commande (docker compose), version hébergée, **vidéo de démo** (souvent exigée par Junction), slides. **Prévoir 3 à 4 h** | Tous | P0 |

---

## Règle d'architecture : aucun surapprentissage sur les produits
- **Aucun identifiant produit, nom ou code catégorie dans le code ni dans les règles.** Les règles portent uniquement sur des **attributs génériques** : allégations et labels GS1, unité de comparaison, niveau d'assurance, montant, quantité, date, origine, fiabilité, écart de prix.
- **Seuils et préférences = configuration** (mandat, profil acheteur), jamais des constantes dans le code.
- **Catalogue versionné** (hash du fichier dans chaque devis) : si le catalogue change, rien ne casse, la règle s'applique aux nouvelles données.
- **Tests sur des données fabriquées** (produits générés avec les propriétés voulues), pas sur des ids réels. Les chiffres observés dans le dataset (`edge-cases.md` [Données]) **justifient** un cas ; ils ne deviennent jamais une règle.
- **Le jeu d'évaluation** (G5) décrit le résultat attendu par ses **propriétés** (« sans lactose, ≥ 1 000 L, livré avant lundi »), pas par un id produit, pour qu'il reste valable si l'assortiment change.

## Nouvelles fonctionnalités : canaux et interactions
| # | Fonctionnalité | Détail | Critère | Prio |
|---|---|---|---|---|
| M1 | **Approbation via messagerie (Telegram)** | Quand l'issue est `ESCALATE`, l'approbateur reçoit un résumé (lignes, total, **motifs**, ce que change une substitution, heure limite) avec les boutons **Approuver / Rejeter / Voir le détail**. Bot API gratuite, fonctionne en *long polling*, donc sans URL publique en local. Même logique que **CIBA** (approbation découplée sur un autre appareil) | Contrôles, Démo | P0 |
| M2 | **Sécurité de l'approbation par messagerie** | Le compte de messagerie est lié à l'approbateur par un code d'appairage à usage unique. Les données du bouton sont **signées** (id du devis + hash + nonce + expiration). On affiche le hash court du devis. **Au-delà d'un second seuil, le clic dans la messagerie ne suffit pas** : lien vers la page web d'approbation (vérification renforcée). Approbation idempotente | Contrôles, Sécurité | P0 |
| M3 | **Escalade si personne ne répond** | Délai écoulé → approbateur de secours → puis expiration, avec un compte à rebours calé sur l'heure limite de commande | Contrôles, Exceptions | P1 |
| M4 | **Interrupteur d'arrêt depuis la messagerie** | `/pause` pour suspendre le mandat (interrupteur AI Act art. 14), `/resume`, `/budget` pour l'état du budget de la période | Contrôles | P1 |
| M5 | **Demande depuis la messagerie** | Le chef écrit « il me faut 20 kg de beurre pour vendredi » au bot → même chemin intention → devis → mandat. Le bot répond par le résultat ou la demande d'approbation | Besoin utilisateur, Démo | P1 |
| M6 | **Résumé quotidien** | Pour l'acheteur : commandes automatiques du jour, escalades, budget consommé. Pour Valio : demandes non satisfaites, ruptures vues par les agents | Audit, Valeur Valio | P1 |
| M7 | **Approbation avec modification dans la messagerie** | Boutons « ×½ », « retirer la ligne », « accepter sans le substitut » → nouveau devis + **nouvelle évaluation du mandat** (EC-H2) | Contrôles | P2 |
| M8 | **Webhooks d'événements au format CloudEvents** | Le système de l'acheteur (ERP) s'abonne : `quote.created`, `order.escalated`, `order.approved`… Signature HMAC. C'est le **pont ouvert vers n'importe quel outil** (Slack, Teams, e-mail, ERP) sans le coder nous-mêmes | Ouverture, Production | P1 |
| M9 | **Export de la commande** | JSON du protocole → **UBL / Peppol Order** (XML) + bon de commande PDF lisible, pour montrer le chemin vers l'ERP et la facturation | Ouverture, Production | P1 |
| M10 | **Commandes récurrentes / niveaux de stock cible** | « Maintenir 200 L de lait » → l'agent propose un réassort chaque semaine, dans le mandat | Besoin utilisateur | P2 |
| M11 | **Alerte d'expiration** | Devis en attente qui va expirer, prix qui expire, heure limite qui approche → relance de l'approbateur | Exceptions | P1 |
| M12 | **Commande « pourquoi ? »** | `/why <commande>` → récit de l'audit (même gabarit que la vue web) | Audit, explicabilité | P1 |

**Pourquoi Telegram plutôt que WhatsApp** : l'API WhatsApp Business exige un compte Meta Business, un numéro vérifié et des **modèles de messages pré-approuvés** pour tout message envoyé à l'initiative de l'entreprise. C'est trop risqué en 20 h. Le canal est derrière une **interface `Notifier`** : WhatsApp, Slack, Teams ou e-mail s'ajoutent sans toucher au cœur (feuille de route). Les webhooks CloudEvents (M8) couvrent tous les autres outils.

---

## Alignement sur le flux imposé par Valio (« The flow your solution must run »)
**1 Request → 2 Lookup → 3 Order → 4 Approval.** Le protocole, l'OpenAPI, les outils MCP, l'interface (indicateur de progression) et le journal suivent **exactement** ce découpage et ces noms.

| Étape Valio | Notre opération | Contenu |
|---|---|---|
| (0, côté acheteur, hors protocole) | `interpret` | Langage libre (interface / Telegram) → `BuyerIntent` par le LLM |
| **1 Request** | `POST /requests` | L'**agent** envoie une demande structurée : lignes (besoin par propriétés), quantités et unités, date voulue, contraintes obligatoires et préférences, référence du mandat |
| **2 Lookup** | `POST /requests/{id}/lookup` | Candidats + prix + dispo + niveaux d'assurance + good / better / best ; **exceptions ici** : dispo partielle, rupture, substitution, stock inconnu, données manquantes |
| **3 Order** | `POST /orders` | Commande à **prix bloqué** qui référence l'offre signée (`offer_hash`, `validUntil`) → statut `PENDING_DECISION` ; **exceptions ici** : offre expirée, prix ou dispo changés, heure limite |
| **4 Approval** | `POST /orders/{id}/decision` (puis `/approve`, `/reject`) | **L'agent décide dans son mandat** (Cedar) → `AUTO_APPROVED` ; sinon `PENDING_HUMAN` → Telegram / web → `APPROVED` / `REJECTED` ; `DENIED` hors mandat. **La passerelle revérifie la même règle** (double vérification : un agent compromis ne peut rien imposer) |

Chaque événement d'audit porte `step: request|lookup|order|approval`.
