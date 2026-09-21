"""Job nocturne — veille PLF / PLFSS 2027.

    python -m jobs.run_collecte_plf [--dry-run] [--max N] [--textes plf,plfss]

Étapes : collecte (collecte/plf.py) → filtre de nouveauté (exports déjà produits) → extraction LLM
(prompt extraction/prompts_plf.py) → validation (extraction/schema_plf.py) → export exports/fiches_plf_AAAA-MM-JJ.json.

Le matin, la permanence colle l'export dans le Projet Claude « Import veille » (mode « Import PLF », instructions v17c),
ou dans l'onglet Source manuelle > Importer des fiches JSON de l'espace PLF de l'artefact.

Appel LLM : `appeler_llm` s'appuie sur `extraction.llm.appeler(systeme, utilisateur)` du dépôt (fournisseur, modèle
et clés lus dans l'environnement : LLM_FOURNISSEUR, LLM_MODELE, *_API_KEY, OPENAI_BASE_URL).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from collecte import plf as collecte_plf
from extraction import schema_plf
from extraction.prompts_plf import prompt_plf

RACINE = Path(__file__).resolve().parents[1]
EXPORTS = RACINE / "exports"
ETAT = RACINE / "exports" / ".plf_sources_vues.json"   # source_id déjà traités (évite de ré-extraire chaque nuit)
log = logging.getLogger("jobs.plf")


SYSTEME = ("Tu es un extracteur de fiches structurées pour un outil interne de veille. "
           "Tu réponds uniquement par une liste JSON valide (ou un objet {\"fiches\": [...]}), sans texte ni balises autour.")


def appeler_llm(prompt: str) -> tuple[str, str]:
    """Renvoie (texte_reponse, nom_modele) via extraction/llm.py du dépôt (fournisseur interchangeable, relances, replis)."""
    from extraction import llm  # import différé pour que --dry-run fonctionne sans clé API
    reponse = llm.appeler(SYSTEME, prompt)
    _, modele = llm.fournisseur_courant()   # lu après l'appel : tient compte d'un éventuel repli de modèle
    return reponse, modele


def parser_json(texte: str) -> list[dict]:
    t = texte.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t); t = re.sub(r"\s*```$", "", t)
    data = json.loads(t)
    if isinstance(data, dict):
        for k in ("fiches", "mesures", "items", "results"):
            if isinstance(data.get(k), list):
                data = data[k]; break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("Le JSON doit être une liste de fiches")
    return [x for x in data if isinstance(x, dict)]


def charger_vus() -> set[str]:
    try:
        return set(json.loads(ETAT.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="collecte et filtre seulement, aucun appel LLM")
    ap.add_argument("--max", type=int, default=150, help="nombre maximal de documents envoyés au LLM par exécution")
    ap.add_argument("--textes", default="plf,plfss")
    ap.add_argument("--ignorer-vus", action="store_true", help="ne pas filtrer les sources déjà traitées")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    ref = schema_plf.charger_referentiel(); idx = schema_plf.indexer(ref)
    docs = collecte_plf.collecter(textes=tuple(args.textes.split(",")))
    vus = set() if args.ignorer_vus else charger_vus()
    nouveaux = [d for d in docs if d["source_id"] not in vus]
    log.info("%d documents, %d nouveaux, %d envoyés au LLM", len(docs), len(nouveaux), min(len(nouveaux), args.max))
    if args.dry_run:
        for d in nouveaux[: args.max]:
            print(f"- {d['acteur_id']:<32} {d['contexte']['stade']:<14} {d['contexte'].get('article',''):<22} {d['url']}")
        return 0

    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    fiches, refusees, modele_vu = [], [], "llm"
    for d in nouveaux[: args.max]:
        try:
            reponse, modele_vu = appeler_llm(prompt_plf(d["acteur_id"], d["url"], d["date"], d["texte"][:20000], d["contexte"], ref))
            brutes = parser_json(reponse)
        except Exception as e:  # noqa: BLE001
            log.error("LLM/JSON %s : %s", d["source_id"], e); refusees.append({"source_id": d["source_id"], "erreur": str(e)}); continue
        for f in brutes:
            f.setdefault("url_source", d["url"]); f.setdefault("date_source", d["date"])
            for k in ("texte", "chambre", "stade", "article", "num_amendement", "auteur", "sort"):
                if not f.get(k) and d["contexte"].get(k):
                    f[k] = d["contexte"][k]
            err = schema_plf.valider(f, idx)
            if err:
                refusees.append({"source_id": d["source_id"], "titre": f.get("titre"), "erreurs": err}); continue
            fiches.append(schema_plf.normaliser(f, id_fiche=str(uuid.uuid4()), saisi_par=f"auto:{modele_vu}", horodatage=horodatage))
        vus.add(d["source_id"])

    EXPORTS.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(timezone.utc).date().isoformat()
    sortie = EXPORTS / f"fiches_plf_{jour}.json"
    sortie.write_text(json.dumps(fiches, ensure_ascii=False, indent=2), encoding="utf-8")
    (EXPORTS / f"refus_plf_{jour}.json").write_text(json.dumps(refusees, ensure_ascii=False, indent=2), encoding="utf-8")
    ETAT.write_text(json.dumps(sorted(vus)), encoding="utf-8")
    log.info("%d fiches exportées vers %s ; %d refus journalisés", len(fiches), sortie, len(refusees))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
