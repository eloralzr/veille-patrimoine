# Phase 4 — Installation de la v0 (sans API)

Propriétaire : Elora Lazaar — 2026-09-15. Durée estimée : 45 minutes, tout depuis le navigateur.

## A. Déposer les fichiers sur GitHub (10 min)

1. Décompresser `veille-patrimoine-phase4.zip` dans Téléchargements.
2. Sur github.com, dépôt `veille-patrimoine` → **Add file → Upload files**.
3. Glisser-déposer **le contenu** du dossier décompressé (les fichiers et sous-dossiers, pas le dossier parent). Les fichiers existants (`data/`, `README.md`) sont remplacés par les versions identiques ou mises à jour : normal.
4. Message : `phase 4 : application v0 sans API` → **Commit changes**.
5. Vérifier que le dossier `.streamlit/` contient bien `config.toml` et `secrets.toml.example` (les dossiers commençant par un point sont parfois ignorés par le glisser-déposer). Sinon : **Add file → Create new file**, nom `.streamlit/config.toml`, coller le contenu, commit.
6. Vérifier que `.gitignore` contient `.streamlit/secrets.toml`.
7. Supprimer le dossier décompressé du poste.

## B. Créer les tables Supabase (10 min)

1. supabase.com → votre projet → **SQL Editor → New query**.
2. Ouvrir `db/schema.sql` sur GitHub → bouton **Raw** → tout sélectionner, copier → coller dans l'éditeur → **Run**. Résultat attendu : `Success. No rows returned`.
3. **New query** → même opération avec `db/seed_referentiel.sql` → **Run**. Résultat attendu : `Success` avec 38 puis 53 lignes.
4. **Table Editor** : les tables `acteurs` (38 lignes), `sources` (53), `documents` (0), `mesures` (0) doivent apparaître.

## C. Déployer sur Streamlit Community Cloud (10 min)

1. share.streamlit.io → **New app → Deploy a public app from GitHub**.
2. *Repository* : `votre-nom/veille-patrimoine` · *Branch* : `main` · *Main file path* : `app.py`.
3. *App URL* : choisir un nom neutre (ex. `veille-prog-2027`).
4. **Advanced settings** → *Python version* : 3.12 → *Secrets* : coller

   ```
   APP_PASSWORD = "un mot de passe robuste à partager avec les ingénieurs"
   SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
   SUPABASE_KEY = "..."
   ```

   `SUPABASE_URL` et `SUPABASE_KEY` : Supabase → **Project Settings → API** → *Project URL* et clé **service_role** (bouton *Reveal*). Copier d'un onglet à l'autre, sans passer par un fichier.
5. **Save → Deploy**. Premier déploiement : 2 à 4 minutes. L'écran de mot de passe doit apparaître.
6. En cas d'erreur : bouton **Manage app** (bas droit) → copier le journal → me le coller.

## D. Créer le Projet Claude (10 min)

1. Claude Enterprise → **Projects → New project** → nom `Veille programmes`.
2. **Instructions** : coller le contenu de `extraction/projet_claude_instructions.md` (à partir de la ligne « ## Rôle »).
3. **Project knowledge → Add content** : téléverser `data/taxonomie.yaml` et `data/acteurs.csv` (les télécharger depuis GitHub → *Raw* → enregistrer, ou copier-coller leur contenu comme texte).
4. Partager le projet avec les ingénieurs testeurs.

## E. Premier test de bout en bout (5 min)

1. Dans le Projet Claude, coller :

   ```
   ACTEUR : institut-montaigne
   URL : https://www.institutmontaigne.org/
   DATE : 2026-09-15
   TEXTE : [un paragraphe réel d'une note récente sur la fiscalité ou la transmission]
   ```
2. Copier le JSON renvoyé.
3. Application → initiales dans la barre latérale → page **Saisie** → coller → **Enregistrer les fiches valides**.
4. Page **Fiches** : la fiche apparaît en statut Brut → **Marquer vérifiée**.
5. Page **Tableau de bord** : les compteurs se mettent à jour.

## Mise à jour du référentiel en v0

Modifier `data/acteurs.csv` ou `data/sources.csv` sur GitHub ne suffit pas : la base lit ses propres tables. Procédure v0 : me transmettre les modifications, je régénère `db/seed_referentiel.sql`, vous le rejouez dans SQL Editor (il est ré-exécutable). Une page d'administration remplacera cette étape en v1.

## Résolution des problèmes fréquents

| Symptôme | Cause probable | Correction |
|---|---|---|
| `KeyError: 'SUPABASE_URL'` | Secrets non enregistrés | App settings → Secrets → vérifier, *Save*, *Reboot app* |
| `Invalid API key` | Clé `anon` au lieu de `service_role` | Remplacer par la clé service_role |
| Page Référentiel vide | `seed_referentiel.sql` non exécuté | Étape B.3 |
| `ModuleNotFoundError` | `requirements.txt` absent ou mal placé | Il doit être à la racine du dépôt |
| Fiche refusée « acteur_id inconnu » | Claude a inventé un identifiant | Vérifier `acteurs.csv` dans le Projet Claude ; corriger le JSON |
