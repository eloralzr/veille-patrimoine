"""veille-patrimoine — application Streamlit v0 (sans API).

Circuit : l'ingénieur extrait la fiche dans le Projet Claude Enterprise (JSON),
la colle dans la page "Saisie", contrôle, enregistre. Les pages "Fiches" et
"Tableau de bord" lisent la base Supabase.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import client as db  # noqa: E402
from extraction import schema as sch  # noqa: E402

st.set_page_config(page_title="Veille programmes", page_icon="📋", layout="wide")

# ---------------------------------------------------------------- Accès
def controle_acces() -> None:
    if st.session_state.get("ok"):
        return
    st.title("Veille programmes — accès")
    mdp = st.text_input("Mot de passe", type="password")
    if st.button("Entrer"):
        if mdp == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["ok"] = True
            st.rerun()
        st.error("Mot de passe incorrect.")
    st.stop()


controle_acces()

TAX = sch.load_taxonomie()
IDX = sch.index_taxonomie(TAX)
ACTEURS = db.load_acteurs(actifs_seulement=False)
ACTEUR_NOM = {a["acteur_id"]: a["nom"] for a in ACTEURS}
ACTEUR_IDS = set(ACTEUR_NOM)

LIB_NATURE = IDX["natures"]
LIB_CONF = IDX["confiances"]
LIB_STATUT = {"brut": "Brut", "verifie": "Vérifié", "publie": "Publié", "retire": "Retiré"}

# ---------------------------------------------------------------- Menu
with st.sidebar:
    st.markdown("### Veille programmes")
    page = st.radio("Navigation", ["Tableau de bord", "Fiches", "Saisie", "File de collecte", "Référentiel"], label_visibility="collapsed")
    st.divider()
    utilisateur = st.text_input("Vos initiales", value=st.session_state.get("user", ""), max_chars=6,
                                help="Utilisées pour tracer les saisies et validations.")
    st.session_state["user"] = utilisateur.strip().upper()
    st.caption("Données publiques uniquement. L'outil compare, il ne classe pas.")


def df_mesures() -> pd.DataFrame:
    rows = db.load_mesures()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["theme"] = df["theme_id"].map(IDX["themes"])
    df["sous_theme"] = df["sous_theme_id"].map(IDX["libelle_sous"])
    df["nature_lib"] = df["nature"].map(LIB_NATURE)
    df["confiance_lib"] = df["confiance"].map(LIB_CONF)
    df["statut_lib"] = df["statut"].map(LIB_STATUT)
    df["cree_le"] = pd.to_datetime(df["cree_le"]).dt.tz_localize(None)
    return df


# ================================================================ Tableau de bord
if page == "Tableau de bord":
    st.title("Tableau de bord")
    df = df_mesures()
    if df.empty:
        st.info("Aucune fiche en base. Commencez par la page **Saisie**.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fiches", len(df))
    c2.metric("Vérifiées / publiées", int(df["statut"].isin(["verifie", "publie"]).sum()))
    semaine = df[df["cree_le"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]
    c3.metric("Nouvelles (7 j)", len(semaine))
    c4.metric("Acteurs couverts", df["acteur_id"].nunique())

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Par thème")
        st.bar_chart(df["theme"].value_counts())
    with g2:
        st.subheader("Par acteur (10 premiers)")
        st.bar_chart(df["acteur_nom"].value_counts().head(10))

    st.subheader("Matrice acteurs × thèmes (nombre de fiches)")
    piv = pd.crosstab(df["acteur_nom"], df["theme"])
    st.dataframe(piv, use_container_width=True)

    st.subheader("Dernières fiches")
    st.dataframe(
        df[["cree_le", "acteur_nom", "theme", "sous_theme", "titre", "nature_lib", "confiance_lib", "statut_lib"]]
        .head(15).rename(columns={"cree_le": "Saisie", "acteur_nom": "Acteur", "theme": "Thème", "sous_theme": "Sous-thème",
                                  "titre": "Titre", "nature_lib": "Nature", "confiance_lib": "Confiance", "statut_lib": "Statut"}),
        use_container_width=True, hide_index=True,
    )

# ================================================================ Fiches
elif page == "Fiches":
    st.title("Fiches mesure")
    df = df_mesures()
    if df.empty:
        st.info("Aucune fiche en base.")
        st.stop()

    f1, f2, f3, f4, f5 = st.columns([2, 2, 2, 2, 3])
    sel_act = f1.multiselect("Acteur", sorted(df["acteur_nom"].unique()))
    sel_th = f2.multiselect("Thème", list(IDX["themes"].values()))
    sel_nat = f3.multiselect("Nature", list(LIB_NATURE.values()))
    sel_st = f4.multiselect("Statut", list(LIB_STATUT.values()), default=[v for k, v in LIB_STATUT.items() if k != "retire"])
    texte = f5.text_input("Recherche (titre, résumé, mots-clés)")

    v = df.copy()
    if sel_act:
        v = v[v["acteur_nom"].isin(sel_act)]
    if sel_th:
        v = v[v["theme"].isin(sel_th)]
    if sel_nat:
        v = v[v["nature_lib"].isin(sel_nat)]
    if sel_st:
        v = v[v["statut_lib"].isin(sel_st)]
    if texte:
        t = texte.lower()
        v = v[v.apply(lambda r: t in str(r["titre"]).lower() or t in str(r["resume"]).lower()
                      or t in " ".join(r["mots_cles"] or []).lower(), axis=1)]

    st.caption(f"{len(v)} fiche(s)")
    st.download_button("Exporter la sélection (CSV)",
                       v.drop(columns=["json_brut"], errors="ignore").to_csv(index=False).encode("utf-8"),
                       "fiches.csv", "text/csv")

    for _, r in v.iterrows():
        auto = "  ·  🤖 auto" if str(r.get("saisi_par") or "").startswith("auto:") else ""
        titre = f"{r['acteur_nom']} — {r['titre']}  ·  {r['sous_theme']}  ·  {r['nature_lib']}  ·  {r['statut_lib']}{auto}"
        with st.expander(titre):
            st.write(r["resume"])
            if r.get("citation"):
                st.markdown(f"> « {r['citation']} »")
            meta = f"**Source :** [{r['url_source']}]({r['url_source']})"
            if r.get("date_source"):
                meta += f"  ·  **Date :** {r['date_source']}"
            meta += f"  ·  **Confiance :** {r['confiance_lib']}"
            st.markdown(meta)
            if r.get("impact_client"):
                st.markdown(f"**Impact client :** {r['impact_client']}")
            if r.get("mots_cles"):
                st.caption("Mots-clés : " + ", ".join(r["mots_cles"]))
            st.caption(f"Saisie par {r.get('saisi_par') or '—'} le {r['cree_le']:%d/%m/%Y}"
                       + (f" · validée par {r['valide_par']}" if r.get("valide_par") else ""))
            b1, b2, b3, _ = st.columns([1, 1, 1, 5])
            uid = str(r["id"])
            if r["statut"] == "brut" and b1.button("Marquer vérifiée", key="v" + uid):
                db.update_statut(uid, "verifie", st.session_state["user"]); st.rerun()
            if r["statut"] == "verifie" and b2.button("Publier", key="p" + uid):
                db.update_statut(uid, "publie", st.session_state["user"]); st.rerun()
            if r["statut"] != "retire" and b3.button("Retirer", key="r" + uid):
                db.update_statut(uid, "retire", st.session_state["user"]); st.rerun()

# ================================================================ Saisie
elif page == "Saisie":
    st.title("Saisie d'une fiche")
    st.markdown(
        "1. Dans le **Projet Claude « Veille programmes »**, collez votre extrait (article, programme, interview) "
        "avec l'acteur, l'URL et la date.  \n"
        "2. Copiez le JSON renvoyé par Claude.  \n"
        "3. Collez-le ci-dessous, contrôlez, enregistrez."
    )
    if not st.session_state["user"]:
        st.warning("Renseignez vos initiales dans la barre latérale avant d'enregistrer.")

    brut = st.text_area("JSON de la ou des fiches", height=260,
                        placeholder='{\n  "acteur_id": "philippe-edouard",\n  "theme_id": "transmission",\n  ...\n}')
    if brut.strip():
        try:
            fiches = sch.parse_json_fiches(brut)
        except Exception as e:
            st.error(f"JSON illisible : {e}")
            st.stop()

        valides, erreurs = [], []
        for i, f in enumerate(fiches, 1):
            errs = sch.valider_fiche(f, IDX, ACTEUR_IDS)
            if errs:
                erreurs.append((i, f, errs))
            else:
                valides.append(f)

        if erreurs:
            st.error(f"{len(erreurs)} fiche(s) refusée(s) :")
            for i, f, errs in erreurs:
                st.markdown(f"**Fiche {i}** — {f.get('titre', '(sans titre)')}")
                for e in errs:
                    st.markdown(f"- {e}")
            st.caption("Corrigez le JSON (ou demandez à Claude de le corriger) puis recollez.")

        if valides:
            st.success(f"{len(valides)} fiche(s) valide(s)")
            apercu = pd.DataFrame([{
                "Acteur": ACTEUR_NOM.get(f["acteur_id"]), "Thème": IDX["themes"][f["theme_id"]],
                "Sous-thème": IDX["libelle_sous"][f["sous_theme_id"]], "Titre": f["titre"],
                "Nature": LIB_NATURE[f["nature"]], "Confiance": LIB_CONF[f["confiance"]],
                "Date": f.get("date_source", ""), "Source": f["url_source"],
            } for f in valides])
            st.dataframe(apercu, use_container_width=True, hide_index=True)
            for f in valides:
                with st.expander(f"Détail — {f['titre']}"):
                    st.write(f["resume"])
                    if f.get("citation"):
                        st.markdown(f"> « {f['citation']} »")
                    if f.get("impact_client"):
                        st.markdown(f"**Impact client :** {f['impact_client']}")
            if st.button("Enregistrer les fiches valides", type="primary", disabled=not st.session_state["user"]):
                n = db.insert_mesures([sch.normaliser_fiche(f, st.session_state["user"]) for f in valides])
                st.success(f"{n} fiche(s) enregistrée(s) avec le statut « Brut ».")
                st.balloons()

    with st.expander("Rappel du format attendu"):
        st.code(
            '{\n'
            '  "acteur_id": "philippe-edouard",\n'
            '  "theme_id": "transmission",\n'
            '  "sous_theme_id": "droits_succession",\n'
            '  "mots_cles": ["droits de succession", "abattement"],\n'
            '  "titre": "Relèvement de l\'abattement en ligne directe",\n'
            '  "resume": "Propose de porter l\'abattement ... (2 à 4 phrases, en vos propres mots).",\n'
            '  "citation": "extrait court, 25 mots maximum",\n'
            '  "nature": "engagement | piste | proposition | reaction | chiffrage",\n'
            '  "impact_client": "Conséquence concrète pour un client type.",\n'
            '  "url_source": "https://...",\n'
            '  "date_source": "2026-09-10",\n'
            '  "confiance": "eleve | moyen | incertain"\n'
            '}', language="json")
        st.markdown("**Identifiants d'acteurs disponibles :** " + ", ".join(f"`{a}`" for a in sorted(ACTEUR_IDS)))

# ================================================================ File de collecte
elif page == "File de collecte":
    st.title("File de collecte")
    st.caption("Collecte automatique des flux (GitHub Actions, chaque nuit) et extraction par le modèle configuré. "
               "Les fiches produites arrivent en statut « Brut », marquées 🤖 auto.")

    stats = db.stats_documents()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("À traiter", stats["a_traiter"])
    c2.metric("Traités", stats["traite"])
    c3.metric("Ignorés", stats["ignore"])
    c4.metric("En erreur", stats["erreur"])

    st.subheader("Dernières exécutions")
    runs = db.load_runs()
    if runs:
        dr = pd.DataFrame(runs)
        dr["debut"] = pd.to_datetime(dr["debut"]).dt.tz_convert("Europe/Paris").dt.strftime("%d/%m %H:%M")
        cols = ["debut", "fournisseur", "modele", "flux_lus", "docs_vus", "docs_nouveaux", "docs_extraits", "fiches_creees", "erreurs"]
        st.dataframe(dr[cols].rename(columns={"debut": "Début", "fournisseur": "Fournisseur", "modele": "Modèle", "flux_lus": "Flux",
                                              "docs_vus": "Vus", "docs_nouveaux": "Nouveaux", "docs_extraits": "Extraits",
                                              "fiches_creees": "Fiches", "erreurs": "Erreurs"}),
                     use_container_width=True, hide_index=True)
        with st.expander("Journal de la dernière exécution"):
            st.code(runs[0].get("journal") or "", language="text")
    else:
        st.info("Aucune exécution enregistrée. Lancez le workflow **Collecte et extraction quotidiennes** dans l'onglet Actions de GitHub (bouton *Run workflow*).")

    st.subheader("Documents")
    choix = st.multiselect("Statut", ["a_traiter", "erreur", "traite", "ignore"], default=["a_traiter", "erreur"])
    docs = db.load_documents(choix) if choix else []
    st.caption(f"{len(docs)} document(s)")
    for d in docs:
        entete = f"[{d['statut']}] {d.get('acteur_nom')} — {(d.get('titre') or d['url'])[:90]}"
        if d.get("date_publication"):
            entete += f"  ·  {d['date_publication']}"
        if d.get("nb_fiches") is not None:
            entete += f"  ·  {d['nb_fiches']} fiche(s)"
        with st.expander(entete):
            st.markdown(f"**Source :** [{d.get('url_finale') or d['url']}]({d.get('url_finale') or d['url']})  ·  type : {d.get('source_type')}")
            if d.get("erreur"):
                st.warning(d["erreur"])
            b1, b2, b3, _ = st.columns([1, 1, 1, 4])
            did = str(d["id"])
            if d["statut"] != "a_traiter" and b1.button("Relancer l'extraction", key="rl" + did):
                db.update_document_statut(did, "a_traiter"); st.rerun()
            if d["statut"] != "ignore" and b2.button("Ignorer", key="ig" + did):
                db.update_document_statut(did, "ignore"); st.rerun()
            if b3.button("Copier pour Claude", key="cp" + did):
                st.session_state["copie_" + did] = True
            if st.session_state.get("copie_" + did):
                st.code(f"ACTEUR : {d['acteur_id']}\nURL : {d.get('url_finale') or d['url']}\nDATE : {d.get('date_publication') or ''}\nTEXTE :\n{(d.get('texte') or '')[:6000]}",
                        language="text")
                st.caption("À coller dans le Projet Claude en secours, puis la fiche dans la page Saisie.")

# ================================================================ Référentiel
elif page == "Référentiel":
    st.title("Référentiel")
    t1, t2 = st.tabs(["Acteurs", "Taxonomie"])
    with t1:
        da = pd.DataFrame(ACTEURS)
        cols = ["acteur_id", "nom", "type", "organisation", "camp", "statut", "priorite", "frequence_veille", "site_officiel", "notes", "actif"]
        st.dataframe(da[[c for c in cols if c in da.columns]], use_container_width=True, hide_index=True)
        st.caption("Modification via le fichier data/acteurs.csv et db/seed_referentiel.sql pour la v0 ; page d'administration prévue en v1.")
    with t2:
        for t in TAX["themes"]:
            st.subheader(f"{t['libelle']}  `{t['id']}`")
            st.dataframe(pd.DataFrame([{
                "sous_theme_id": s["id"], "Libellé": s["libelle"],
                "Mots-clés": ", ".join(s["mots_cles"]), "Impact client": s["impact_client"],
            } for s in t["sous_themes"]]), use_container_width=True, hide_index=True)
