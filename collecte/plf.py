"""Collecte des documents source PLF / PLFSS 2027.

Produit une liste de « documents » homogènes, prêts pour l'extraction LLM :
    {
      "source_id":  identifiant stable (dédoublonnage entre exécutions),
      "acteur_id":  acteur du référentiel PLF (data/acteurs_plf.csv),
      "url":        URL publique de la source,
      "date":       AAAA-MM-JJ,
      "texte":      texte à analyser (dispositif + exposé, ou extrait),
      "contexte":   {"texte": plf|plfss, "chambre": ..., "stade": ..., "article": ..., "num_amendement": ..., "auteur": ..., "sort": ...}
    }

Quatre collecteurs :
  - presse (collecte/plf_presse.py) : flux Google Actualités PLF/PLFSS via collecte/rss.py — actif dès aujourd'hui ;
  - amendements_an()   : données ouvertes de l'Assemblée nationale (JSON zippé) — le cœur du dispositif après le dépôt ;
  - texte_initial()    : articles du projet de loi et exposé des motifs, depuis un PDF ou une page HTML configurés ;
  - amendements_senat(): pages HTML de liste des amendements du Sénat (phase 1 ; le dump Ameli est la phase 2).

Toutes les adresses viennent de data/sources_plf.yaml. Les structures JSON de l'AN sont lues de façon
défensive (chaînes de .get) : après la première exécution réelle, vérifier les champs sur un échantillon
(voir README-CHANTIER-PLF.md, étape 3) et ajuster les fonctions _champ_* ci-dessous si besoin.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Iterable

import requests
import yaml

log = logging.getLogger("collecte.plf")
RACINE = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- utilitaires

def charger_sources(chemin: Path | None = None) -> dict:
    return yaml.safe_load((chemin or RACINE / "data" / "sources_plf.yaml").read_text(encoding="utf-8"))


def mots_cles_taxonomie(chemin: Path | None = None) -> list[str]:
    tax = yaml.safe_load((chemin or RACINE / "data" / "taxonomie.yaml").read_text(encoding="utf-8"))
    mots = []
    for th in tax["themes"]:
        for st in th["sous_themes"]:
            mots.extend(st.get("mots_cles", []))
    return sorted(set(m.lower() for m in mots))


def pertinent(texte: str, mots: list[str], minimum: int = 1, longueur_min: int = 120) -> bool:
    """Filtre grossier avant appel LLM : longueur et présence de mots-clés patrimoniaux."""
    if not texte or len(texte) < longueur_min:
        return False
    t = texte.lower()
    return sum(1 for m in mots if m in t) >= minimum


def source_id(*parts: str) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def _nettoyer_html(html: str) -> str:
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", txt, flags=re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n", txt).strip()


def _telecharger(url: str, timeout: int = 120) -> bytes:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "veille-patrimoine/plf (interne)"})
    r.raise_for_status()
    return r.content


# ---------------------------------------------------------------- Assemblée nationale : amendements (données ouvertes)

def _premier(d: dict, *chemins: str):
    """Renvoie la première valeur non vide trouvée parmi des chemins 'a.b.c'."""
    for ch in chemins:
        cur = d
        for k in ch.split("."):
            if isinstance(cur, dict):
                cur = cur.get(k)
            else:
                cur = None
                break
        if cur not in (None, "", [], {}):
            return cur
    return None


def _texte_amendement(am: dict) -> str:
    dispositif = _premier(am, "corps.dispositif", "dispositif") or ""
    expose = _premier(am, "corps.exposeSommaire", "exposeSommaire") or ""
    return _nettoyer_html(f"{dispositif}\n\nExposé sommaire :\n{expose}")


def _acteur_amendement(am: dict, cfg_an: dict) -> str | None:
    aut = _premier(am, "signataires.auteur", "auteur") or {}
    type_auteur = (aut.get("typeAuteur") or "").lower()
    if "gouvernement" in type_auteur:
        return cfg_an.get("auteur_gouvernement")
    if "commission" in type_auteur:
        org = (str(aut.get("organeRef") or "") + str(aut.get("libelle") or "")).lower()
        if "social" in org:
            return cfg_an.get("auteur_commission_affaires_sociales")
        return cfg_an.get("auteur_commission_finances")
    grp = aut.get("groupePolitiqueRef") or _premier(am, "signataires.auteur.groupePolitique.ref")
    return cfg_an.get("groupes", {}).get(grp)


def _stade_amendement(am: dict) -> str:
    etat = (str(_premier(am, "cycleDeVie.etatDesTraitements.etat.libelle", "cycleDeVie.etat", "etat") or "")).lower()
    examen = (str(_premier(am, "examenRef", "identification.examenRef") or "")).lower()
    if "commission" in etat or "commission" in examen or examen.startswith("ex_com"):
        return "commission"
    if "séance" in etat or "seance" in etat or "discut" in etat or "adopt" in etat or "rejet" in etat:
        return "seance"
    return "depose"


def _sort_amendement(am: dict) -> str:
    sort = (str(_premier(am, "cycleDeVie.sort.sortEnSeance", "cycleDeVie.sort.libelle", "sort") or "")).lower()
    for motif, code in (("adopt", "adopte"), ("rejet", "rejete"), ("retir", "retire"), ("tomb", "tombe"), ("non soutenu", "non_soutenu"), ("irrecev", "sans_objet")):
        if motif in sort:
            return code
    return "en_attente"


def _date_amendement(am: dict) -> str:
    d = _premier(am, "cycleDeVie.dateDepot", "dateDepot", "cycleDeVie.dateSort") or date.today().isoformat()
    return str(d)[:10]


def amendements_an(cfg: dict, mots: list[str], texte_loi: str = "plf") -> Iterable[dict]:
    """Lit le zip JSON des amendements de l'AN et retient ceux du dossier PLF/PLFSS configuré."""
    cfg_an = cfg["assemblee_nationale"]
    dossier = cfg["dossiers"][texte_loi]
    refs_textes = set(dossier.get("an_texte_refs") or [])
    ref_dossier = dossier.get("an_dossier_ref") or ""
    if not refs_textes and not ref_dossier:
        log.warning("Dossier %s : aucun identifiant AN renseigné dans sources_plf.yaml — collecte AN sautée", texte_loi)
        return
    data = _telecharger(cfg_an["amendements_zip"])
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        noms = [n for n in z.namelist() if n.endswith(".json")]
        log.info("AN : %d fichiers JSON dans l'archive", len(noms))
        for nom in noms:
            try:
                obj = json.loads(z.read(nom).decode("utf-8"))
            except Exception as e:  # noqa: BLE001
                log.debug("JSON illisible %s : %s", nom, e)
                continue
            am = obj.get("amendement", obj)
            texte_ref = str(_premier(am, "texteLegislatifRef", "identification.texteLegislatifRef") or "")
            dossier_ref = str(_premier(am, "dossierRef", "identification.dossierRef") or "")
            if texte_ref not in refs_textes and (not ref_dossier or ref_dossier not in dossier_ref):
                continue
            texte = _texte_amendement(am)
            if not pertinent(texte, mots, cfg["filtre"]["mots_cles_minimum"], cfg["filtre"]["longueur_minimum_texte"]):
                continue
            acteur = _acteur_amendement(am, cfg_an)
            if not acteur:
                log.debug("Amendement sans acteur reconnu : %s", nom)
                continue
            uid = str(_premier(am, "uid", "identification.uid") or nom)
            numero = str(_premier(am, "identification.numeroLong", "identification.numeroOrdreDepot", "numero") or "")
            article = str(_premier(am, "pointeurFragmentTexte.division.titre", "pointeurFragmentTexte.division.articleDesignationCourte", "division") or "")
            auteur = _premier(am, "signataires.auteur.nom", "signataires.auteur.libelle") or ""
            url = _premier(am, "urlAmendement", "identification.url") or (dossier.get("page_an") or "")
            yield {
                "source_id": source_id("an", uid),
                "acteur_id": acteur,
                "url": url,
                "date": _date_amendement(am),
                "texte": texte,
                "contexte": {"texte": texte_loi, "chambre": "an", "stade": _stade_amendement(am), "article": article,
                             "num_amendement": numero, "auteur": str(auteur), "sort": _sort_amendement(am)},
            }


