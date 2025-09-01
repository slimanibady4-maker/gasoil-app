import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration des scopes ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

st.title("📊 Connexion à Google Sheets")

try:
    # --- Lecture des secrets ---
    sa_info = dict(st.secrets["gcp_service_account"])
    # Remplace les \\n par des vraies nouvelles lignes
    sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")
    
    # --- Authentification ---
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    client = gspread.authorize(creds)

    # --- Connexion au Google Sheet ---
    SHEET_NAME = "Nom_de_ton_Google_Sheet"
    sheet = client.open(SHEET_NAME).sheet1

    # --- Lecture des données ---
    records = sheet.get_all_records()
    st.write("✅ Connexion réussie ! Voici un aperçu des données :")
    st.dataframe(records)

except Exception as e:
    st.error(f"❌ Erreur : {str(e)}")
