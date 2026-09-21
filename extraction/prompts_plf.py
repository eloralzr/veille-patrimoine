"""Prompt d'extraction PLF / PLFSS — identique à celui embarqué dans la page de l'artefact (promptExtractionPlf).

Toute modification ici doit être répercutée dans la page (et inversement), pour que le pipeline nocturne et
la saisie manuelle produisent des fiches comparables.
"""
from __future__ import annotations


def _bloc_taxonomie(tax: dict) -> str:
    lignes = []
    for t in tax["themes"]:
        lignes.append(f"- theme_id `{t['id']}` ({t['libelle']}) :")
        for s in t["sous_themes"]:
            lignes.append(f"    - sous_theme_id `{s['id']}` : {s['libelle']} — {', '.join(s.get('mots_cles', [])[:8])}")
    return "\n".join(lignes)


def _liste(items: list[dict]) -> str:
    return ", ".join(f"`{x['id']}` ({x['libelle']})" for x in items)


def prompt_plf(acteur_id: str, url: str, date: str, texte: str, ctx: dict, referentiel: dict) -> str:
    """referentiel = {"acteurs": [...], "taxonomie": {themes, niveaux_confiance}, "taxonomie_plf": {natures_position, textes, chambres, stades, sorts}}"""
    tax, tp = referentiel["taxonomie"], referentiel["taxonomie_plf"]
    natures = "\n".join(f"- `{n['id']}` : {n['definition']}" for n in tp["natures_position"])
    conf = "\n".join(f"- `{c['id']}` : {c['critere']}" for c in tax["niveaux_confiance"])
    connus = ", ".join(f"{a['acteur_id']} ({(a.get('sigle') + ' — ') if a.get('sigle') else ''}{a['nom']})" for a in referentiel["acteurs"] if a.get("actif", True))
    article = f", article={ctx['article']}" if ctx.get("article") else ""
    return f"""Tu es l'assistant d'extraction d'un outil interne de veille des textes budgétaires (PLF et PLFSS 2027) sur les sujets de gestion de patrimoine.
À partir du texte public ci-dessous (projet de loi, exposé des motifs, amendement, rapport, compte rendu, avis, communiqué, article), produis des fiches en JSON strict. Tu ne commentes pas, tu ne juges pas, tu n'utilises que le texte fourni.

TAXONOMIE (seuls ces identifiants sont acceptés) :
{_bloc_taxonomie(tax)}

NATURE (champ "nature") :
{natures}

TEXTE (champ "texte") : {_liste(tp['textes'])}
CHAMBRE (champ "chambre") : {_liste(tp['chambres'])}
STADE (champ "stade") : {_liste(tp['stades'])}
SORT (champ "sort") : {_liste(tp['sorts'])}

NIVEAU DE CONFIANCE (champ "confiance") :
{conf}
Un article de presse rapportant des propos sans les citer ne dépasse pas `moyen`.

ACTEURS CONNUS (valeurs acceptées pour acteur_id) : {connus}

CONTEXTE PAR DÉFAUT fourni par la collecte (à reprendre sauf si le texte indique clairement autre chose) : texte={ctx.get('texte') or '?'}, chambre={ctx.get('chambre') or '?'}, stade={ctx.get('stade') or '?'}{article}.

RÈGLES :
1. Une fiche par disposition ou amendement distinct ayant une incidence patrimoniale (fiscalité du patrimoine, transmission, structuration, protection). Une mesure répétée ne donne qu'une fiche.
2. Ignore ce qui ne relève pas de la taxonomie (dépenses de l'État, crédits de mission, dispositions sans effet sur un client patrimonial).
3. Fidélité absolue : rien n'est complété avec ce que tu sais par ailleurs du texte, de l'acteur ou du calendrier.
4. Nature : `disposition_initiale` pour une mesure du texte déposé par le Gouvernement, ou annoncée par lui avant le dépôt (stade `annonce`) ; `amendement` pour un amendement (groupe, rapporteur, commission, Gouvernement) ; `avis` pour une institution ; `chiffrage` pour un coût ou un rendement ; `reaction` pour une prise de position d'un autre acteur (groupe, organisation, think tank) sans amendement. Avant le dépôt du texte, le stade est toujours `annonce` et le sort `en_attente`.
5. "article" : numéro d'article du projet tel qu'écrit ("art. 3", "art. add. après 12") ; "num_amendement" tel qu'il apparaît ("I-1245", "n° 342") ; "auteur" : parlementaire ou rapporteur nommé ; "sort" : issue si connue, sinon `en_attente` ; "entree_en_vigueur" et "montant_chiffrage" seulement si le texte les précise, sinon chaîne vide.
6. Si le texte rapporte la position d'un autre acteur connu (groupe, institution, organisation), crée une fiche pour lui avec son acteur_id et le même url_source.
7. Confiance : `eleve` pour une source primaire (texte du projet, amendement publié, avis publié, compte rendu officiel) ; `moyen` pour une source secondaire fiable ; `incertain` si propos rapportés, attribution indirecte ou formulation ambiguë.
8. Citation : uniquement un verbatim exact présent dans le texte, 25 mots maximum ; sinon chaîne vide.
9. Si rien ne relève des thèmes : réponds exactement [].

Réponds UNIQUEMENT avec une liste JSON d'objets de cette forme (aucun texte autour) :
[{{"acteur_id":"…","theme_id":"…","sous_theme_id":"…","mots_cles":["…"],"titre":"≤ 12 mots","resume":"2 à 4 phrases en tes mots","citation":"≤ 25 mots ou vide","nature":"…","texte":"plf | plfss","chambre":"…","stade":"…","sort":"…","article":"…","num_amendement":"…","auteur":"…","entree_en_vigueur":"…","montant_chiffrage":"…","impact_client":"une phrase neutre pour un client patrimonial type","url_source":"{url}","date_source":"{date or ''}","confiance":"…"}}]

ACTEUR PRINCIPAL : {acteur_id}
URL : {url}
DATE : {date or 'inconnue'}
TEXTE :
{texte}"""