# ---------------------------------------------------------------- texte initial (Gouvernement)

_RE_ARTICLE = re.compile(r"^\s*Article\s+(\d+[\s\w]*)\s*$", re.M)


def texte_initial(cfg: dict, mots: list[str], texte_loi: str = "plf", url: str | None = None, chemin_local: Path | None = None) -> Iterable[dict]:
    """Découpe le projet de loi (texte + exposé des motifs) article par article.

    Source : `url` (HTML ou PDF) ou `chemin_local` (PDF déposé à la main dans data/textes/). Pour un PDF,
    pdfplumber ou pypdf doit être installé ; le texte est ensuite découpé sur les intitulés « Article N ».
    """
    if chemin_local:
        contenu = chemin_local.read_bytes()
        url = url or cfg["dossiers"][texte_loi].get("page_gouv", "")
    elif url:
        contenu = _telecharger(url)
    else:
        log.warning("Texte initial %s : ni URL ni fichier local — sauté", texte_loi)
        return
    if contenu[:4] == b"%PDF":
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(io.BytesIO(contenu)) as pdf:
                brut = "\n".join((p.extract_text() or "") for p in pdf.pages)
        except ImportError:
            from pypdf import PdfReader  # type: ignore
            brut = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(contenu)).pages)
    else:
        brut = _nettoyer_html(contenu.decode("utf-8", errors="replace"))
    positions = [(m.start(), m.group(1).strip()) for m in _RE_ARTICLE.finditer(brut)]
    for i, (debut, num) in enumerate(positions):
        fin = positions[i + 1][0] if i + 1 < len(positions) else len(brut)
        morceau = brut[debut:fin].strip()
        if not pertinent(morceau, mots, cfg["filtre"]["mots_cles_minimum"], cfg["filtre"]["longueur_minimum_texte"]):
            continue
        yield {
            "source_id": source_id("gouv", texte_loi, num),
            "acteur_id": cfg["assemblee_nationale"]["auteur_gouvernement"],
            "url": url,
            "date": date.today().isoformat(),
            "texte": morceau[:20000],
            "contexte": {"texte": texte_loi, "chambre": "gouvernement", "stade": "texte_initial", "article": f"art. {num}",
                         "num_amendement": "", "auteur": "Gouvernement", "sort": "en_attente"},
        }


