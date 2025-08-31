import streamlit as st
import pandas as pd
import os
from datetime import date
import uuid
from io import BytesIO
from google.oauth2.service_account import Credentials
import gspread
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# =========================
# CONFIGURATION
# =========================
SERVICE_ACCOUNT_FILE = "gasoil-uploader-91adc02a1dfb.json"
SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
SHEET_NAME = "Gasoil_Records"
DRIVE_FOLDER_ID = "1Drc-2yYlHd7mScOGp13ALKHUKQFneAEF"

# Authentification Google pour Sheets
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
try:
    sh = gc.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sh = gc.create(SHEET_NAME)
worksheet = sh.sheet1

# Authentification PyDrive pour Drive
gauth = GoogleAuth()
gauth.ServiceAuth(SERVICE_ACCOUNT_FILE)
drive = GoogleDrive(gauth)

# =========================
# HELPERS
# =========================
def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "-")
    name = name.strip().replace(" ", "_")
    return name or "inconnu"

def upload_file_to_drive(file_bytes, filename, folder_id):
    file_drive = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
    file_drive.SetContentString(file_bytes.decode('utf-8', errors='ignore'))
    file_drive.Upload()
    return file_drive['id']

def save_to_google_sheet(data: dict):
    worksheet.append_row(list(data.values()))

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Gestions Dépenses Gasoil", page_icon="⛽", layout="wide")
st.title("⛽ Gestion des dépenses de gasoil – Saisie & Upload Google Drive")

st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie_unique", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *", placeholder="Ex: Ahmed B.")
        montant = st.text_input("Montant (€) *", placeholder="Ex: 50, 50.00, 50 €")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
        justification = st.text_area("Justification *", placeholder="Détails de la dépense")
    fichiers = st.file_uploader(
        "Photos justificatives (jpg, png, pdf)",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
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
        saved_files = []

        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                unique_name = f"{date_val.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}{ext}"
                content = f.read()
                if ext in [".jpg", ".jpeg", ".png", ".webp", ".pdf"]:
                    # Upload file to Drive
                    file_drive = drive.CreateFile({
                        'title': unique_name,
                        'parents': [{'id': DRIVE_FOLDER_ID}]
                    })
                    file_drive.SetContentFile(f.name)
                    file_drive.Upload()
                    saved_files.append(unique_name)

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),
            "Date": str(date_val),
            "Justification": justification.strip(),
            "Photos": "; ".join(saved_files)
        }

        save_to_google_sheet(new_row)
        st.success("✅ Saisie enregistrée et fichiers uploadés sur Google Drive !")

# =========================
# HISTORIQUE
# =========================
st.markdown("---")
st.subheader("📊 Historique des dépenses (dernières lignes)")

data = worksheet.get_all_records()
df = pd.DataFrame(data)
st.dataframe(df, use_container_width=True)

# Download Excel depuis Google Sheet
excel_bytes = BytesIO()
df.to_excel(excel_bytes, index=False)
st.download_button(
    label="📥 Télécharger Excel",
    data=excel_bytes.getvalue(),
    file_name="gasoil_records.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
