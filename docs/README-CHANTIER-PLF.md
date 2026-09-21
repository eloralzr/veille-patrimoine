# Chantier « Veille PLF / PLFSS 2027 » — kit d'intégration dans `veille-patrimoine`

Propriétaire : Elora Lazaar · Kit du 2026-09-21 · Cible : dépôt https://github.com/eloralzr/veille-patrimoine (v0.9)

Ce kit ajoute au pipeline nocturne la collecte et l'extraction des textes budgétaires, en parallèle de la
veille programmes (rien n'est modifié dans `collecte/rss.py`, `extraction/llm.py`, `jobs/run_collecte.py`).
Les fiches produites sont importées dans l'espace **PLF · PLFSS 2027** de l'artefact
(https://claude.ai/artifact/FJCFkScutgDMyVZ8Lsvvpe), collection `mesures_plf`, publié le 2026-09-21.

## Contenu du kit

| Fichier | Rôle | Où le déposer |
|---|---|---|
| `data/acteurs_plf.csv` | 31 acteurs parlementaires et institutionnels (Gouvernement, commissions, CMP, CC, CE, HCFP, Cour des comptes, 12 groupes AN, 9 groupes Sénat) avec effectifs, sources officielles et codes AN (`code_an`) | `data/` |
| `data/taxonomie_plf.yaml` | Listes fermées : `natures_position`, `textes`, `chambres`, `stades`, `sorts` (thèmes communs : `taxonomie.yaml`) | `data/` |
| `data/sources_plf.yaml` | Configuration de collecte : identifiants des dossiers, URL des données ouvertes, correspondance groupes → `acteur_id`, mots-clés presse, filtre | `data/` |
| `collecte/plf.py` | Collecteurs : amendements AN (données ouvertes), texte initial (PDF/HTML découpé par article), amendements Sénat (HTML, phase 1) | `collecte/` |
| `extraction/prompts_plf.py` | Prompt d'extraction législatif, **identique** à celui de la page de l'artefact | `extraction/` |
| `extraction/schema_plf.py` | Chargement du référentiel PLF, validation et normalisation des fiches (miroir de la page) | `extraction/` |
| `jobs/run_collecte_plf.py` | Job : collecte → nouveauté → LLM → validation → `exports/fiches_plf_AAAA-MM-JJ.json` (+ `refus_plf_…json`) | `jobs/` |
| `.github/workflows/collecte_plf.yml` | Exécution quotidienne 04h30 UTC + déclenchement manuel (option `dry_run`) | `.github/workflows/` |
| `tests/test_schema_plf.py` | 4 tests : référentiel, fiche valide, refus, normalisation | `tests/` |
| `docs/PROJET-import-veille.md` | Instructions du Projet Claude **v17c** (mode « Import PLF ») — à coller aussi dans Projects → Instructions et à remplacer dans les fichiers du Projet | `docs/` |

## Intégration en six étapes

1. **Déposer les fichiers** aux emplacements du tableau ; ajouter `pdfplumber` (ou `pypdf`) à `requirements.txt`
   si absent ; s'assurer que `collecte/`, `extraction/`, `jobs/` ont un `__init__.py`.
2. **LLM** : déjà branché sur `extraction/llm.py` (`llm.appeler`, `llm.fournisseur_courant`). Le workflow reprend
   les mêmes secrets et variables que `collecte.yml` ; aucun nouveau secret à créer si la veille programmes tourne.
3. **Vérifier les données ouvertes de l'AN** (avant la première exécution réelle) : télécharger le zip indiqué
   dans `sources_plf.yaml`, ouvrir un amendement JSON et confronter les chemins lus par `collecte/plf.py`
   (`_texte_amendement`, `_acteur_amendement`, `_stade_amendement`, `_sort_amendement`, `_date_amendement`,
   `uid`, `numeroLong`, `pointeurFragmentTexte.division.titre`, `texteLegislatifRef`). Ajuster les chemins si
   la structure diffère : tout est concentré dans ces fonctions.
4. **Renseigner le dossier PLF 2027** dans `sources_plf.yaml` dès le dépôt du texte (début octobre 2026) :
   `an_dossier_ref`, `an_texte_refs` (un identifiant par texte examiné : dépôt, texte de commission, etc.),
   `page_an`, `page_gouv`, et soit `texte_initial_url` (PDF/HTML du projet) soit `texte_initial_pdf`
   (chemin d'un PDF déposé dans `data/textes/`). Même chose pour `plfss`.
5. **Premier passage à blanc** : `python -m jobs.run_collecte_plf --dry-run` liste les documents qui seraient
   envoyés au LLM (acteur, stade, article, URL) sans consommer de quota. Ajuster le filtre
   (`filtre.mots_cles_minimum`) si le volume est déraisonnable, puis lancer sans `--dry-run`.
6. **Routine du matin** : coller `exports/fiches_plf_<date>.json` dans le Projet Claude (mode « Import PLF »,
   v17c) ou dans l'artefact, espace PLF, Source manuelle → Importer des fiches JSON. Relire le compte rendu ;
   les fiches arrivent en « Brut ». `exports/refus_plf_<date>.json` liste ce qui a été écarté et pourquoi.

## Règles reprises du pipeline programmes

- Date ≥ 2025-09-01, acteur du référentiel, URL http(s), citation ≤ 25 mots, statut `brut`, `saisi_par = auto:<modèle>`.
- Aucun complément de mémoire : le prompt interdit d'ajouter ce que le modèle sait du texte ou de l'acteur.
- Nouveauté : `exports/.plf_sources_vues.json` mémorise les `source_id` traités ; un amendement n'est envoyé
  au LLM qu'une fois. Son évolution (stade, sort) se gère au moment de l'import (mise à jour de la fiche
  existante, jamais silencieuse — voir v17c).

## Phase 2 (après stabilisation)

- **Sénat** : remplacer le collecteur HTML par la lecture du dump Ameli/Dosleg (data.senat.fr) : stade et sort
  fiables, numéros d'amendement normalisés.
- **Suivi de sort automatique** : rapprocher chaque nuit les amendements déjà en base (`num_amendement`) avec
  leur sort dans les données ouvertes, et produire un fichier `exports/sorts_plf_<date>.json` de mises à jour
  à appliquer par le Projet Claude.
- **Renouvellement sénatorial** : mettre à jour `acteurs_plf.csv` et le référentiel embarqué dans la page
  début octobre 2026 (nouvelle composition des groupes).

## Points de vigilance

- Les URL des données ouvertes (`a_verifier: true`) sont à confirmer : elles changent avec la législature.
- Les données ouvertes de l'AN peuvent peser plusieurs centaines de Mo : le job s'exécute sur GitHub Actions
  (timeout 45 min) ; si nécessaire, filtrer par `texteLegislatifRef` avant le décodage JSON.
- Sorties internes uniquement ; aucune fiche ne sort du périmètre sans relecture (`verifie` minimum).
