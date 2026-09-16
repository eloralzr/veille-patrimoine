# Routine quotidienne — alimenter l'artefact (2 minutes)

Chaque nuit (04:00 UTC), GitHub Actions lit les flux, extrait les fiches avec le modèle configuré et publie deux fichiers dans le dossier `exports/` du dépôt :

- `exports/fiches_AAAA-MM-JJ.json` — les fiches créées cette nuit ;
- `exports/derniers_7_jours.json` — toutes les fiches des sept derniers jours, pour rattraper un import oublié.

## Le geste du matin

1. github.com → dépôt `veille-patrimoine` → dossier `exports` → fichier du jour.
2. Bouton **Raw** → Ctrl+A, Ctrl+C.
3. Artefact **Veille programmes** → onglet **Analyser un texte** → dépliant **Importer des fiches au format JSON** → coller → **Contrôler**.
4. Lire le bilan : *nouvelles fiches / déjà en base / refusées*. Les doublons (même candidat, même source, même titre) sont ignorés automatiquement ; un import répété est sans effet.
5. Décocher les fiches manifestement hors sujet, puis **Enregistrer les fiches cochées**. Elles arrivent en statut « Brut », marquées `auto`.

Après une absence : importer `derniers_7_jours.json` en une seule fois.

## Ce qu'il faut savoir

- Si le fichier du jour n'existe pas : la collecte n'a rien produit (aucun document nouveau) ou le workflow a échoué → onglet **Actions** du dépôt, dernière exécution, journal.
- Le fichier peut contenir des fiches de qualité inégale (modèle Gemini) : c'est la relecture au moment du **Contrôler** qui fait le tri, puis la validation dans **Propositions**.
- Les fiches dont la source est antérieure au 1er septembre 2025 sont refusées, côté pipeline comme côté artefact.
- Le bot commite les exports sous le nom `veille-bot` ; ces commits n'affectent ni le code ni le référentiel.

## Installation (une fois)

Voir `docs/INSTALL-phase7.md` (dépôt, migration Supabase, secrets, premier lancement). La phase 8 ajoute uniquement le dossier `exports/` et l'étape de publication dans le workflow ; aucun secret supplémentaire.
