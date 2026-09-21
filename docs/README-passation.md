# Veille programmes — patrimoine 2027 : note de passation

Propriétaire : Elora Lazaar · Version 2026-09-21 · Destinataire : personne de permanence.
À déposer dans les fichiers du Projet Claude « Import veille » et dans `docs/` du dépôt.
Changement 17b : le Projet Claude couvre désormais deux modes (import du JSON nocturne, extraction
manuelle d'un texte source) ; convention de déclenchement dans `PROJET-import-veille.md`.
Changement 2026-09-21 : référentiel v2026-09-19 (thème `fiscalite` renommé « Fiscalité du patrimoine et
ingénierie patrimoniale » et rattachement de `regime_matrimonial` ; `structuration` ne garde que
`societes_patrimoniales` ; Tondelier et Lisnard en P1 / quotidien). La page de l'artefact met désormais
`config/referentiel` à jour automatiquement à l'ouverture quand elle embarque une version plus récente
que la base (acteurs ajoutés à la main conservés). Chantiers ouverts : onglet PLF/PLFSS 2027, export
PowerPoint par thème sur le gabarit LAM 2026.

## Liens
- Artefact Claude (interface de l'équipe) : https://claude.ai/artifact/FJCFkScutgDMyVZ8Lsvvpe
- Dépôt GitHub (pipeline, référentiel, documentation) : https://github.com/eloralzr/veille-patrimoine — v0.9, référentiel v2026-09-19
- Documents du dépôt à connaître : `docs/ROUTINE-quotidienne.md` (le geste du matin), `docs/MODE-EMPLOI.md`, `docs/PROJET-import-veille.md` (v2026-09-17b)

## Architecture en dix lignes
1. Chaque nuit, GitHub Actions (`.github/workflows/collecte.yml`) lance `jobs/run_collecte.py`.
2. `collecte/rss.py` lit les flux RSS et requêtes presse du référentiel (`data/`), hors `data/domaines_exclus.txt`.
3. `extraction/llm.py` extrait les fiches via une API LLM interchangeable (Gemini par défaut, repli possible), avec le prompt de `extraction/prompts.py`.
4. `extraction/schema.py` valide chaque fiche contre la taxonomie.
5. Les fiches sont écrites dans Supabase (`db/`) et exportées dans `exports/fiches_AAAA-MM-JJ.json`, avec `saisi_par = auto:<modèle>`.
6. Le matin, la permanence colle ce JSON dans le Projet Claude « Import veille ».
7. Claude lit le référentiel et les fiches voisines dans l'artefact, trie, puis écrit les fiches retenues en `batch` dans la collection `mesures`.
8. L'artefact porte la base : collection `mesures` et document `config/referentiel` (acteurs + taxonomie, embarqués dans la page, qui fait foi).
9. L'équipe travaille dans l'artefact : filtres, tableau de bord, export CSV, workflow `brut → verifie → publie` (ou `retire`).
10. Streamlit + Supabase restent le dossier d'internalisation ; l'artefact est l'interface d'usage, le réseau n'autorisant pas l'hébergement externe.

## Base de l'artefact
- `mesures` : une fiche par document, `doc_id = id`. Champs : `id`, `acteur_id`, `theme_id`, `sous_theme_id`, `mots_cles`, `titre`, `resume`, `citation`, `nature`, `impact_client`, `url_source`, `date_source`, `confiance`, `statut`, `saisi_par`, `valide_par`, `cree_le`, `maj_le`.
- Valeurs de `saisi_par` : `auto:<modèle>` (pipeline nocturne), `manuel:claude` (extraction manuelle via le Projet Claude), `manuel:<nom>` (saisie directe dans l'artefact).
- `config/referentiel` : `version`, `acteurs[]`, `taxonomie{themes, natures_position, niveaux_confiance, statuts_fiche}`. Réécrit par la page à partir du référentiel embarqué, automatiquement à l'ouverture si la page est plus récente que la base : pour modifier le référentiel, modifier la page (et `data/` du dépôt), pas la base.
- Contrôle de doublons de l'artefact à l'enregistrement manuel : fiches « voisines » = même `acteur_id` et même `sous_theme_id`, statut ≠ `retire`. L'import du matin et l'extraction manuelle appliquent le même critère.

## Procédure d'import du matin (2 minutes)
1. Ouvrir `exports/fiches_<date>.json` dans le dépôt, copier le contenu.
2. Le coller dans le Projet Claude « Import veille ».
3. Claude lit `config/referentiel`, puis, pour chaque couple (`acteur_id`, `sous_theme_id`) du fichier, interroge `mesures` par `query` — pas de lecture de toute la collection.
4. Tri fiche par fiche : refusée / écartée / corrigée puis importée (règles ci-dessous) ; `id`, `saisi_par`, `cree_le` conservés ; statut `brut`.
5. Écriture en un `write_db` `batch` (op `set`).
6. Relire le compte rendu (tableau fiche / décision / motif, puis état par thème). Vérifier dans l'artefact que les fiches apparaissent en « Brut ».
7. Jamais de modification silencieuse d'une fiche existante, jamais de suppression, aucun complément de mémoire.

## Procédure d'extraction manuelle (hors pipeline)
Pour un texte public que le pipeline n'a pas capté (programme, interview, note de think tank, communiqué).
1. Coller dans le Projet Claude le texte au format :
   ```
   ACTEUR : <acteur_id ou nom>
   URL : <lien de la source>
   DATE : <AAAA-MM-JJ>
   TEXTE :
   <extrait>
   ```
2. Par défaut, Claude répond avec le JSON des fiches seulement, puis propose l'écriture en base ; répondre « importe » pour déclencher l'import (mêmes contrôles que le matin), ou coller le JSON dans l'artefact.
3. Pour tout faire en un passage, ajouter « extrais et importe » au message.
4. Claude génère `id` (UUID v4), `saisi_par = manuel:claude`, `cree_le` ; statut `brut`. Relire le compte rendu comme pour un import.
5. Si l'acteur n'est pas au référentiel, Claude le dit et n'extrait pas : ajouter l'acteur dans `data/` et la page de l'artefact d'abord.

## Règles de qualité
- **Date** : `date_source` obligatoire et ≥ 2025-09-01 ; sinon refus.
- **Acteur** : `acteur_id` présent dans le référentiel ; sinon refus.
- **Source** : rédaction identifiable ; sinon refus.
- **Doublon** : même mesure (même sens, mêmes chiffres) déjà en base pour le même acteur → écartée, quelle que soit la source ; une source nouvelle ne justifie une fiche que si elle apporte une précision.
- **Nature** : un candidat n'est jamais en `proposition` (réservé aux think tanks, organisations, clubs). `engagement` = programme ou engagement ferme ; `piste` = idée évoquée ; `reaction` = réponse à un autre acteur ; `chiffrage` = estimation de coût ou de rendement.
- **Citation** : verbatim de 25 mots au plus, jamais reformulée ; vide sinon.
- **Confiance** : `eleve` = source primaire et mesure explicite ; `moyen` = source secondaire fiable ou formulation générale ; `incertain` = propos rapportés par un tiers, rappel ancien, média faible, formulation ambiguë. Un article qui rapporte des propos sans les citer ne dépasse pas `moyen`.
- **Neutralité** : l'outil compare, il ne classe pas ; aucune opinion, aucun complément de mémoire sur les acteurs.

## Statuts d'une fiche
`brut` (importée ou saisie, non relue) → `verifie` (relue par un ingénieur, `valide_par` renseigné) → `publie` (visible dans le tableau de bord en mode vérifié) ; `retire` sort la fiche de la vue sans la supprimer, « Rétablir » la ramène en `brut`.

## Points de vigilance
- Le référentiel du Projet (`acteurs.csv`, `taxonomie.yaml`) est une copie au 2026-09-19 ; la référence vivante est `config/referentiel` dans l'artefact et `data/` dans le dépôt. À chaque modification de `data/` : republier la page de l'artefact (la base suit à l'ouverture), remplacer les deux fichiers du Projet.
- Le Projet ne doit contenir qu'une seule version de `PROJET-import-veille.md` (la 17b) ; toute version pointant vers un autre artefact est à supprimer. Le texte des Instructions du Projet est identique à ce fichier.
- Tenir synchronisés `PROJET-import-veille.md` du Projet et `docs/PROJET-import-veille.md` du dépôt.
- Les sorties de Claude restent internes ; aucune fiche ne sort du périmètre sans relecture (`verifie` au minimum).
