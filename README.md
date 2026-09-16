# veille-patrimoine

Outil de veille des programmes économiques et fiscaux (présidentielle 2027) sur les thèmes de l'ingénierie patrimoniale : fiscalité, transmission, structuration, protection.

Propriétaire : Elora Lazaar — v0.8 (collecte automatique + export vers l'artefact Claude), 2026-09-16

## Principe

1. Un ingénieur colle un texte public dans le **Projet Claude « Veille programmes »** → Claude renvoie une fiche JSON.
2. La fiche est collée dans l'application (**Saisie**), validée contre la taxonomie, enregistrée dans Supabase.
3. **Fiches**, **Tableau de bord** et export CSV pour l'équipe ; workflow brut → vérifié → publié.
4. Depuis la phase 7 : collecte RSS et extraction automatiques chaque nuit (GitHub Actions + API LLM interchangeable, Gemini par défaut) ; page **File de collecte**.
5. Depuis la phase 8 : l'interface utilisée par l'équipe est l'**artefact Claude « Veille programmes »** (réseau Lazard n'autorisant pas l'hébergement externe) ; le pipeline publie chaque nuit `exports/fiches_AAAA-MM-JJ.json`, importé dans l'artefact en deux minutes (`docs/ROUTINE-quotidienne.md`). Streamlit + Supabase restent le dossier d'internalisation.

Données publiques uniquement. Aucun secret, aucune donnée collectée dans ce dépôt.

## Structure

```
app.py                                  # interface Streamlit
requirements.txt
.streamlit/config.toml                  # thème ; secrets.toml.example = modèle des secrets (jamais commiter secrets.toml)
data/                                   # référentiel (acteurs, sources, taxonomie, requêtes presse)
db/schema.sql                           # tables Supabase
db/seed_referentiel.sql                 # chargement du référentiel (ré-exécutable)
db/client.py                            # accès base
extraction/schema.py                    # validation des fiches JSON
extraction/projet_claude_instructions.md# instructions du Projet Claude
docs/INSTALL-phase4.md                  # notice d'installation pas à pas
collecte/rss.py                         # collecte des flux RSS et presse
extraction/prompts.py, extraction/llm.py# prompt d'extraction et fournisseurs LLM (gemini, mistral, anthropic, openai)
jobs/run_collecte.py                    # tâche nocturne collecte → extraction → base
.github/workflows/collecte.yml          # planification GitHub Actions
requirements-collecte.txt               # dépendances de la tâche nocturne
db/migration_phase7.sql                 # migration base pour la phase 7
docs/INSTALL-phase7.md                  # notice phase 7
exports/                                # fiches produites chaque nuit, à importer dans l'artefact Claude
docs/ROUTINE-quotidienne.md             # le geste du matin (2 min)
```

## Installation

Phase 4 (application) : `docs/INSTALL-phase4.md`. Phase 7 (collecte automatique) : `docs/INSTALL-phase7.md`.
