# Ressources Valio Aimo – notes d'exploration (2026-11-14)

Portail : https://junction26.valioaimo.fi/ (mdp événement `<event password>`)
API : header `X-API-Key`, base `https://junction26.valioaimo.fi/api`

## Fichiers
| Fichier | Contenu |
|---|---|
| `valio_aimo_junction26_product_data.json` (87 Mo) | 17 546 produits, 349 catégories (codes sans nom) |
| `valio_aimo_junction26_product_data_schema.json` | JSON Schema du catalogue |
| `valio_aimo_junction26_delivery_reliability.csv` | 4 425 produits, `deliveryReliability` 0–1 (médiane 1.0, 291 < 0.9) |
| `valio_aimo_junction26_carbon_footprint.csv` | 11 033 produits, `AVG kg CO2-eq/kg` (moyenne du groupe produit) |
| `openapi.json` | Spec des API mock |

## Clarifications d'un dev Valio (confirmées)
1. **Aucune API de commande.** Il suffit de produire des commandes prêtes à faire approuver par un humain ; elles n'ont pas besoin d'être envoyées. Un compte webshop (prod, sans possibilité de commander) est disponible au stand.
2. `closingTime` = heure limite de commande pour obtenir la livraison à `availableDate`. Les données mock restent figées tout le week-end, donc une `closingTime` passée est un artefact. En production, ces valeurs bougent.
3. `availableAmount` ≥ 999999 = **dispo inconnue** (produits Terminal non stockés par Valio) ; la logique actuelle accepte n'importe quelle quantité. `scheduleLines` vide = **non disponible**.
4. `allowedLotSize` 0.01 → **à traiter comme 1** (pas de fraction de carton).
5. Rate limit : un **429 bloque 30 s**. Quelques centaines d'appels par minute passent ; plus de ~10 par seconde, non. → client avec throttle (< 10 req/s), gestion du 429 (pause de 30 s puis nouvel essai), et cache.

## Endpoints
- `GET /api/ping`
- `POST /api/availability` et `POST /api/price` : body `{customer, requestedDate (YYYY-MM-DD), products[1..1000]}`
- **Pas d'endpoint de commande, de réservation ni de substitution** → à concevoir nous-mêmes.
- Rate limits non divulgués : filtrer d'abord sur le catalogue statique, puis appeler l'API.
- `customer` n'a aucun effet dans le mock.

## Catalogue : champs utiles
- `id`, `salesUnit` (KI, ST, KG, PAK…), `baseUnit`, `units[]` (`sizeInBaseUnits`), `allowedLotSize`
- `vendorName`, `countryOfOrigin` (ISO-2), `temperatureCondition`, `deposits`
- `substitutions[]` : seulement 196 produits ont des substitutions officielles
- `synkkaData` (GS1 Synkka) : noms en en/fi/sv, ingrédients, nutrition, `brand`, `producers`, `vatCode`
  - `classifications` :
    - `packagingMarkedLabel` = labels (EU_ORGANIC_FARMING, SVANEN, MSC, ASC, FAIR_TRADE, RAINFOREST_ALLIANCE, GOODS_FROM_FINLAND_BLUE_SWAN, KRAV…)
    - `nutritionalClaim` (FREE_FROM_LACTOSE, LOW_LACTOSE, VEGAN, FREE_FROM_GLUTEN…)
    - `allergen` / `nonAllergen` (codes GS1)
    - `gda` / `nutritionFact`
  - Pas de volume en litres explicite : à parser depuis le nom (« 10 l », « 1 L ») ou à dériver de `comparisonPrice`.

## Comportement de la disponibilité (échantillon de 300 produits, livraison le 16/11)
- `Terminal` (~40 %) : quantité toujours 999999, donc inconnue → c'est une affirmation **non vérifiable**
- `Stock` avec quantité limitée (~26 %) : vraie quantité → **dispo partielle possible**
- `Stock` 9999999999 (~11 %) : en pratique illimité
- `scheduleLines` vide (~19 %) : non livrable
- `Stock` avec quantité 0 et sans date (~3 %)
- `closingTime` = heure limite de commande. Pour les produits Terminal elle tombe parfois **avant maintenant** alors que le produit est quand même dispo à la date demandée → artefact des données figées (cf. clarification 2).
- Prix : `catalogPrice` / `listPrice` / `comparisonPrice` (par L ou KG), validFrom/validTo, TVA 13,5 % en alimentaire.

