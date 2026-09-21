"""Validation et normalisation des fiches PLF / PLFSS — miroir de `valider()` / `normaliser()` de la page de l'artefact.

Une fiche refusée ici serait refusée à l'import dans l'artefact ; autant l'écarter (et la journaliser) dès le pipeline.
"""
from __future__ import annotations

import csv
import re
from datetime import date, datetime
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]
DATE_PLANCHER = date(2025, 9, 1)

CHAMPS_OBL = ["acteur_id", "theme_id", "sous_theme_id", "titre", "resume", "nature", "url_source", "confiance", "texte", "stade"]
CHAMPS_OPT = ["mots_cles", "citation", "impact_client", "date_source", "statut", "saisi_par", "valide_par", "cree_le", "maj_le", "id",
              "article", "num_amendement", "chambre", "sort", "auteur", "entree_en_vigueur", "montant_chiffrage", "mesure_parent_id", "programme_lie_id"]


def charger_referentiel(data: Path | None = None) -> dict:
    """Assemble le référentiel PLF à partir de data/ : acteurs_plf.csv + taxonomie.yaml (thèmes) + taxonomie_plf.yaml."""
    data = data or RACINE / "data"
    with (data / "acteurs_plf.csv").open(encoding="utf-8", newline="") as f:
        acteurs = [{**r, "actif": str(r.get("actif", "True")).lower() == "true"} for r in csv.DictReader(f)]
    # les think tanks / organisations du référentiel principal sont acceptés aussi (réactions, chiffrages)
    with (data / "acteurs.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("type") != "candidat" and str(r.get("actif", "True")).lower() == "true":
                acteurs.append({"acteur_id": r["acteur_id"], "nom": r["nom"], "sigle": "", "type": r["type"], "chambre": "na", "actif": True})
    tax = yaml.safe_load((data / "taxonomie.yaml").read_text(encoding="utf-8"))
    tp = yaml.safe_load((data / "taxonomie_plf.yaml").read_text(encoding="utf-8"))
    return {"acteurs": acteurs, "taxonomie": tax, "taxonomie_plf": tp}


def indexer(ref: dict) -> dict:
    tax, tp = ref["taxonomie"], ref["taxonomie_plf"]
    sous_par_theme = {t["id"]: {s["id"] for s in t["sous_themes"]} for t in tax["themes"]}
    return {
        "acteurs": {a["acteur_id"] for a in ref["acteurs"] if a.get("actif", True)},
        "themes": set(sous_par_theme), "sous_par_theme": sous_par_theme,
        "natures": {n["id"] for n in tp["natures_position"]},
        "confiances": {c["id"] for c in tax["niveaux_confiance"]},
        "textes": {x["id"] for x in tp["textes"]}, "chambres": {x["id"] for x in tp["chambres"]},
        "stades": {x["id"] for x in tp["stades"]}, "sorts": {x["id"] for x in tp["sorts"]},
    }


def valider(f: dict, idx: dict) -> list[str]:
    if not isinstance(f, dict):
        return ["La fiche n'est pas un objet JSON."]
    err = [f"champ obligatoire manquant : {c}" for c in CHAMPS_OBL if not f.get(c)]
    inconnus = [k for k in f if k not in CHAMPS_OBL and k not in CHAMPS_OPT]
    if inconnus:
        err.append("champs non reconnus : " + ", ".join(inconnus))
    if f.get("acteur_id") and f["acteur_id"] not in idx["acteurs"]:
        err.append(f"acteur_id inconnu : {f['acteur_id']}")
    if f.get("theme_id") and f["theme_id"] not in idx["themes"]:
        err.append(f"theme_id inconnu : {f['theme_id']}")
    elif f.get("theme_id") and f.get("sous_theme_id") and f["sous_theme_id"] not in idx["sous_par_theme"][f["theme_id"]]:
        err.append(f"sous_theme_id '{f['sous_theme_id']}' n'appartient pas au thème '{f['theme_id']}'")
    for champ, cle in (("nature", "natures"), ("confiance", "confiances"), ("texte", "textes"), ("stade", "stades"), ("chambre", "chambres"), ("sort", "sorts")):
        if f.get(champ) and f[champ] not in idx[cle]:
            err.append(f"{champ} invalide : {f[champ]}")
    if f.get("url_source") and not re.match(r"^https?://\S+$", str(f["url_source"])):
        err.append("url_source doit être une URL http(s)")
    ds = f.get("date_source")
    if not ds:
        err.append("date_source obligatoire")
    else:
        try:
            if datetime.strptime(str(ds)[:10], "%Y-%m-%d").date() < DATE_PLANCHER:
                err.append(f"source datée du {ds} : antérieure à septembre 2025, refusée")
        except ValueError:
            err.append("date_source doit être au format AAAA-MM-JJ")
    if f.get("mots_cles") is not None and not isinstance(f["mots_cles"], list):
        err.append("mots_cles doit être une liste")
    if len(str(f.get("citation") or "").split()) > 25:
        err.append("citation trop longue (> 25 mots)")
    return err


def normaliser(f: dict, *, id_fiche: str, saisi_par: str, horodatage: str) -> dict:
    """Fiche au format attendu par l'import de l'artefact (collection mesures_plf, statut brut)."""
    txt = lambda k: (str(f.get(k) or "").strip() or None)  # noqa: E731
    return {
        "id": id_fiche, "acteur_id": f["acteur_id"], "theme_id": f["theme_id"], "sous_theme_id": f["sous_theme_id"],
        "mots_cles": [str(m) for m in (f.get("mots_cles") or [])][:8],
        "titre": str(f["titre"]).strip(), "resume": str(f["resume"]).strip(), "citation": txt("citation"), "nature": f["nature"],
        "impact_client": txt("impact_client"), "url_source": str(f["url_source"]).strip(), "date_source": str(f.get("date_source"))[:10], "confiance": f["confiance"],
        "texte": f["texte"], "stade": f["stade"], "chambre": f.get("chambre") or None, "sort": f.get("sort") or "en_attente",
        "article": txt("article"), "num_amendement": txt("num_amendement"), "auteur": txt("auteur"),
        "entree_en_vigueur": txt("entree_en_vigueur"), "montant_chiffrage": txt("montant_chiffrage"),
        "mesure_parent_id": f.get("mesure_parent_id") or None, "programme_lie_id": f.get("programme_lie_id") or None,
        "statut": "brut", "saisi_par": saisi_par, "valide_par": None, "cree_le": horodatage, "maj_le": horodatage,
    }