# ---------------------------------------------------------------- Sénat : pages HTML de liste (phase 1)

def amendements_senat(cfg: dict, mots: list[str], texte_loi: str = "plf", urls_listes: list[str] | None = None) -> Iterable[dict]:
    """Phase 1 : lit des pages HTML de liste d'amendements du Sénat données en configuration ou en paramètre.

    Chaque page est nettoyée et découpée par amendement sur le motif « N° … » ; le groupe est reconnu par son
    sigle (cfg['senat']['groupes']). Approche volontairement simple : la phase 2 remplace ce collecteur par une
    lecture du dump Ameli (data.senat.fr), plus fiable pour le sort et le stade.
    """
    urls = urls_listes or cfg["dossiers"][texte_loi].get("senat_listes_amendements") or []
    if not urls:
        log.info("Sénat : aucune page de liste configurée pour %s", texte_loi)
        return
    grp = cfg["senat"]["groupes"]
    for url in urls:
        html = _telecharger(url).decode("utf-8", errors="replace")
        texte = _nettoyer_html(html)
        blocs = re.split(r"\n(?=N°\s*[\w-]+)", texte)
        for bloc in blocs:
            m = re.match(r"N°\s*([\w-]+)", bloc)
            if not m or not pertinent(bloc, mots, cfg["filtre"]["mots_cles_minimum"], cfg["filtre"]["longueur_minimum_texte"]):
                continue
            acteur = next((aid for sigle, aid in grp.items() if sigle.lower() in bloc.lower()), None)
            if "gouvernement" in bloc.lower()[:400]:
                acteur = cfg["assemblee_nationale"]["auteur_gouvernement"]
            if not acteur:
                continue
            article = (re.search(r"(Article\s+\S+(?:\s*\(nouveau\))?|art\.\s*\S+)", bloc, re.I) or [None, ""])[1] if re.search(r"Article\s+\S+|art\.\s*\S+", bloc, re.I) else ""
            yield {
                "source_id": source_id("senat", url, m.group(1)),
                "acteur_id": acteur,
                "url": url,
                "date": date.today().isoformat(),
                "texte": bloc[:20000],
                "contexte": {"texte": texte_loi, "chambre": "senat", "stade": "depose", "article": article,
                             "num_amendement": m.group(1), "auteur": "", "sort": "en_attente"},
            }


# ---------------------------------------------------------------- point d'entrée

def collecter(cfg: dict | None = None, textes: tuple[str, ...] = ("plf", "plfss")) -> list[dict]:
    cfg = cfg or charger_sources()
    mots = mots_cles_taxonomie()
    docs: list[dict] = []
    for t in textes:
        for collecteur in (amendements_an, amendements_senat):
            try:
                docs.extend(collecteur(cfg, mots, t))
            except Exception as e:  # noqa: BLE001 — une source en panne ne bloque pas les autres
                log.error("%s (%s) : %s", collecteur.__name__, t, e)
        try:
            page = cfg["dossiers"][t].get("texte_initial_url")
            local = cfg["dossiers"][t].get("texte_initial_pdf")
            docs.extend(texte_initial(cfg, mots, t, url=page, chemin_local=RACINE / local if local else None))
        except Exception as e:  # noqa: BLE001
            log.error("texte_initial (%s) : %s", t, e)
    # presse (flux Google Actualités) : réutilise collecte/rss.py ; disponible dès aujourd'hui, avant le dépôt du texte
    if cfg.get("presse", {}).get("requetes_csv"):
        try:
            from collecte.plf_presse import presse
            docs.extend(presse(cfg, mots))
        except Exception as e:  # noqa: BLE001
            log.error("presse PLF : %s", e)
    vus, uniques = set(), []
    for d in docs:
        if d["source_id"] in vus:
            continue
        vus.add(d["source_id"]); uniques.append(d)
    log.info("PLF/PLFSS : %d documents collectés (%d avant dédoublonnage)", len(uniques), len(docs))
    return uniques
