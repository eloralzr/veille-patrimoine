# Dossier `data/` — référentiel de veille

**Propriétaire :** Elora Lazaar  
**Version :** v1 — 2026-09-14  
**Objet :** référentiel métier de l'outil de veille des programmes économiques et fiscaux (candidats à la présidentielle 2027, think tanks, organisations représentatives, clubs d'entrepreneurs) sur les thèmes de l'ingénierie patrimoniale.

## Fichiers

| Fichier | Contenu | Clé |
|---|---|---|
| `acteurs.csv` | 1 ligne par acteur suivi (26 candidats, 5 think tanks, 4 organisations, 1 club, 2 institutions) | `acteur_id` |
| `sources.csv` | 1 ligne par flux de collecte, rattaché à un acteur | `source_id` → `acteur_id` |
| `taxonomie.yaml` | Thèmes → sous-thèmes → mots-clés, natures de position, niveaux de confiance, statuts | `theme.id`, `sous_theme.id` |
| `requetes_presse.csv` | Flux RSS Google Actualités générés acteur × thème (P1) ou acteur tous thèmes (P2) | `requete_id` → `acteur_id`, `theme_id` |

Encodage UTF-8, séparateur virgule, dates au format ISO `AAAA-MM-JJ`, booléens `true` / `false`.

## Valeurs autorisées

**`acteurs.type`** : `candidat`, `think_tank`, `organisation`, `club`, `institution`  
**`acteurs.camp`** : `extreme_gauche`, `gauche`, `ecologiste`, `centre`, `droite`, `droite_nationale`, `souverainiste`, `autre`, `na`  
**`acteurs.statut`** : `declare`, `primaire`, `investi`, `a_confirmer`, `retire`, `na`  
**`acteurs.priorite`** : `P1` (veille quotidienne), `P2` (hebdomadaire), `P3` (mensuelle, programme publié uniquement)  
**`sources.type_source`** : `rss`, `page_web`, `pdf`, `youtube`, `podcast`, `newsletter`, `parlement`, `manuel`  
**`sources.mode_collecte`** : `auto`, `manuel`  
**`sources.fiabilite`** : `primaire` (l'acteur lui-même), `secondaire` (presse, relais)  
**`sources.robots_ok`** : `true`, `false`, `na` — à renseigner après vérification du `robots.txt` et des CGU ; **aucune source `auto` ne doit être activée avec `robots_ok` = `na` ou `false`**.

## Règles de saisie

1. **Un acteur = une ligne** dans `acteurs.csv`. Ses flux vont dans `sources.csv`, jamais dans `acteurs.csv`.
2. **`acteur_id`** : slug minuscule, sans accent, `nom-prenom` pour les personnes (`philippe-edouard`), nom court pour les structures (`ofce`).
3. **Ajout d'un acteur** : renseigner `maj_par` et `maj_le` ; laisser `actif = true`. Ne jamais supprimer une ligne : passer `statut = retire` et `actif = false` (historisation).
4. **Ajout d'un mot-clé** : d'abord dans `taxonomie.yaml`, puis dans `requetes_presse.csv` si pertinent pour la presse.
5. **Sources déduites** : les URL RSS marquées « déduite, à confirmer » dans `notes` sont désactivées (`actif = false`) tant qu'un ingénieur ne les a pas ouvertes dans un navigateur et renseigné `robots_ok`.
6. **Traçabilité** : toute modification passe par un commit Git avec un message explicite (`data: ajout Maurel Emmanuel (primaire PS)`).

## Neutralité

La priorité `P1`/`P2`/`P3` mesure **l'effort de veille** (poids électoral estimé et richesse attendue du programme sur nos thèmes). Elle n'exprime aucun jugement politique et ne doit pas être présentée comme tel. L'outil compare les positions ; il ne les classe pas.

## Cadre

- Données publiques uniquement. Aucune donnée client, aucun document interne.
- Aucune collecte automatisée sur les réseaux sociaux (X, LinkedIn) : sources écartées à la date de la v1.
- Traitement relevant du RGPD (opinions de personnes physiques) : inscription au registre des traitements à effectuer avant mise en production partagée.

## État au 2026-09-14

- Statut de Xavier Bertrand validé par la propriétaire ; source presse à joindre dans `notes`.
- URL des sites de campagne, programmes et chaînes vidéo des candidats : **à renseigner** (champs vides).
- Sites MEDEF, CGT, CFDT, FO et flux parlementaires : **à renseigner**.
- Entrées attendues dans la liste : François Hollande, Bernard Cazeneuve, Emmanuel Maurel, Fabien Verdier (primaire PS), Antoine Mikolajczak, Francis Lalanne, Benoît Mathieu.

## Historique

| Version | Date | Auteur | Modification |
|---|---|---|---|
| v1 | 2026-09-14 | Elora Lazaar | Création du référentiel : 38 acteurs, taxonomie 4 thèmes / 17 sous-thèmes, 34 requêtes presse |
