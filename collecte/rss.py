"""Collecte RSS : flux des acteurs (table sources) + flux presse (data/requetes_presse.csv).

Chaque entrée nouvelle devient une ligne de la table documents (statut 'a_traiter').
Le texte complet de l'article est récupéré quand c'est possible (trafilatura) ; sinon on garde le résumé du flux.

Flux de presse généraux (ex. rubrique Politique d'un éditeur) : dans requetes_presse.csv, acteur_id = "*".
L'acteur est alors détecté dans le titre et le résumé (data/alias_acteurs.csv), et l'entrée n'est gardée que si
elle cite un acteur connu ET un mot-clé patrimonial (taxonomie), en mots entiers.
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
DOMAINES_EXCLUS = ROOT / "data" / "domaines_exclus.txt"
ALIAS_ACTEURS = ROOT / "data" / "alias_acteurs.csv"
TAXONOMIE = ROOT / "data" / "taxonomie.yaml"
ACTEUR_A_DETECTER = "*"
MOTS_GENERAUX = ["patrimoine", "fiscalité", "impôt", "impôts", "taxe", "héritage", "succession", "successions",
                 "donation", "donations", "retraite", "retraites", "épargne"]


def _charger_exclus() -> set[str]:
    if not DOMAINES_EXCLUS.exists():
        return set()
    return {l.strip().lower() for l in DOMAINES_EXCLUS.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


def _domaine(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return (m.group(1).lower().removeprefix("www.") if m else "")


def domaine_exclu(url: str, exclus: set[str]) -> bool:
    d = _domaine(url)
    return any(d == e or d.endswith("." + e) for e in exclus)

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


def resoudre_url(url: str) -> str:
    """Les liens des flux Google Actualités (news.google.com/rss/articles/...) sont encodés :
    on les décode pour obtenir l'URL réelle de l'article. Retourne l'URL d'origine si le décodage échoue."""
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        res = gnewsdecoder(url, interval=1)
        if isinstance(res, dict) and (res.get("status") or res.get("success")) and res.get("decoded_url"):
            return res["decoded_url"]
        log.warning("décodage Google News refusé %s : %s", url[:80], str((res or {}).get("message", ""))[:200])
    except Exception as ex:
        log.warning("décodage Google News échoué %s : %s", url[:80], ex)
    return url


UA_NAVIGATEUR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 veille-patrimoine/0.8")


def _texte_article(url: str) -> tuple[str, str | None]:
    """Retourne (texte, url_finale). Texte vide si échec. Résout d'abord les liens Google Actualités."""
    cible = resoudre_url(url)
    if "news.google.com" in cible:      # décodage échoué : inutile de télécharger la page Google
        return "", None
    try:
        r = requests.get(cible, headers={"User-Agent": UA_NAVIGATEUR, "Accept-Language": "fr-FR,fr;q=0.9"},
                         timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            return "", r.url
        txt = ""
        try:
            import trafilatura
            txt = trafilatura.extract(r.text, include_comments=False, include_tables=False,
                                      favor_precision=False) or ""
        except Exception:
            txt = ""
        if not txt:  # repli grossier : texte des paragraphes
            paras = re.findall(r"<p[^>]*>(.*?)</p>", r.text, flags=re.S | re.I)
            txt = " ".join(_nettoyer_html(p) for p in paras if len(_nettoyer_html(p)) > 60)
        return txt.strip(), r.url
    except Exception as ex:
        log.warning("fetch échoué %s : %s", cible[:80], ex)
        return "", cible if cible != url else None


def _nettoyer_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- flux généraux : détection de l'acteur

def _charger_alias(acteurs_valides: set[str]) -> list[tuple[str, str]]:
    if not ALIAS_ACTEURS.exists():
        log.warning("alias des acteurs absent (%s) : les flux généraux seront ignorés", ALIAS_ACTEURS)
        return []
    with open(ALIAS_ACTEURS, encoding="utf-8", newline="") as f:
        return [(r["acteur_id"].strip(), r["alias"].strip()) for r in csv.DictReader(f)
                if (r.get("alias") or "").strip() and (r.get("acteur_id") or "").strip() in acteurs_valides]


def _motif(mots: list[str]):
    mots = sorted({m.strip() for m in mots if m and m.strip()}, key=len, reverse=True)
    if not mots:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(m) for m in mots) + r")(?!\w)", re.I)


def _motif_patrimoine():
    mots = list(MOTS_GENERAUX)
    try:
        import yaml
        tax = yaml.safe_load(TAXONOMIE.read_text(encoding="utf-8"))
        for th in tax.get("themes", []):
            for st in th.get("sous_themes", []):
                mots.extend(st.get("mots_cles", []))
    except Exception as ex:
        log.warning("taxonomie illisible pour le filtre presse : %s", ex)
    return _motif(mots)


def _detecter_acteur(texte: str, alias: list[tuple[str, str]]) -> str | None:
    """Acteur le plus cité (en mots entiers) dans le texte, ou None."""
    comptes: dict[str, int] = {}
    for acteur_id, a in alias:
        n = len(re.findall(r"(?<!\w)" + re.escape(a) + r"(?!\w)", texte, flags=re.I))
        if n:
            comptes[acteur_id] = comptes.get(acteur_id, 0) + n
    return max(comptes, key=comptes.get) if comptes else None


def _attribuer(docs: list[dict], alias, motif_pat, stats: dict) -> list[dict]:
    gardes = []
    for d in docs:
        t = f"{d.get('titre', '')} {d.get('texte', '')}"
        acteur = _detecter_acteur(t, alias)
        if not acteur or not motif_pat or not motif_pat.search(t):
            stats["docs_hors_sujet"] = stats.get("docs_hors_sujet", 0) + 1
            continue
        d["acteur_id"] = acteur
        gardes.append(d)
    return gardes


# ---------------------------------------------------------------- lecture des flux

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
        if r["acteur_id"] == ACTEUR_A_DETECTER:
            flux.append((r["url_rss"], ACTEUR_A_DETECTER, None, "presse", "secondaire"))
        elif r["acteur_id"] in acteurs_valides:
            flux.append((r["url_rss"], r["acteur_id"], None, "presse", "secondaire"))

    alias = _charger_alias(acteurs_valides)
    motif_pat = _motif_patrimoine()
    stats = {"flux_lus": 0, "docs_vus": 0, "docs_nouveaux": 0, "flux_en_erreur": 0, "docs_hors_sujet": 0}
    candidats: list[dict] = []
    for url, acteur_id, source_id, source_type, fiab in flux:
        try:
            docs = _lire_flux(url, acteur_id, source_id, source_type, fiab, depuis)
            stats["flux_lus"] += 1
            if acteur_id == ACTEUR_A_DETECTER:
                docs = _attribuer(docs, alias, motif_pat, stats)
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

    exclus = _charger_exclus()
    retenus: list[dict] = []
    for d in nouveaux:
        if recuperer_texte:
            txt, url_finale = _texte_article(d["url"])
            if txt and len(txt) > len(d["texte"]):
                d["texte"] = txt
            d["url_finale"] = url_finale
            time.sleep(0.5)
        cible = d.get("url_finale") or d["url"]
        if domaine_exclu(cible, exclus):
            stats["docs_exclus"] = stats.get("docs_exclus", 0) + 1
            log.info("domaine exclu : %s", _domaine(cible))
            continue
        d["texte"] = (d["texte"] or "")[:TEXTE_MAX]
        d.pop("_fiabilite", None)
        retenus.append(d)

    stats["docs_nouveaux"] = supa.inserer_documents(retenus)
    log.info("collecte : %s", stats)
    return stats
