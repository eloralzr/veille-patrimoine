"""Collecte RSS : flux des acteurs (table sources) + flux presse Google Actualités (data/requetes_presse.csv).

Chaque entrée nouvelle devient une ligne de la table documents (statut 'a_traiter').
Le texte complet de l'article est récupéré quand c'est possible (trafilatura) ; sinon on garde le résumé du flux.
"""
from __future__ import annotations

import csv
import hashlib
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

from db import supa

log = logging.getLogger("collecte.rss")

ROOT = Path(__file__).resolve().parents[1]
REQUETES_PRESSE = ROOT / "data" / "requetes_presse.csv"

UA = "veille-patrimoine/0.7 (+veille programmes electoraux; contact via depot GitHub)"
TIMEOUT = 20
FENETRE_JOURS = 7          # on ignore les entrées plus anciennes
MAX_PAR_FLUX = 25
TEXTE_MAX = 12000          # caractères conservés par document
PAUSE_ENTRE_FLUX = 1.0     # politesse


def _hash(url: str) -> str:
    u = url.strip().lower()
    u = re.sub(r"[?#].*$", "", u)           # on retire les paramètres de suivi
    u = re.sub(r"/+$", "", u)
    return hashlib.sha256(u.encode("utf-8")).hexdigest()


def _date_entree(e) -> datetime | None:
    for k in ("published_parsed", "updated_parsed"):
        t = getattr(e, k, None) or e.get(k)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _texte_article(url: str) -> tuple[str, str | None]:
    """Retourne (texte, url_finale). Texte vide si échec."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            return "", r.url
        try:
            import trafilatura
            txt = trafilatura.extract(r.text, include_comments=False, include_tables=False,
                                      favor_precision=True) or ""
        except Exception:
            txt = ""
        return txt.strip(), r.url
    except Exception as ex:
        log.debug("fetch échoué %s : %s", url, ex)
        return "", None


def _nettoyer_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def _lire_flux(url_flux: str, acteur_id: str, source_id: str | None, source_type: str,
               fiabilite: str, depuis: datetime) -> list[dict]:
    fp = feedparser.parse(url_flux, request_headers={"User-Agent": UA})
    if getattr(fp, "bozo", 0) and not fp.entries:
        log.warning("flux illisible %s (%s)", url_flux, getattr(fp, "bozo_exception", ""))
        return []
    docs: list[dict] = []
    for e in fp.entries[:MAX_PAR_FLUX]:
        lien = e.get("link")
        if not lien:
            continue
        d = _date_entree(e)
        if d and d < depuis:
            continue
        resume = _nettoyer_html(e.get("summary", "") or (e.get("content") or [{}])[0].get("value", ""))
        docs.append({
            "acteur_id": acteur_id,
            "source_id": source_id,
            "source_type": source_type,
            "url": lien,
            "titre": _nettoyer_html(e.get("title", ""))[:300],
            "date_publication": d.date().isoformat() if d else None,
            "texte": resume,                     # complété plus bas si l'article est récupérable
            "hash": _hash(lien),
            "statut": "a_traiter",
            "_fiabilite": fiabilite,
        })
    return docs


def _charger_requetes_presse() -> list[dict]:
    if not REQUETES_PRESSE.exists():
        return []
    with open(REQUETES_PRESSE, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("actif", "true").lower() == "true" and r.get("url_rss")]


def collecter(acteurs_valides: set[str], recuperer_texte: bool = True) -> dict:
    """Lit tous les flux actifs, insère les nouveaux documents. Retourne des compteurs."""
    depuis = datetime.now(timezone.utc) - timedelta(days=FENETRE_JOURS)
    flux: list[tuple[str, str, str | None, str, str]] = []  # (url, acteur_id, source_id, source_type, fiabilite)

    for s in supa.sources_actives("rss"):
        if s.get("url") and s["acteur_id"] in acteurs_valides:
            flux.append((s["url"], s["acteur_id"], s["source_id"], "rss", s.get("fiabilite") or "primaire"))
    for r in _charger_requetes_presse():
        if r["acteur_id"] in acteurs_valides:
            flux.append((r["url_rss"], r["acteur_id"], None, "presse", "secondaire"))

    stats = {"flux_lus": 0, "docs_vus": 0, "docs_nouveaux": 0, "flux_en_erreur": 0}
    candidats: list[dict] = []
    for url, acteur_id, source_id, source_type, fiab in flux:
        try:
            docs = _lire_flux(url, acteur_id, source_id, source_type, fiab, depuis)
            stats["flux_lus"] += 1
            stats["docs_vus"] += len(docs)
            candidats.extend(docs)
        except Exception as ex:
            stats["flux_en_erreur"] += 1
            log.warning("erreur flux %s : %s", url, ex)
        time.sleep(PAUSE_ENTRE_FLUX)

    # dédoublonnage : dans le lot, puis contre la base
    vus: dict[str, dict] = {}
    for d in candidats:
        vus.setdefault(d["hash"], d)
    existants = supa.hashes_existants(list(vus))
    nouveaux = [d for h, d in vus.items() if h not in existants]

    for d in nouveaux:
        if recuperer_texte:
            txt, url_finale = _texte_article(d["url"])
            if txt and len(txt) > len(d["texte"]):
                d["texte"] = txt
            d["url_finale"] = url_finale
            time.sleep(0.5)
        d["texte"] = (d["texte"] or "")[:TEXTE_MAX]
        d.pop("_fiabilite", None)

    stats["docs_nouveaux"] = supa.inserer_documents(nouveaux)
    log.info("collecte : %s", stats)
    return stats
