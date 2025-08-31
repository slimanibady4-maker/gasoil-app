import streamlit as st
import pandas as pd
import os
from datetime import date
import uuid
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# =========================
# CONFIGURATION
# =========================
st.set_page_config(page_title="Gestion Gasoil", page_icon="⛽", layout="wide")

# Nom de la feuille Google Sheet
SHEET_NAME = "Gasoil_Records"

# ID du dossier Google Drive pour les justificatifs
# Mets ici ton dossier partagé Google Drive
DRIVE_FOLDER_ID = "1Drc-2yYlHd7mScOGp13ALKHUKQFneAEF"

# =========================
# AUTH GOOGLE
# =========================
# Credentials pour Google Sheet et Drive depuis st.secrets
sa_info = st.secrets["gcp_service_account"]

creds = Credentials.from_service_account_info(
    sa_info, scopes=["https://www.googleapis.com/auth/drive"]
)
gc = gspread.authorize(creds)

gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

# =========================
# FEUILLE GOOGLE SHEET
# =========================
try:
    sh = gc.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sh = gc.create(SHEET_NAME)
worksheet = sh.sheet1

# Ajouter les colonnes si elles n'existent pas
if not worksheet.get_all_records():
    worksheet.update([["ID","Technicien","Montant","Date","Justification","Photos"]])

# =========================
# HELPERS
# =========================
def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "-")
    name = name.strip().replace(" ", "_")
    return name or "inconnu"

def parse_amount_to_float(txt: str):
    if txt is None:
        return None
    s = str(txt).replace("€", "").replace("EUR", "").replace("eur", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def upload_file_to_drive(local_path, folder_id):
    file_drive = drive.CreateFile({'title': os.path.basename(local_path),
                                   'parents':[{'id': folder_id}]})
    file_drive.SetContentFile(local_path)
    file_drive.Upload()
    return file_drive['id']

def save_to_google_sheet(row_dict):
    worksheet.append_row(list(row_dict.values()))

# =========================
# STREAMLIT UI
# =========================
st.title("⛽ Gestion des dépenses de gasoil – Saisie & Export Excel")

st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie_unique", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *")
        montant = st.text_input("Montant (€) *")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
        justification = st.text_area("Justification *")
    fichiers = st.file_uploader(
        "Photos justificatives (JPG, PNG, PDF)",
        type=["jpg","jpeg","png","pdf"],
        accept_multiple_files=True
    )
    submitted = st.form_submit_button("💾 Enregistrer")

if submitted:
    errors = []
    if not technicien.strip():
        errors.append("Le nom du technicien est requis.")
    if not montant.strip():
        errors.append("Le montant est requis.")
    if not justification.strip():
        errors.append("La justification est requise.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        rec_id = str(uuid.uuid4())[:8]
        saved_paths = []

        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                tmp_path = os.path.join("/tmp", f"{uuid.uuid4().hex}{ext}")
                with open(tmp_path, "wb") as out:
                    out.write(f.getbuffer())
                upload_file_to_drive(tmp_path, DRIVE_FOLDER_ID)
                saved_paths.append(f.name)

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),
            "Date": str(date_val),
            "Justification": justification.strip(),
            "Photos": "; ".join(saved_paths) if saved_paths else ""
        }

        save_to_google_sheet(new_row)
        st.success("✅ Saisie enregistrée avec succès !")

# =========================
# HISTORIQUE
# =========================
st.subheader("📊 Historique")
records = worksheet.get_all_records()
if records:
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True)
    amounts = [parse_amount_to_float(x) for x in df["Montant"]]
    amounts = [x for x in amounts if x is not None]
    st.metric("Total", f"{sum(amounts):,.2f} €")
else:
    st.info("Aucune donnée pour le moment.")