## Scénario « 1000 L de lait sans lactose »
78 produits contiennent « lactose » et « milk » dans leur nom anglais. Exemples de formats vrac :
- 463038 : Valio Eila semi-skimmed 10 l novobox, KI = 2×ST, 31,31 €/KI, 1,57 €/L, Terminal
- 464179 : Arla 10 L Novobox, 27,22 €, 2,72 €/L, Terminal
- 464201 / 464398 : Valio 1 l UHT, Stock

## Exploration approfondie de l'API (14/11, environ 30 appels)
- **La disponibilité est un instantané fixe, indépendant de la date demandée.** Sur 9 dates testées, du 15/11/2026 au 01/02/2027 (et même en 2025), on obtient toujours les mêmes quantités et `availableDate` = 2026-11-16. « Earliest date » veut donc dire : prochain jour de livraison possible, le lundi 16/11.
  - Une date passée est acceptée sans erreur.
  - Un mauvais format de date renvoie 422.
- **Les prix ne dépendent pas non plus de la date** : identiques entre novembre 2026 et février 2027. En revanche, le champ `validTo` est utile, car certains prix nets expirent le 31/12/2026. Il peut servir de durée de validité pour un devis.
- **`netPriceFound` = true** pour environ 1 % d'un échantillon aléatoire, mais pour beaucoup de laits. Il s'agit d'un prix net client très inférieur au `listPrice` (ex. 10,42 contre 24,85).
- **TVA** à 13,5 % ou 25,5 %.
- **`comparisonUnit`** absent pour ~26 % des produits, donc pas de comparaison au L ou au kg possible pour eux. Valeurs observées : KG ~62 %, L ~12 %.
- **Produit inconnu** :
  - l'API availability renvoie `scheduleLines: []`, ce qui est **indiscernable d'un produit indisponible** ;
  - l'API price renvoie `error: true`.
  - → Toujours valider l'id contre le catalogue avant d'appeler l'API.
- **Consignes** : 506 produits en ont, avec des codes matière (1, 3, 4, 171…) **absents du catalogue et sans prix** (`error: true`). On ne peut donc pas calculer le coût total consigne comprise.
- **`allowedLotSize`** ≠ 0,01 pour environ 670 produits (2, 3, 1,5, 5, 10 ; ex. bavette 10 kg). Il faut respecter ces multiples.
- **Substitutions** :
  - 250 paires, surtout des **fruits et légumes frais**, souvent dans les deux sens ;
  - la substitution **change souvent l'origine** (courgette NL/ES ↔ FI, concombre FI ↔ NL/ES) → conflit possible avec les préférences d'origine de l'acheteur ;
  - le taux de disponibilité des originaux et des substituts est le même (~69 %).
- **Carbone** : valeur moyenne par catégorie, donc **identique pour tous les laits** (1,1). Elle ne différencie rien au sein d'une catégorie, seulement entre catégories (ex. lait vs boisson végétale).
- **Fiabilité de livraison** : souvent 1.0 ou absente pour les laits, peu discriminante ici.

### Scénario « 1000 L de lait sans lactose » (catégorie 10400, 35 produits)
- Les moins chers au litre sont **trompeurs** : lait de café, lait fermenté (sour milk), aromatisé… → le moteur doit écarter les **types de produit non équivalents**, pas seulement trier par prix.
- Vrai lait de consommation le moins cher : 464306 Valio Arki Eila 1 L, **1,01 €/L (prix net client)**, Stock illimité, limite de commande dim. 15/11 17h → ~1 010 € HT.
- Aucun cas de dispo partielle pour le lait : tout est illimité ou Terminal. **Pour montrer la dispo partielle et la substitution, il faut un 2e scénario** (produits frais avec stock limité, ou les paires de substitution fruits et légumes).
