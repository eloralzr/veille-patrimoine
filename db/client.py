"""Accès à la base Supabase pour l'application Streamlit.

Les secrets sont lus dans st.secrets (Streamlit Cloud > Settings > Secrets) :
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_KEY = "clé service_role"
"""
from __future__ import annotations

import streamlit as st
from supabase import Client, create_client


@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    url = str(st.secrets.get("SUPABASE_URL", "")).strip()
    key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
    problemes = []
    if not url.startswith("https://") or not url.endswith(".supabase.co"):
        problemes.append("SUPABASE_URL doit être de la forme https://xxxx.supabase.co")
    if not key.startswith(("eyJ", "sb_secret_")):
        problemes.append("SUPABASE_KEY ne ressemble pas à une clé Supabase (doit commencer par eyJ ou sb_secret_)")
    for nom, val in (("SUPABASE_URL", url), ("SUPABASE_KEY", key)):
        mauvais = [c for c in val if ord(c) > 127]
        if mauvais:
            problemes.append(f"{nom} contient des caractères non autorisés : {''.join(sorted(set(mauvais)))}")
    if problemes:
        st.error("Configuration des secrets incorrecte :\n\n- " + "\n- ".join(problemes)
                 + "\n\nCorrigez dans Streamlit Cloud > Settings > Secrets, puis Save.")
        st.stop()
    return create_client(url, key)

# ---------- Référentiel ----------

@st.cache_data(ttl=300, show_spinner=False)
def load_acteurs(actifs_seulement: bool = True) -> list[dict]:
    q = get_client().table("acteurs").select("*").order("priorite").order("nom")
    if actifs_seulement:
        q = q.eq("actif", True)
    return q.execute().data or []


# ---------- Fiches mesure ----------

def insert_mesures(fiches: list[dict]) -> int:
    """Insère une liste de fiches déjà validées. Retourne le nombre de lignes créées."""
    if not fiches:
        return 0
    res = get_client().table("mesures").insert(fiches).execute()
    return len(res.data or [])


def load_mesures(limit: int = 2000) -> list[dict]:
    res = (
        get_client()
        .table("mesures")
        .select("*, acteurs(nom, type, priorite)")
        .order("cree_le", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    for r in rows:  # aplatir la jointure
        a = r.pop("acteurs", None) or {}
        r["acteur_nom"] = a.get("nom", r.get("acteur_id"))
        r["acteur_type"] = a.get("type")
        r["acteur_priorite"] = a.get("priorite")
    return rows


def update_statut(mesure_id: str, statut: str, valide_par: str | None) -> None:
    payload = {"statut": statut}
    if statut in ("verifie", "publie"):
        payload["valide_par"] = valide_par
    get_client().table("mesures").update(payload).eq("id", mesure_id).execute()


def count_documents_a_traiter() -> int:
    res = (
        get_client()
        .table("documents")
        .select("id", count="exact")
        .eq("statut", "a_traiter")
        .execute()
    )
    return res.count or 0
