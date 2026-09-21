"""pytest tests/test_schema_plf.py — valide le miroir de validation et le référentiel PLF."""
from extraction import schema_plf

REF = schema_plf.charger_referentiel()
IDX = schema_plf.indexer(REF)

def fiche_ok(**kw):
    f = {"acteur_id": "an-soc", "theme_id": "fiscalite", "sous_theme_id": "ifi_fortune", "mots_cles": ["IFI"],
         "titre": "Impôt plancher sur les très hauts patrimoines", "resume": "Amendement créant un impôt plancher. Il vise les patrimoines supérieurs à un seuil.",
         "citation": "", "nature": "amendement", "impact_client": "Alourdirait l'imposition des patrimoines les plus élevés.",
         "url_source": "https://www.assemblee-nationale.fr/dyn/17/amendements/x", "date_source": "2026-10-15", "confiance": "eleve",
         "texte": "plf", "chambre": "an", "stade": "commission", "sort": "adopte", "article": "art. add. après 3", "num_amendement": "CF1245"}
    f.update(kw); return f

def test_referentiel_charge():
    assert "gouvernement-plf" in IDX["acteurs"] and "an-rn" in IDX["acteurs"] and "senat-lr" in IDX["acteurs"]
    assert "institut-montaigne" in IDX["acteurs"]          # repris du référentiel principal
    assert {"plf", "plfss"} == IDX["textes"] and "regime_matrimonial" in IDX["sous_par_theme"]["fiscalite"]

def test_fiche_valide():
    assert schema_plf.valider(fiche_ok(), IDX) == []

def test_refus():
    assert any("texte" in e for e in schema_plf.valider(fiche_ok(texte=""), IDX))
    assert any("stade invalide" in e for e in schema_plf.valider(fiche_ok(stade="vote"), IDX))
    assert any("acteur_id inconnu" in e for e in schema_plf.valider(fiche_ok(acteur_id="an-xyz"), IDX))
    assert any("antérieure" in e for e in schema_plf.valider(fiche_ok(date_source="2025-06-01"), IDX))
    assert any("n'appartient pas" in e for e in schema_plf.valider(fiche_ok(sous_theme_id="dutreil"), IDX))

def test_normaliser():
    n = schema_plf.normaliser(fiche_ok(), id_fiche="abc", saisi_par="auto:test", horodatage="2026-10-16T05:00:00Z")
    assert n["statut"] == "brut" and n["sort"] == "adopte" and n["valide_par"] is None and n["texte"] == "plf"
