"""Tâche principale : collecte des flux puis extraction des documents 'à traiter'.

Usage :
  python jobs/run_collecte.py                 # collecte + extraction
  python jobs/run_collecte.py --sans-collecte # extraction seule
  python jobs/run_collecte.py --sans-extraction
  python jobs/run_collecte.py --max 20        # limite de documents extraits (défaut : MAX_DOCS ou 40)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import supa  # noqa: E402
from extraction import llm, prompts  # noqa: E402
from extraction import schema as sch  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
log = logging.getLogger("jobs")

TEXTE_MIN = 200  # en dessous, le document est ignoré (résumé de flux trop court, page non récupérée)


def extraire(max_docs: int, acteurs: set[str], tax: dict, idx: dict, fournisseur: str) -> dict:
    systeme = prompts.prompt_systeme(tax)
    stats = {"docs_extraits": 0, "fiches_creees": 0, "docs_ignores": 0, "erreurs": 0}
    docs = supa.documents_a_traiter(max_docs)
    log.info("%d document(s) à traiter (max %d)", len(docs), max_docs)
    maintenant = datetime.now(timezone.utc).isoformat()

    for d in docs:
        texte = (d.get("texte") or "").strip()
        if len(texte) < TEXTE_MIN:
            supa.maj_document(d["id"], statut="ignore", erreur="texte trop court", traite_le=maintenant)
            stats["docs_ignores"] += 1
            continue
        try:
            brut = llm.appeler(systeme, prompts.prompt_utilisateur(
                d["acteur_id"], d.get("url_finale") or d["url"], d.get("date_publication"),
                d.get("titre"), texte, sorted(acteurs)))
            fiches = llm.extraire_liste(brut)
        except Exception as ex:
            supa.maj_document(d["id"], statut="erreur", erreur=str(ex)[:500], traite_le=maintenant, fournisseur=fournisseur)
            stats["erreurs"] += 1
            log.warning("extraction échouée %s : %s", d["url"], str(ex)[:120])
            continue

        valides, refus = [], []
        for f in fiches:
            if isinstance(f, dict):
                f.setdefault("url_source", d.get("url_finale") or d["url"])
                if d.get("date_publication") and not f.get("date_source"):
                    f["date_source"] = d["date_publication"]
            errs = sch.valider_fiche(f, idx, acteurs)
            (valides if not errs else refus).append((f, errs))
        lignes = []
        for f, _ in valides:
            ligne = sch.normaliser_fiche(f, saisi_par=f"auto:{fournisseur}")
            ligne["document_id"] = d["id"]
            lignes.append(ligne)
        n = supa.inserer_mesures(lignes)
        note = f"{len(refus)} fiche(s) refusée(s) : " + " | ".join("; ".join(e) for _, e in refus) if refus else None
        supa.maj_document(d["id"], statut="traite", nb_fiches=n, erreur=(note or "")[:500] or None,
                          traite_le=maintenant, fournisseur=fournisseur)
        stats["docs_extraits"] += 1
        stats["fiches_creees"] += n
        log.info("%s → %d fiche(s)%s", (d.get("titre") or d["url"])[:70], n, f" ({len(refus)} refusée(s))" if refus else "")
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sans-collecte", action="store_true")
    ap.add_argument("--sans-extraction", action="store_true")
    ap.add_argument("--max", type=int, default=int(os.environ.get("MAX_DOCS", "40")))
    ap.add_argument("--sans-texte", action="store_true", help="ne pas récupérer le texte complet des articles")
    args = ap.parse_args()

    fournisseur, modele = llm.fournisseur_courant()
    run_id = supa.ouvrir_run(fournisseur, modele)
    journal: list[str] = [f"fournisseur={fournisseur} modele={modele}"]
    total = {"flux_lus": 0, "docs_vus": 0, "docs_nouveaux": 0, "docs_extraits": 0, "fiches_creees": 0, "erreurs": 0}
    code = 0
    try:
        acteurs = supa.acteurs_ids()
        tax = sch.load_taxonomie()
        idx = sch.index_taxonomie(tax)
        if not args.sans_collecte:
            from collecte import rss
            s = rss.collecter(acteurs, recuperer_texte=not args.sans_texte)
            total.update({k: s.get(k, 0) for k in ("flux_lus", "docs_vus", "docs_nouveaux")})
            total["erreurs"] += s.get("flux_en_erreur", 0)
            journal.append(f"collecte : {s}")
        if not args.sans_extraction:
            s = extraire(args.max, acteurs, tax, idx, fournisseur)
            total["docs_extraits"] = s["docs_extraits"]
            total["fiches_creees"] = s["fiches_creees"]
            total["erreurs"] += s["erreurs"]
            journal.append(f"extraction : {s}")
    except Exception:
        code = 1
        journal.append("ERREUR FATALE :\n" + traceback.format_exc()[-1500:])
        log.error("échec de la tâche", exc_info=True)
    finally:
        supa.fermer_run(run_id, journal="\n".join(journal), **total)
        log.info("bilan : %s", total)
    return code


if __name__ == "__main__":
    sys.exit(main())
