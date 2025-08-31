import streamlit as st
import pandas as pd
import os
import uuid
from datetime import date
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# =========================
# CONFIG GOOGLE
# =========================
# Récupérer les secrets
sa_info = st.secrets["gcp_service_account"]

# Credentials pour Google Sheet
SCOPES = ["https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
gc = gspread.authorize(creds)

# Google Sheet
SHEET_NAME = "Gasoil_Records"
try:
    sh = gc.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sh = gc.create(SHEET_NAME)
worksheet = sh.sheet1

# Google Drive via PyDrive pour fichiers
gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

# ID du dossier Drive où enregistrer les justificatifs
DRIVE_FOLDER_ID = "1Drc-2yYlHd7mScOGp13ALKHUKQFneAEF"  # Remplace par ton ID Drive

# =========================
# UI
# =========================
st.set_page_config(page_title="Gestion Gasoil", page_icon="⛽", layout="wide")
st.title("⛽ Gestion des dépenses de gasoil – Saisie & Export Google Sheet")

# =========================
# FORMULAIRE
# =========================
st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie_unique", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *", placeholder="Ex: Ahmed B.")
        montant = st.text_input("Montant (€) *", placeholder="Ex: 50, 50.00, 50 €")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
        justification = st.text_area("Justification *", placeholder="Station, véhicule, etc.")
    fichiers = st.file_uploader(
        "Photos/PDF justificatives",
        type=["jpg", "jpeg", "png", "pdf", "webp"],
        accept_multiple_files=True
    )
    submitted = st.form_submit_button("💾 Enregistrer")

# =========================
# ENREGISTRER
# =========================
if submitted:
    errors = []
    if not technicien.strip():
        errors.append("Nom du technicien requis.")
    if not montant.strip():
        errors.append("Montant requis.")
    if not justification.strip():
        errors.append("Justification requise.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        # Préparer la ligne
        rec_id = str(uuid.uuid4())[:8]

        saved_paths = []
        if fichiers:
            for f in fichiers:
                unique_name = f"{date_val.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}_{f.name}"
                f_drive = drive.CreateFile({'title': unique_name, 'parents':[{'id': DRIVE_FOLDER_ID}]})
                f_drive.SetContentFile(f.name)
                f_drive.Upload()
                saved_paths.append(f_drive['id'])

        # Ajouter la ligne dans Google Sheet
        row = [rec_id, technicien.strip(), montant.strip(), str(date_val), justification.strip(), ";".join(saved_paths)]
        worksheet.append_row(row)
        st.success("✅ Saisie enregistrée et fichiers uploadés !")

# =========================
# HISTORIQUE
# =========================
st.markdown("---")
st.subheader("📊 Historique des dépenses")
data = worksheet.get_all_records()
if data:
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
else:
    st.info("Aucune donnée encore.")
