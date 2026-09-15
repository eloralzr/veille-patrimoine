# veille-patrimoine

Outil de veille des programmes économiques et fiscaux (présidentielle 2027) sur les thèmes de l'ingénierie patrimoniale : fiscalité, transmission, structuration, protection.

Propriétaire : Elora Lazaar — v0 (sans API), 2026-09-15

## Principe

1. Un ingénieur colle un texte public dans le **Projet Claude « Veille programmes »** → Claude renvoie une fiche JSON.
2. La fiche est collée dans l'application (**Saisie**), validée contre la taxonomie, enregistrée dans Supabase.
3. **Fiches**, **Tableau de bord** et export CSV pour l'équipe ; workflow brut → vérifié → publié.

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
collecte/, jobs/                        # phase 7 (collecte RSS) — à venir
```

## Installation

Voir `docs/INSTALL-phase4.md`.
