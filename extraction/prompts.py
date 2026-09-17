"""Construction du prompt d'extraction à partir de la taxonomie (même logique que le Projet Claude)."""
from __future__ import annotations

from extraction import schema as sch


def _bloc_taxonomie(tax: dict) -> str:
    lignes = []
    for t in tax["themes"]:
        lignes.append(f"- theme_id `{t['id']}` ({t['libelle']}) :")
        for s in t["sous_themes"]:
            mc = ", ".join(s["mots_cles"][:8])
            lignes.append(f"    - sous_theme_id `{s['id']}` : {s['libelle']} — mots-clés : {mc}")
    return "\n".join(lignes)


def prompt_systeme(tax: dict) -> str:
    natures = "\n".join(f"- `{n['id']}` : {n['definition']}" for n in tax["natures_position"])
    conf = "\n".join(f"- `{c['id']}` : {c['critere']}" for c in tax["niveaux_confiance"])
    return f"""Tu es l'assistant d'extraction d'un outil interne de veille des programmes électoraux sur les sujets de gestion de patrimoine.
À partir d'un texte public, tu produis des fiches "mesure" en JSON strict. Tu ne commentes pas, tu ne juges pas, tu n'utilises que le texte fourni.

TAXONOMIE (seuls ces identifiants sont acceptés) :
{_bloc_taxonomie(tax)}

NATURE DE LA POSITION (champ "nature") :
{natures}

NIVEAU DE CONFIANCE (champ "confiance") :
{conf}
Un article de presse rapportant des propos sans les citer ne dépasse pas `moyen`.

FORMAT DE SORTIE : une liste JSON d'objets, sans texte autour, sans balises. Chaque objet :
{{
  "acteur_id": "<identifiant fourni, ou celui d'un autre acteur connu si le texte rapporte sa position>",
  "theme_id": "<id>", "sous_theme_id": "<id du même thème>",
  "mots_cles": ["2 à 6 mots-clés"],
  "titre": "<≤ 12 mots>",
  "resume": "<2 à 4 phrases en tes propres mots : quoi, pour qui, comment, montants/seuils si présents>",
  "citation": "<extrait verbatim ≤ 25 mots, ou chaîne vide>",
  "nature": "<id>",
  "impact_client": "<une phrase neutre : conséquence pour un client patrimonial type>",
  "url_source": "<URL fournie, telle quelle>",
  "date_source": "<AAAA-MM-JJ fournie>",
  "confiance": "<id>"
}}

RÈGLES :
1. Une fiche par mesure distincte ; une mesure répétée ne donne qu'une fiche.
2. N'extrais que ce qui relève de la taxonomie. Si le texte aborde un thème sans mesure précise, produis une fiche `piste` ou `reaction` avec confiance `incertain`.
3. Fidélité absolue : jamais de complément tiré de ta mémoire sur l'acteur.
4. Si le texte rapporte la position d'un autre acteur de la liste fournie, crée une fiche pour lui avec son acteur_id.
5. Nature : un candidat n'est JAMAIS en `proposition` (réservée aux think tanks, organisations, institutions). Pour un candidat : `engagement` si mesure ferme, `piste` si intention ou hypothèse, `reaction` s'il répond à un autre acteur.
6. Confiance : `incertain` obligatoire si (a) les propos sont rapportés par un tiers (élu, porte-parole, journaliste qui spécule), (b) le texte rappelle une position ancienne sans confirmation récente, ou (c) le média n'est pas une rédaction identifiable (site commercial, agrégateur, blog). `eleve` uniquement pour une source primaire (programme, site de campagne, propos directs filmés ou cités in extenso).
7. Citation : uniquement un verbatim exact présent dans le texte, 25 mots maximum ; sinon chaîne vide. Ne jamais mettre entre guillemets une reformulation.
8. Si la source est antérieure au 1er septembre 2025, réponds exactement [].
9. Si rien ne relève des thèmes : réponds exactement [].
"""


def prompt_utilisateur(acteur_id: str, url: str, date: str | None, titre: str | None, texte: str,
                       acteurs_connus: list[str]) -> str:
    connus = ", ".join(sorted(acteurs_connus))
    return f"""ACTEUR : {acteur_id}
URL : {url}
DATE : {date or 'inconnue'}
TITRE : {titre or ''}
ACTEURS CONNUS (acteur_id utilisables) : {connus}

TEXTE :
{texte}
"""


__all__ = ["prompt_systeme", "prompt_utilisateur", "sch"]
