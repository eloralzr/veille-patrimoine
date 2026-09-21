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


def presse(cfg: dict, mots: list[str], recuperer_texte: bool = True) -> Iterable[dict]:
    pcfg = cfg["presse"]
    depuis = datetime.now(timezone.utc) - timedelta(days=int(pcfg.get("fenetre_jours", rss.FENETRE_JOURS)))
    exclus = rss._charger_exclus()
    vus: set[str] = set()
    for r in _requetes(cfg):
        try:
            docs = rss._lire_flux(r["url_rss"], r["acteur_id"], None, "presse", "secondaire", depuis)
        except Exception as ex:  # noqa: BLE001
            log.warning("flux presse PLF en erreur %s : %s", r["requete_id"], ex)
            continue
        time.sleep(rss.PAUSE_ENTRE_FLUX)
        for d in docs:
            if d["hash"] in vus:
                continue
            vus.add(d["hash"])
            texte = d["texte"] or ""
            url_finale = d["url"]
            if recuperer_texte:
                txt, uf = rss._texte_article(d["url"])
                if txt and len(txt) > len(texte):
                    texte = txt
                url_finale = uf or d["url"]
                time.sleep(0.5)
            if rss.domaine_exclu(url_finale, exclus):
                continue
            texte = texte[: rss.TEXTE_MAX]
            if not pertinent(texte, mots, cfg["filtre"]["mots_cles_minimum"], cfg["filtre"]["longueur_minimum_texte"]):
                continue
            yield {
                "source_id": "presse-" + d["hash"][:16],
                "acteur_id": r["acteur_id"],
                "url": url_finale,
                "date": d["date_publication"] or datetime.now(timezone.utc).date().isoformat(),
                "texte": f"{d['titre']}\n\n{texte}" if d.get("titre") else texte,
                "contexte": {"texte": r.get("texte") or "plf", "chambre": pcfg.get("chambre_par_defaut", "gouvernement"),
                             "stade": pcfg.get("stade_par_defaut", "annonce"), "article": "", "num_amendement": "", "auteur": "", "sort": "en_attente"},
            }
