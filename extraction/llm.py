"""Appel du modèle de langage pour l'extraction. Fournisseur interchangeable.

Variables d'environnement :
  LLM_FOURNISSEUR = gemini | mistral | anthropic | openai   (défaut : gemini)
  LLM_MODELE      = nom du modèle (défaut selon fournisseur)
  GEMINI_API_KEY / MISTRAL_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY
  OPENAI_BASE_URL = URL d'une API compatible OpenAI (ex. passerelle interne type LazardGPT)
"""
from __future__ import annotations

import json
import logging
import os
import time

import requests

log = logging.getLogger("extraction.llm")

MODELES_DEFAUT = {
    "gemini": "gemini-3.6-flash",
    "mistral": "mistral-small-latest",
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o-mini",
}
TIMEOUT = 90
MAX_TENTATIVES = 3
# modèles essayés dans l'ordre si le modèle configuré renvoie "not found / no longer available"
REPLI = {
    "gemini": ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3-flash", "gemini-2.5-flash"],
    "mistral": ["mistral-small-latest", "mistral-medium-latest"],
    "anthropic": ["claude-sonnet-4-5", "claude-3-5-haiku-latest"],
    "openai": [],
}
_modele_actif: dict[str, str] = {}


class ErreurLLM(RuntimeError):
    pass


def fournisseur_courant() -> tuple[str, str]:
    f = os.environ.get("LLM_FOURNISSEUR", "gemini").strip().lower()
    if f not in MODELES_DEFAUT:
        raise ErreurLLM(f"Fournisseur inconnu : {f}")
    if f in _modele_actif:              # un repli a déjà été retenu pendant cette exécution
        return f, _modele_actif[f]
    m = os.environ.get("LLM_MODELE", "").strip() or MODELES_DEFAUT[f]
    return f, m


def _modele_indisponible(msg: str) -> bool:
    m = msg.lower()
    return ("http 404" in m or "http 400" in m) and ("model" in m) and ("not found" in m or "no longer available" in m or "not supported" in m)


def _cle(nom: str) -> str:
    v = os.environ.get(nom, "").strip()
    if not v:
        raise ErreurLLM(f"Secret manquant : {nom}")
    return v


# ------------------------------------------------------------------ appels bruts

def _gemini(systeme: str, utilisateur: str, modele: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": systeme}]},
        "contents": [{"role": "user", "parts": [{"text": utilisateur}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json", "maxOutputTokens": 8192},
    }
    # clé transmise dans l'en-tête recommandé par Google (compatible anciens AIza… et nouveaux AQ.… formats)
    r = requests.post(url, headers={"x-goog-api-key": _cle("GEMINI_API_KEY"), "Content-Type": "application/json"},
                      json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        raise ErreurLLM(f"Gemini HTTP {r.status_code} : {' '.join(r.text.split())[:600]}")
    data = r.json()
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
    except Exception:
        raise ErreurLLM(f"Gemini réponse inattendue : {json.dumps(data)[:300]}")


def _openai_compatible(systeme: str, utilisateur: str, modele: str, base_url: str, cle: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": modele,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {cle}"}, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        raise ErreurLLM(f"{base_url} HTTP {r.status_code} : {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        raise ErreurLLM(f"réponse inattendue : {r.text[:300]}")


def _anthropic(systeme: str, utilisateur: str, modele: str) -> str:
    cle = _cle("ANTHROPIC_API_KEY")
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
    body = {"model": modele, "max_tokens": 8192, "system": systeme,
            "messages": [{"role": "user", "content": utilisateur}]}
    if modele.startswith(("claude-sonnet-5", "claude-opus-5", "claude-fable")):
        body["output_config"] = {"effort": "low"}   # génération 5 : temperature refusée (HTTP 400)
    else:
        body["temperature"] = 0.1
    r = requests.post(base + "/v1/messages",
                      headers={"x-api-key": cle, "api-key": cle, "anthropic-version": "2023-06-01"},
                      json=body, timeout=240)
    if r.status_code != 200:
        raise ErreurLLM(f"Anthropic HTTP {r.status_code} : {r.text[:300]}")
    try:
        return "".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text")
    except Exception:
        raise ErreurLLM(f"Anthropic réponse inattendue : {r.text[:300]}")


def appeler(systeme: str, utilisateur: str) -> str:
    """Appelle le fournisseur configuré, avec relances sur erreurs transitoires. Retourne le texte brut."""
    f, m = fournisseur_courant()
    derniere: Exception | None = None
    for tentative in range(1, MAX_TENTATIVES + 1):
        try:
            if f == "gemini":
                return _gemini(systeme, utilisateur, m)
            if f == "mistral":
                return _openai_compatible(systeme, utilisateur, m, "https://api.mistral.ai/v1", _cle("MISTRAL_API_KEY"))
            if f == "anthropic":
                return _anthropic(systeme, utilisateur, m)
            if f == "openai":
                base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
                return _openai_compatible(systeme, utilisateur, m, base, _cle("OPENAI_API_KEY"))
        except ErreurLLM as ex:
            derniere = ex
            msg = str(ex)
            if _modele_indisponible(msg):
                # essayer le modèle de repli suivant, une seule fois par modèle
                candidats = [x for x in REPLI.get(f, []) if x != m]
                if candidats:
                    m = candidats[0]
                    REPLI[f] = candidats[1:]
                    _modele_actif[f] = m
                    log.warning("modèle indisponible, repli sur %s", m)
                    continue
                raise
            transitoire = any(code in msg for code in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")) and "quota" not in msg.lower()
            if not transitoire or tentative == MAX_TENTATIVES:
                raise
            attente = 10 * tentative
            log.warning("erreur transitoire (%s), nouvelle tentative dans %ss", msg[:80], attente)
            time.sleep(attente)
        except requests.RequestException as ex:
            derniere = ex
            if tentative == MAX_TENTATIVES:
                raise ErreurLLM(f"réseau : {ex}")
            time.sleep(10 * tentative)
    raise ErreurLLM(str(derniere))


def extraire_liste(texte_brut: str) -> list[dict]:
    """Transforme la réponse du modèle en liste de fiches. Tolère un objet seul ou un objet {"fiches": [...]}."""
    from extraction import schema as sch
    data = sch.parse_json_fiches(texte_brut)
    # certains modèles en mode json_object renvoient {"fiches": [...]} ou {"mesures": [...]}
    if len(data) == 1 and isinstance(data[0], dict):
        for k in ("fiches", "mesures", "items", "results"):
            if k in data[0] and isinstance(data[0][k], list):
                return data[0][k]
    return data
