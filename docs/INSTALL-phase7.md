# Phase 7 — Collecte et extraction automatiques

Propriétaire : Elora Lazaar — 2026-09-15. Durée : 30 minutes, tout depuis le navigateur.

## Ce que fait la phase 7

Chaque nuit (04:00 UTC, soit 6 h à Paris l'été), GitHub Actions :
1. lit les flux RSS actifs de la table `sources` et les 34 flux presse de `data/requetes_presse.csv` ;
2. enregistre les articles nouveaux dans `documents` (statut « à traiter »), avec le texte complet quand il est récupérable ;
3. envoie chaque document au modèle configuré (Gemini par défaut) avec le prompt d'extraction ;
4. valide les fiches (mêmes règles que la page Saisie) et les insère dans `mesures` en statut **Brut**, marquées `auto:gemini` ;
5. consigne l'exécution dans `collecte_runs`, visible dans la page **File de collecte** de l'application.

Le fournisseur se change sans toucher au code : variable `LLM_FOURNISSEUR` (`gemini`, `mistral`, `anthropic`, `openai` pour une passerelle compatible type LazardGPT).

## A. Déposer les fichiers sur GitHub (10 min)

1. Décompresser `veille-patrimoine-phase7.zip`.
2. Dépôt → **Add file → Upload files** → glisser le **contenu** du dossier (pas le dossier parent) → message `phase 7 : collecte automatique` → **Commit changes**.
3. Le dossier `.github/` est masqué et n'est souvent pas uploadé. Vérifier ; sinon **Add file → Create new file**, nom `.github/workflows/collecte.yml`, coller le contenu du fichier du zip, commit.
4. Vérifier à la racine : `requirements-collecte.txt`, dossiers `collecte/`, `jobs/`, `.github/workflows/collecte.yml`.

## B. Mettre la base à jour (2 min)

Supabase → **SQL Editor → New query** → coller `db/migration_phase7.sql` (bouton *Raw* sur GitHub) → **Run**. Attendu : `Success`. Le Table Editor montre une nouvelle table `collecte_runs`.

## C. Vérifier les secrets GitHub (déjà faits)

Dépôt → **Settings → Secrets and variables → Actions** : `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY` présents. `MISTRAL_API_KEY` et `ANTHROPIC_API_KEY` sont facultatifs.

Pour changer de fournisseur ou de modèle plus tard : onglet **Variables** (pas Secrets) → **New repository variable** → `LLM_FOURNISSEUR` = `mistral` (et éventuellement `LLM_MODELE`).

## D. Premier lancement manuel (10 min)

1. Dépôt → onglet **Actions** → workflow **Collecte et extraction quotidiennes** → **Run workflow** → `max_docs` = `10` pour un premier essai → **Run workflow**.
2. Cliquer sur l'exécution qui apparaît → étape *Collecte + extraction* → lire le journal : nombre de flux lus, documents nouveaux, fiches créées, erreurs éventuelles.
3. Application → **File de collecte** : l'exécution et ses compteurs apparaissent ; les documents sont listés avec leur statut.
4. Application → **Fiches** : les fiches 🤖 auto sont en statut Brut. En relire deux ou trois : si le résumé est fidèle, passer en « vérifié ».
5. Si tout est correct, relancer sans limite (`max_docs` = `40`) ou attendre la nuit.

## E. Lire les résultats

| Statut document | Signification | Action |
|---|---|---|
| à traiter | collecté, pas encore extrait (limite `max_docs` atteinte) | attendre la prochaine exécution |
| traité | extrait ; `nb_fiches` = fiches créées (0 possible si hors thème) | rien |
| ignoré | texte trop court (résumé de flux seul, page non récupérable) | bouton *Copier pour Claude* si l'article vous intéresse |
| erreur | l'API a refusé ou renvoyé un JSON illisible | bouton *Relancer l'extraction* ; si récurrent, voir F |

## F. Problèmes fréquents

| Symptôme | Cause | Correction |
|---|---|---|
| `Secret manquant : GEMINI_API_KEY` | secret absent ou mal nommé | Settings → Secrets → vérifier le nom exact |
| `Gemini HTTP 429` | quota gratuit atteint | réduire `MAX_DOCS` (variable ou saisie au lancement) ; le script relance automatiquement 3 fois |
| `Gemini HTTP 400 … model not found` | nom de modèle obsolète | Variables → `LLM_MODELE` = un modèle Flash courant listé dans AI Studio |
| Beaucoup de documents « ignorés » | sites qui bloquent la récupération du texte | normal pour certains médias ; les flux think tanks/organisations passent mieux |
| `flux illisible` dans le journal | URL RSS déduite fausse | corriger `sources.csv`, régénérer le seed, ou désactiver la source |
| Fiches avec acteur refusé | le modèle invente un identifiant | déjà filtré : la fiche est refusée et notée dans `erreur` du document |
| Le workflow ne tourne pas la nuit | GitHub suspend les crons des dépôts inactifs 60 jours | un commit ou un lancement manuel réactive |

## G. Quotas et volumes

Volume attendu : 20 à 60 documents nouveaux par jour, une requête par document. Le palier gratuit Gemini le couvre largement ; le script plafonne à `MAX_DOCS` par exécution (40) et réessaie en cas de limitation. Le texte envoyé est tronqué à 12 000 caractères.

## H. Bascule vers un autre fournisseur

- **Mistral** : secret `MISTRAL_API_KEY` + variable `LLM_FOURNISSEUR` = `mistral`.
- **Claude (API Lazard ou personnelle)** : secret `ANTHROPIC_API_KEY` + `LLM_FOURNISSEUR` = `anthropic`.
- **Passerelle compatible OpenAI (LazardGPT si c'est son format)** : secrets `OPENAI_API_KEY` et `OPENAI_BASE_URL`, `LLM_FOURNISSEUR` = `openai`, `LLM_MODELE` = nom du modèle exposé. À confirmer avec la documentation de la passerelle ; ce mode ne doit être utilisé qu'avec un hébergement dans le périmètre Lazard.
