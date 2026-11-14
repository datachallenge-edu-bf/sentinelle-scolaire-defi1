"""Sentinelle Scolaire : lance le tableau de bord web dans Streamlit.

Le tableau de bord lui-même est la page web/sentinelle_scolaire.html.
Lancer : streamlit run app.py
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

PAGE = Path(__file__).resolve().parent / "web" / "sentinelle_scolaire.html"

st.set_page_config(page_title="Sentinelle Scolaire", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
header, footer, #MainMenu {visibility:hidden}
.block-container {padding:0 !important; max-width:100% !important}
iframe {border:0}
</style>""", unsafe_allow_html=True)

if not PAGE.exists():
    st.error(f"Fichier introuvable : {PAGE}. Copiez le dossier « web » à côté de app.py.")
else:
    components.html(PAGE.read_text(encoding="utf-8"), height=1400, scrolling=True)
