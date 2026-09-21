"""Collecte presse pour la veille PLF / PLFSS 2027 — réutilise collecte/rss.py (flux Google Actualités, texte intégral
via trafilatura, exclusion de domaines), mais sans passer par la table `documents` de Supabase : les documents vont
directement au job PLF (jobs/run_collecte_plf.py), qui gère la nouveauté avec exports/.plf_sources_vues.json.

Requêtes : data/requetes_presse_plf.csv (requete_id, acteur_id, texte plf|plfss, libelle, url_rss, actif).
Avant le dépôt du texte, chaque document part avec le contexte {stade: annonce, chambre: gouvernement} ; le prompt
laisse le modèle créer des fiches `reaction` pour les autres acteurs cités (groupes, organisations, think tanks).
"""
from __future__ import annotations

import csv
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from collecte import rss
from collecte.plf import RACINE, pertinent

log = logging.getLogger("collecte.plf_presse")


def _requetes(cfg: dict) -> list[dict]:
    chemin = RACINE / cfg["presse"].get("requetes_csv", "data/requetes_presse_plf.csv")
    if not Path(chemin).exists():
        log.warning("presse PLF : %s absent", chemin)
        return []
    with open(chemin, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if str(r.get("actif", "true")).lower() == "true" and r.get("url_rss")]


def _pertinent_titre(titre: str, resume: str, mots_titre: list[str]) -> bool:
    t = f"{titre} {resume}".lower()
    return any(m.lower() in t for m in mots_titre)


def presse(cfg: dict, mots: list[str], recuperer_texte: bool = True) -> Iterable[dict]:
    pcfg = cfg["presse"]
    depuis = datetime.now(timezone.utc) - timedelta(days=int(pcfg.get("fenetre_jours", rss.FENETRE_JOURS)))
    mots_titre = pcfg.get("mots_cles_titre") or []
    exclus = rss._charger_exclus()
    vus: set[str] = set()
    stats = {"lus": 0, "hors_sujet": 0, "google_non_resolu": 0, "sans_texte": 0, "retenus": 0}
    for r in _requetes(cfg):
        est_google = "news.google.com" in r["url_rss"]
        try:
            docs = rss._lire_flux(r["url_rss"], r["acteur_id"], None, "presse", "secondaire", depuis)
        except Exception as ex:  # noqa: BLE001
            log.warning("flux presse PLF en erreur %s : %s", r["requete_id"], ex)
            continue
        time.sleep(rss.PAUSE_ENTRE_FLUX)
        for d in docs:
            if d["hash"] in vus:
                continue
            vus.add(d["hash"]); stats["lus"] += 1
            # flux généraliste d'un éditeur : on ne garde que les entrées dont le titre/résumé parle du budget
            if not est_google and mots_titre and not _pertinent_titre(d.get("titre", ""), d.get("texte", ""), mots_titre):
                stats["hors_sujet"] += 1; continue
            url_finale = rss.resoudre_url(d["url"]) if est_google else d["url"]
            if "news.google.com" in url_finale:
                # lien Google non décodé : la page Google ne contient pas l'article ; on n'envoie rien au LLM
                stats["google_non_resolu"] += 1
                log.info("lien Google Actualités non résolu, ignoré : %s", d.get("titre", "")[:80]); continue
            texte = d["texte"] or ""
            if recuperer_texte:
                txt, uf = rss._texte_article(url_finale)
                if txt and len(txt) > len(texte):
                    texte = txt
                url_finale = uf or url_finale
                time.sleep(0.5)
            if rss.domaine_exclu(url_finale, exclus):
                continue
            texte = texte[: rss.TEXTE_MAX]
            if not pertinent(texte, mots, cfg["filtre"]["mots_cles_minimum"], cfg["filtre"]["longueur_minimum_texte"]):
                stats["sans_texte"] += 1; continue
            stats["retenus"] += 1
            yield {
                "source_id": "presse-" + d["hash"][:16],
                "acteur_id": r["acteur_id"],
                "url": url_finale,
                "date": d["date_publication"] or datetime.now(timezone.utc).date().isoformat(),
                "texte": f"{d['titre']}\n\n{texte}" if d.get("titre") else texte,
                "contexte": {"texte": r.get("texte") or "plf", "chambre": pcfg.get("chambre_par_defaut", "gouvernement"),
                             "stade": pcfg.get("stade_par_defaut", "annonce"), "article": "", "num_amendement": "", "auteur": "", "sort": "en_attente"},
            }
    log.info("presse PLF : %s", stats)
    if stats["google_non_resolu"] and not stats["retenus"]:
        log.warning("aucun lien Google Actualités décodé : vérifier la version de googlenewsdecoder (pip install -U googlenewsdecoder) ; les flux d'éditeurs prennent le relais")
