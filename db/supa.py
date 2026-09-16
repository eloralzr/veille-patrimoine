"""Client Supabase pour les scripts hors Streamlit (GitHub Actions).

Lit SUPABASE_URL et SUPABASE_KEY dans les variables d'environnement.
"""
from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL et SUPABASE_KEY doivent être définis dans l'environnement.")
    return create_client(url, key)


def acteurs_ids() -> set[str]:
    res = get_client().table("acteurs").select("acteur_id").execute()
    return {r["acteur_id"] for r in (res.data or [])}


def sources_actives(type_source: str | None = None) -> list[dict]:
    q = get_client().table("sources").select("*").eq("actif", True)
    if type_source:
        q = q.eq("type_source", type_source)
    return q.execute().data or []


def hashes_existants(hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    out: set[str] = set()
    for i in range(0, len(hashes), 200):  # requêtes par lots
        res = get_client().table("documents").select("hash").in_("hash", hashes[i:i + 200]).execute()
        out |= {r["hash"] for r in (res.data or [])}
    return out


def inserer_documents(docs: list[dict]) -> int:
    if not docs:
        return 0
    res = get_client().table("documents").insert(docs).execute()
    return len(res.data or [])


def documents_a_traiter(limit: int) -> list[dict]:
    res = (
        get_client().table("documents").select("*")
        .eq("statut", "a_traiter").order("cree_le", desc=False).limit(limit).execute()
    )
    return res.data or []


def maj_document(doc_id: str, **champs) -> None:
    get_client().table("documents").update(champs).eq("id", doc_id).execute()


def inserer_mesures(fiches: list[dict]) -> int:
    if not fiches:
        return 0
    res = get_client().table("mesures").insert(fiches).execute()
    return len(res.data or [])


def ouvrir_run(fournisseur: str, modele: str) -> str:
    res = get_client().table("collecte_runs").insert({"fournisseur": fournisseur, "modele": modele}).execute()
    return res.data[0]["id"]


def fermer_run(run_id: str, **champs) -> None:
    from datetime import datetime, timezone
    champs["fin"] = datetime.now(timezone.utc).isoformat()
    get_client().table("collecte_runs").update(champs).eq("id", run_id).execute()
