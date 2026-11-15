# Brainstorm des fonctionnalités : convergence (15/11)

**Question de départ** : *Comment pourrions-nous faire qu'un jury Valio, en 5 minutes de démo, **voie** qu'un agent externe achète précisément, en sécurité, en s'adaptant aux imprévus, sur un protocole ouvert qu'il pourrait mettre en production ?*
**Critère** : points sur la grille du jury × faisabilité à 2 en ~20 h.
**Sources** : 4 recherches par sous-agents (précision et évaluations, approbation humaine, exceptions et substitutions, conformité du protocole et démo). Les références sont dans les sections « Preuve existante ».

---

## Thème 1 : Mesurer et prouver la précision (critère besoin acheteur, 20 %)
| Idée | Preuve existante | Effort |
|---|---|---|
| **Jeu d'évaluation « gold »** : 30 à 50 demandes en fr/en/fi, résultat attendu décrit par **propriétés**, chaque candidat annoté Exact / Substitut / Non pertinent | Amazon ESCI (E/S/C/I), WebShop (score par attributs) | 3 h |
| **Indicateurs affichés** : *first-time-right* (part des lignes acceptées sans modification), *touchless rate* (part des commandes validées sans aucune correction), **pass^k** (constance sur k essais), violation d'une contrainte obligatoire = 0 | τ-bench (pass^k), indicateurs d'achats (touchless 30–80 %, > 85 % pour les meilleurs) | 1 h |
| **Liste habituelle du client** (*order guide*) comme repère pour choisir le produit : les produits habituels sont favorisés et distingués des achats ponctuels | Pepper, Choco : principal facteur de précision cité | 2 h |
| **Fiche normalisée par produit extraite hors ligne par le LLM** (% de matière grasse, volume, format, allégations), avec contrôle de cohérence via le prix par unité de l'API | ExtractGPT (LLM > modèles classiques de ~5 points de F1) | 3–4 h |
| **Recherche hybride** : recherche par mots-clés (BM25) sur les noms fi/sv/en ramenés à leur forme de base + recherche sémantique multilingue, fusion des classements, puis **filtres obligatoires**, puis LLM-juge sur les 20 premiers avec justification attribut par attribut | Peeters & Bizer (LLM comme juge de correspondance), pyvoikko (finnois) | 3–4 h |
| **Une seule question, sur l'attribut qui sépare le plus les candidats**, uniquement si elle change le prix ou la conformité | ProductAgent, SAGE (valeur de l'information) | 2 h |
| Acheteur simulé par LLM pour tester automatiquement les échanges | τ-bench, PROCLARE | 2 h |

## Thème 2 : Approbation humaine qui ne devient pas un tampon (critère contrôles, 20 %)
| Idée | Preuve existante | Effort |
|---|---|---|
| **Carte d'approbation sans plaidoyer** : action brute + **règle Cedar qui a déclenché la demande** + **écart par rapport à l'habitude** (« +240 % par rapport à la médiane ») + score de risque (réversibilité × montant × nouveauté) ; la justification du LLM est repliée | OWASP Agentic Top 10 (risque d'exploitation de la confiance humaine envers l'agent) ; Anthropic : **93 % des demandes de permission sont acceptées**, donc approbation de façade | 3 h |
| **Approuver / modifier / rejeter avec motif renvoyé à l'agent** ; l'agent retente avec le motif ; escalade après 3 refus | LangGraph human-in-the-loop, OpenAI Agents SDK, Claude Code auto mode | inclus |
| **Délai dépassé = refus par défaut** + approbateur suppléant (matrice de délégation : rôle × seuil × suppléant) | Microsoft Agent Governance Toolkit, Temporal | 2 h |
| **Anti-fractionnement + coupe-circuit sur la vitesse** : cumul glissant 24 h / 7 j par catégorie, nombre de commandes par heure → règle Cedar ; `/stop` sur Telegram et **seul un humain relance** | Fractionnement d'achats (*split purchasing*), un signal de fraude classique en achats ; disjoncteurs de dépense pour agents | 3 h |
| **Telegram durci** : données des boutons = id opaque + nonce + expiration ; vérification que **celui qui clique** est un approbateur autorisé ; un second clic est sans effet ; au-delà de X €, vérification renforcée via mini-app Telegram (`initData` signé en HMAC) | **CVE-2026-53807** : contournement d'autorisation sur des boutons d'approbation Telegram | 2–3 h |
| **« Vous approuvez toujours X » → proposition d'élargir le mandat** sous forme de diff Cedar, **elle-même soumise à approbation humaine** ; dans l'autre sens, le mandat se resserre après un incident | Aucun produit ne le fait (constat de la recherche) → **différenciant** | 3 h |
| **Tableau de bord de la qualité de supervision** : taux d'approbation, temps avant clic ; alerte si l'on approche 100 % / 0 s ; **demande piège** occasionnelle, marquée comme test dans le journal | AI Act art. 14 (sur-confiance), pratiques anti-fatigue | 2 h |
| **Niveaux d'autonomie** (Knight Institute L1–L5 ; notre agent = **L4 « Approver »**) + **mode fantôme** (l'agent propose, on compare à la décision humaine) + critères de promotion affichés | Feng et al. 2025, Montecarlo, Anthropic (l'auto-approbation passe de ~20 % à plus de 40 % avec l'expérience) | 2 h |
| Mandat versionné et haché à la manière d'AP2 : décision autonome = « humain absent mais pré-autorisé » ; escalade = « humain présent » | AP2, Stripe Issuing (plafonds cumulables par jour, semaine, mois) | 2 h |

