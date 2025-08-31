import streamlit as st
import pandas as pd
import os
import uuid
from datetime import date
from io import BytesIO
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =========================
# CONFIG GOOGLE
# =========================
SERVICE_ACCOUNT_FILE = "gasoil-uploader-33796bcfdb57.json"
SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]

# Auth Google Sheets
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

# Auth Google Drive
drive_service = build('drive', 'v3', credentials=creds)

# Google Sheet
SHEET_NAME = "Gasoil_Records"
try:
    sh = gc.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sh = gc.create(SHEET_NAME)
worksheet = sh.sheet1

# Google Drive folder ID pour les justificatifs
DRIVE_FOLDER_ID = "1Drc-2yYlHd7mScOGp13ALKHUKQFneAEF"

# =========================
# HELPERS
# =========================
def _to_date_series(s):
    return pd.to_datetime(s, errors="coerce").dt.date

def load_data():
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
    except Exception:
        df = pd.DataFrame()
    df = _ensure_cols(df)
    df["Date"] = _to_date_series(df["Date"])
    return df

def _ensure_cols(df):
    cols = ["ID", "Technicien", "Montant", "Date", "Justification", "Photos"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

def save_to_sheet(df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def sanitize_filename(name):
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "-")
    return name.strip().replace(" ", "_") or "inconnu"

def parse_amount_to_float(txt):
    if txt is None:
        return None
    s = str(txt).replace("€", "").replace(",", ".").replace(" ", "")
    try:
        return float(s)
    except:
        return None

def upload_file_to_drive(local_path, folder_id):
    file_metadata = {'name': os.path.basename(local_path), 'parents': [folder_id]}
    media = MediaFileUpload(local_path, resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, name').execute()
    return file.get('id')

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer.getvalue()

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Gestion gasoil", page_icon="⛽", layout="wide")
st.title("⛽ Gestion des dépenses de gasoil")

st.session_state.setdefault("df", load_data())

# ---- Formulaire ----
st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *", placeholder="Ex: Ahmed B.")
        montant = st.text_input("Montant (€) *", placeholder="Ex: 50,50")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
        justification = st.text_area("Justification *", placeholder="Détails de la dépense")
    fichiers = st.file_uploader(
        "Photos justificatives (jpg, png, pdf) - plusieurs possibles",
        type=["jpg","jpeg","png","pdf"], accept_multiple_files=True
    )
    submitted = st.form_submit_button("💾 Enregistrer")

if submitted:
    errors = []
    if not technicien.strip(): errors.append("Nom requis")
    if not montant.strip(): errors.append("Montant requis")
    if not justification.strip(): errors.append("Justification requise")

    if errors:
        for e in errors: st.error(e)
    else:
        df = st.session_state["df"].copy()
        rec_id = str(uuid.uuid4())[:8]

        saved_paths = []
        if fichiers:
            for f in fichiers:
                tmp_path = f"temp_{uuid.uuid4().hex}_{f.name}"
                with open(tmp_path, "wb") as out:
                    out.write(f.getbuffer())
                file_id = upload_file_to_drive(tmp_path, DRIVE_FOLDER_ID)
                os.remove(tmp_path)
                saved_paths.append(f"https://drive.google.com/file/d/{file_id}/view?usp=sharing")

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),
            "Date": date_val,
            "Justification": justification.strip(),
            "Photos": "; ".join(saved_paths)
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_to_sheet(df)
        st.session_state["df"] = df
        st.success("✅ Saisie enregistrée et fichiers envoyés sur Drive !")

# ---- Historique ----
st.markdown("---")
st.subheader("📊 Historique")
df = st.session_state["df"].copy()
df["Date"] = _to_date_series(df["Date"])
st.dataframe(df, use_container_width=True)

st.markdown("---")
st.download_button(
    "📥 Télécharger Excel",
    data=to_excel_bytes(df),
    file_name="gasoil_records.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
