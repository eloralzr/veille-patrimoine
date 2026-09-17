# Veille programmes — mode d'emploi (v0.9, 17 septembre 2026)

Propriétaire : Elora Lazaar. Outil : artefact Claude « Veille programmes » (membres de l'organisation). Pipeline : dépôt GitHub `veille-patrimoine`.

## 1. Ce que fait l'outil
Compare ce que proposent les candidats à la présidentielle 2027 et les institutions (think tanks, organisations, gouvernement) sur quatre thèmes patrimoniaux — fiscalité, transmission, structuration, protection — sous forme de fiches sourcées, datées, classées et validées. L'outil compare, il ne classe pas. Données publiques uniquement ; aucune source antérieure au 1er septembre 2025.

## 2. Le circuit des données
- **Nuit** : GitHub Actions lit les flux RSS et presse, récupère les articles (liens Google Actualités décodés, domaines commerciaux exclus), extrait des fiches avec le modèle configuré (Gemini par défaut, repli automatique si un modèle disparaît), les valide et publie `exports/fiches_AAAA-MM-JJ.json` dans le dépôt.
- **Matin (2 min)** : la personne de permanence copie le contenu du fichier du jour et le colle dans une conversation Claude avec « Importe dans l'artefact en écartant les doublons de fond ». Claude relit, écarte les redites, écrit dans la base, rend compte. Secours : import JSON directement dans l'artefact (onglet Analyser un texte).
- **Journée** : les ingénieurs consultent, filtrent, valident (brut → vérifié → publié), exportent en CSV, analysent un texte à la main si besoin.

## 3. Utiliser l'artefact
- **Initiales** (barre latérale) : obligatoires pour enregistrer ou valider.
- **Tableau de bord** : compteurs ; comparateur des propositions (candidats × thèmes, couleur = nature dominante, chiffre = nombre de fiches ; clic sur un en-tête de thème = détail par sous-thème ; case « Vérifiées et publiées seulement » pour une vue fiable en rendez-vous client) ; dernières propositions.
- **Propositions** : filtres ; sur chaque fiche : résumé, citation, source, date, confiance, impact client, badge « auto » si produite par le pipeline ; boutons Marquer vérifiée / Publier / Retirer / Supprimer ; export CSV.
- **Analyser un texte** : coller un extrait daté → Extraire avec Claude → cocher → Enregistrer. Import JSON en bas : dédoublonnage automatique (même candidat, même source, même titre), affichage des fiches voisines (même candidat, même sous-thème) pour repérer les doublons de fond, refus des sources antérieures au 01/09/2025.
- **Référentiel** : candidats (famille politique, priorité, statut), institutions, taxonomie ; ajout d'un acteur ; bouton « Charger / mettre à jour le référentiel embarqué » après une livraison de Claude.

## 4. Règles de qualité
- Une fiche = une mesure, un acteur, une source, une date.
- Un candidat n'est jamais en nature « proposition » (réservée aux institutions).
- Confiance : élevé = source primaire ; moyen = presse fiable rapportant sans citer ; incertain = propos rapportés par un tiers, rappel de position ancienne, média non identifiable.
- Citation : verbatim exact, 25 mots maximum, sinon vide.
- Une fiche brute ne se cite pas à un client ; une fiche vérifiée a été relue source ouverte par un ingénieur.

## 5. Contrôle hebdomadaire (10 min)
GitHub → Actions : une exécution planifiée verte par nuit. Artefact → Propositions filtre Brut : relancer la validation. Tableau de bord : thèmes creux à couvrir (demander un lot à Claude). Supabase → documents : part d'ignorés ; AI Studio : quotas.

## 6. Administration
| Besoin | Où | Comment |
|---|---|---|
| Ajouter un candidat/institution | Artefact → Référentiel | Formulaire ; pour le pipeline : demander à Claude la régénération de `acteurs.csv` et `seed_referentiel.sql` |
| Modifier la taxonomie | Claude | Livraison + bouton « Charger / mettre à jour » |
| Activer un flux RSS | Supabase → sources | `robots_ok = true`, `actif = true` après vérification |
| Exclure un site | `data/domaines_exclus.txt` | Un domaine par ligne, commit |
| Changer de modèle | GitHub → Settings → Secrets and variables → Variables | `LLM_FOURNISSEUR`, `LLM_MODELE` |
| Lancer une collecte | GitHub → Actions → Run workflow | `max_docs`, `sans_collecte` |
| Sauvegarder | Artefact → export CSV ; Supabase → Backups | Hebdomadaire |

## 7. Incidents
| Symptôme | Correction |
|---|---|
| `Secret manquant` | Settings → Secrets, vérifier le nom |
| `HTTP 429` | quota : réduire `MAX_DOCS`, attendre |
| `model … no longer available` | le repli automatique essaie les modèles suivants ; sinon variable `LLM_MODELE` |
| `Unterminated string` / JSON invalide | réessai automatique avec texte raccourci ; si récurrent, signaler |
| Export absent, workflow vert | 0 fiche créée, ou permissions Actions en lecture seule |
| Pas d'exécution planifiée | GitHub retarde les crons ; deux créneaux sont configurés ; un lancement manuel dépanne |
| Fiche refusée à l'import | acteur inconnu, sous-thème hors thème, date avant 09/2025, citation > 25 mots |

## 8. Cadre
Prototype personnel sur données publiques ; aucune donnée Lazard dans GitHub, Supabase ou les conversations ; inscription RGPD à demander au DPO avant usage large ; le dépôt est le dossier d'internalisation (LazardGPT + hébergement interne).