## Thème 3 : Exceptions et substitutions (critère robustesse, 15 %)
| Idée | Preuve existante | Effort |
|---|---|---|
| **Préférence de substitution par ligne + valeur par défaut globale** : `best_match` / `specific:<id>` / `no_substitute` ; on ne demande **que pour les lignes à risque** | Instacart, Walmart ; Baymard : 76 % des utilisateurs testés peinent quand on leur demande tout à l'avance | 2 h |
| **Réponse de commande alignée sur Peppol** : statut de commande (accepté / accepté avec modifications / rejeté) + statut de ligne (5 / 3 / 7) + produit de substitution + quantité livrée plus tard (`backorder_qty`, 0 = jamais) + motif inspiré d'EDIFACT (indisponible temporairement / partiel avec reliquat / partiel sans reliquat) | Peppol BIS OrderResponse, EDIFACT DESADV et EANCOM | 3 h |
| **Classement good / better / best** : filtres obligatoires (substitutions officielles en priorité, mêmes allégations, prix dans ±50 %) puis score pondéré (format, marque, origine, prix, fiabilité, **déjà acheté** = bonus) | Instacart (écart de format, marque) ; Hoang & Breugelmans (acceptation 66 % → 75 %, même marque ou même saveur selon la catégorie) | 4 h |
| **Apprentissage des acceptations** : score = w·heuristique + (1−w)·taux d'acceptation de la paire chez ce client ; w diminue avec le nombre d'observations | Instacart (le poids de l'historique sature vers ~400 essais) | 2 h |
| **Probabilité de succès d'une ligne** = P(disponible) × fiabilité historique ; sous un seuil sur un article critique → commande de secours ou marge (logique du stock de sécurité) | Calcul classique du stock de sécurité, suivi des fournisseurs (OTIF) | 3 h |
| **Un seul message d'exception actionnable** (lignes touchées, motif codé, options en un clic) | e-mail d'exception d'US Foods MOXē | 2 h |
| **Indicateurs de commande** : taux de commandes complètes, taux de remplissage, livraison complète et à l'heure prévue (OTIF) | Instacart, OTIF foodservice 95–98 % | 1 h |
| Heure limite → créneau suivant / substitut disponible avant l'heure limite / livraison en deux fois, avec compte à rebours | Metro, Bidfood | 2 h |

## Thème 4 : Ouverture et crédibilité production (critère ouverture, 15 %)
| Idée | Preuve existante | Effort |
|---|---|---|
| **Kit de conformité** en tests automatisés (pytest) : exigences MUST / SHOULD / MAY, tests sautés selon les capacités déclarées, rapport `compatibility.json` + HTML ; « n'importe quel grossiste lance le kit contre son serveur pour se certifier » | Kits officiels A2A et UCP, Testbed Peppol | 4 h |
| **Tests générés depuis l'OpenAPI** (Schemathesis) + **outils officiels MCP** (`@modelcontextprotocol/conformance`, Inspector) avec badges dans le README | Outils officiels | 1,5 h |
| **Démo red-team « produit piégé »** : une description catalogue contient une injection ; défenses montrées : texte marqué `untrusted_text`, plafond du mandat, approbation | Magentic Marketplace (Microsoft), AgentDojo, OWASP Agentic Top 10 | 3 h |
| **Deux agents acheteurs hétérogènes** (Claude via MCP + script ou autre framework via REST) sur la même passerelle | Codelab A2A « Purchasing Concierge » | 2–3 h |
| **Score d'aptitude aux agents de Valio** : scanner inspiré de Cloudflare « Is it agent ready? » + qualité des données (conflits d'origine, champs manquants), noté de A à F | Cloudflare (04/2026), UCP Score | 2–3 h |
| **Fiches de décision (ADR)** au format MADR + `ASSUMPTIONS.md` + spec versionnée par date + journal des changements + processus d'évolution inspiré des SEP de MCP + détection des changements cassants (`oasdiff`) en intégration continue | Spec ACP datée, gouvernance MCP | 2 h |
| Serveur mock public (Prism) + workflow **Arazzo** request → lookup → order → approval | OpenAPI Initiative | 1,5 h |
| Devis signé → approbation qui reprend exactement ce devis (comme le « cart mandate » d'AP2) → commande, le tout chaîné dans le journal | AP2 | inclus |

## Thème 5 : Démo et expérience (critère démo de bout en bout, 30 %)
Mode démo rejouable avec cache préchargé · indicateur de progression des 4 étapes de Valio · tableau de bord en direct des commandes en cours · demande vocale Telegram · récit adapté par rôle (chef / finance / auditeur) · reçu vérifiable hors ligne (QR code) · **changement du catalogue en direct** pour prouver l'absence de surapprentissage.

---

## Matrice impact × effort
| | **Effort faible (≤ 2 h)** | **Effort élevé (≥ 3 h)** |
|---|---|---|
| **Impact fort** | *Gains rapides* : indicateurs (touchless, first-time-right, pass^k) · liste habituelle · préférence de substitution par ligne · refus par défaut au délai · Telegram durci · conformité MCP officielle + Schemathesis · ADR / hypothèses · indicateurs de commande · message d'exception unique | *Gros paris* : jeu d'évaluation gold · réponse de commande Peppol · classement good / better / best · carte d'approbation sans plaidoyer · anti-fractionnement + coupe-circuit · kit de conformité · red-team produit piégé · deux agents hétérogènes |
| **Impact moyen** | Arazzo + Prism · niveaux d'autonomie affichés · alerte de délai | Élargissement du mandat suggéré · apprentissage des acceptations · probabilité de succès · score d'aptitude aux agents · tableau de supervision |
| **Impact faible** | Demande vocale · QR code | Acheteur simulé par LLM · recherche hybride complète (on peut démarrer avec mots-clés + LLM-juge) |

## ⚠️ Réalité du budget
L'addition des estimations dépasse **~90 h**, pour un budget de **~20 h à deux** (~40 h-personne, dont 3–4 h de rendu). « Tout faire » est impossible. On doit **choisir ~25–30 h de fonctionnalités** au-delà du fil complet.

## Recommandation (top par critère)
1. **Démo de bout en bout (30 %)** : fil complet des 4 étapes + mode démo rejouable + **deux agents hétérogènes**.
2. **Besoin acheteur (20 %)** : **jeu d'évaluation gold + indicateurs** (touchless, first-time-right) + liste habituelle.
3. **Contrôles (20 %)** : **carte d'approbation sans plaidoyer** (règle déclenchée + écart à l'habitude) + Telegram durci + anti-fractionnement / coupe-circuit + refus par défaut au délai. Bonus différenciant : **élargissement du mandat suggéré**.
4. **Exceptions (15 %)** : **réponse de commande Peppol** + good / better / best + préférence de substitution par ligne + message d'exception unique.
5. **Ouverture (15 %)** : **kit de conformité** + outils officiels MCP + ADR / hypothèses + **red-team produit piégé**.

## Hypothèses à vérifier
- Code Peppol « accepté avec modifications » : `CA` (règles T116, source lue au premier tour) ou `AC` (second tour) → **relire la liste de codes UNCL4343 avant d'écrire la spec**.
- Le filtre de prix ±50 % pour les substituts vient d'une source non vérifiée → à présenter comme un paramètre réglable, pas comme un fait.
- Les chiffres de fatigue d'approbation autres que les 93 % d'Anthropic viennent de blogs secondaires.
