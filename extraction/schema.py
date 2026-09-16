"""Validation des fiches JSON produites par Claude (Projet Claude Enterprise).

Une fiche = un dictionnaire avec les champs ci-dessous. L'import accepte une fiche
seule ou une liste de fiches.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TAXONOMIE_PATH = ROOT / "data" / "taxonomie.yaml"

CHAMPS_OBLIGATOIRES = [
    "acteur_id", "theme_id", "sous_theme_id", "titre", "resume",
    "nature", "url_source", "confiance",
]
CHAMPS_OPTIONNELS = ["mots_cles", "citation", "impact_client", "date_source"]
CHAMPS_AUTORISES = set(CHAMPS_OBLIGATOIRES + CHAMPS_OPTIONNELS)

MAX_MOTS_CITATION = 25
DATE_PLANCHER = date(2025, 9, 1)   # règle de fraîcheur : aucune source antérieure à septembre 2025


def load_taxonomie() -> dict:
    with open(TAXONOMIE_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def index_taxonomie(tax: dict) -> dict:
    """Retourne des index pratiques : themes, sous_themes par thème, libellés, natures, confiances."""
    themes = {t["id"]: t["libelle"] for t in tax["themes"]}
    sous = {t["id"]: {s["id"]: s["libelle"] for s in t["sous_themes"]} for t in tax["themes"]}
    libelle_sous = {s["id"]: s["libelle"] for t in tax["themes"] for s in t["sous_themes"]}
    natures = {n["id"]: n["libelle"] for n in tax["natures_position"]}
    confiances = {c["id"]: c["libelle"] for c in tax["niveaux_confiance"]}
    return {
        "themes": themes, "sous_themes": sous, "libelle_sous": libelle_sous,
        "natures": natures, "confiances": confiances,
    }


def parse_json_fiches(texte: str) -> list[dict]:
    """Accepte du JSON brut, éventuellement entouré de ```json ... ```."""
    t = texte.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    data = json.loads(t)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Le JSON doit être une fiche (objet) ou une liste de fiches.")
    return data


def _is_url(u: str) -> bool:
    return isinstance(u, str) and re.match(r"^https?://\S+$", u) is not None


def _is_date(d: str) -> bool:
    try:
        date.fromisoformat(d)
        return True
    except Exception:
        return False


def valider_fiche(f: dict, idx: dict, acteurs_ids: set[str]) -> list[str]:
    """Retourne la liste des erreurs (vide = fiche valide)."""
    err: list[str] = []
    if not isinstance(f, dict):
        return ["La fiche n'est pas un objet JSON."]
    for c in CHAMPS_OBLIGATOIRES:
        if not f.get(c):
            err.append(f"champ obligatoire manquant : {c}")
    inconnus = set(f) - CHAMPS_AUTORISES
    if inconnus:
        err.append(f"champs non reconnus : {', '.join(sorted(inconnus))}")
    if f.get("acteur_id") and f["acteur_id"] not in acteurs_ids:
        err.append(f"acteur_id inconnu : {f['acteur_id']}")
    th, st_ = f.get("theme_id"), f.get("sous_theme_id")
    if th and th not in idx["themes"]:
        err.append(f"theme_id inconnu : {th}")
    elif th and st_ and st_ not in idx["sous_themes"].get(th, {}):
        err.append(f"sous_theme_id '{st_}' n'appartient pas au thème '{th}'")
    if f.get("nature") and f["nature"] not in idx["natures"]:
        err.append(f"nature invalide : {f['nature']}")
    if f.get("confiance") and f["confiance"] not in idx["confiances"]:
        err.append(f"confiance invalide : {f['confiance']}")
    if f.get("url_source") and not _is_url(f["url_source"]):
        err.append("url_source doit être une URL http(s)")
    if not f.get("date_source"):
        err.append("date_source obligatoire (sources à partir de septembre 2025)")
    elif not _is_date(str(f["date_source"])):
        err.append("date_source doit être au format AAAA-MM-JJ")
    elif date.fromisoformat(str(f["date_source"])) < DATE_PLANCHER:
        err.append(f"source datée du {f['date_source']} : antérieure à septembre 2025, refusée")
    if f.get("mots_cles") is not None and not isinstance(f["mots_cles"], list):
        err.append("mots_cles doit être une liste")
    cit = f.get("citation") or ""
    if len(cit.split()) > MAX_MOTS_CITATION:
        err.append(f"citation trop longue (> {MAX_MOTS_CITATION} mots)")
    return err


def normaliser_fiche(f: dict, saisi_par: str) -> dict:
    """Prépare la ligne à insérer dans la table mesures."""
    return {
        "acteur_id": f["acteur_id"],
        "theme_id": f["theme_id"],
        "sous_theme_id": f["sous_theme_id"],
        "mots_cles": f.get("mots_cles") or [],
        "titre": f["titre"].strip(),
        "resume": f["resume"].strip(),
        "citation": (f.get("citation") or "").strip() or None,
        "nature": f["nature"],
        "impact_client": (f.get("impact_client") or "").strip() or None,
        "url_source": f["url_source"].strip(),
        "date_source": f.get("date_source") or None,
        "confiance": f["confiance"],
        "statut": "brut",
        "saisi_par": saisi_par or None,
        "json_brut": f,
    }
