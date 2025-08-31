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
SERVICE_ACCOUNT_FILE = "gasoil-uploader-33796bcfdb57.json"
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Authentification Google Sheets
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

# Authentification Google Drive
gauth = GoogleAuth()
gauth.ServiceAuth(SERVICE_ACCOUNT_FILE)
drive = GoogleDrive(gauth)

# Ouvrir ou créer le Google Sheet
try:
    sh = gc.open("Gasoil_Records")
except gspread.SpreadsheetNotFound:
    sh = gc.create("Gasoil_Records")
worksheet = sh.sheet1

# ID du dossier Google Drive où stocker les justificatifs
# Mets ici ton dossier partagé Drive
FOLDER_ID = "1Drc-2yYlHd7mScOGp13ALKHUKQFneAEF"

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

def save_to_google_sheet(row: dict):
    # Ajouter ligne dans Google Sheet
    worksheet.append_row([row["ID"], row["Technicien"], row["Montant"], str(row["Date"]), row["Justification"], row["Photos"]])

def upload_file_to_drive(local_file_path, folder_id=FOLDER_ID):
    file_drive = drive.CreateFile({'title': os.path.basename(local_file_path), 'parents': [{'id': folder_id}]})
    file_drive.SetContentFile(local_file_path)
    file_drive.Upload()
    return file_drive['id']

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Gasoil")
    buffer.seek(0)
    return buffer.getvalue()

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Gestion Gasoil", page_icon="⛽", layout="wide")
st.title("⛽ Gestion des dépenses de gasoil – Saisie & Export")

st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *")
        montant = st.text_input("Montant (€) *")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
        justification = st.text_area("Justification *")
    fichiers = st.file_uploader(
        "Photos justificatives (plusieurs possibles)",
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
        saved_paths = []

        # Enregistrer fichiers sur Google Drive
        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                tmp_path = f"{uuid.uuid4().hex}{ext}"
                with open(tmp_path, "wb") as out:
                    out.write(f.getbuffer())
                file_id = upload_file_to_drive(tmp_path)
                saved_paths.append(f"https://drive.google.com/file/d/{file_id}/view?usp=sharing")
                os.remove(tmp_path)  # Supprimer fichier local temporaire

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),
            "Date": date_val,
            "Justification": justification.strip(),
            "Photos": "; ".join(saved_paths)
        }

        # Enregistrer dans Google Sheet
        save_to_google_sheet(new_row)
        st.success("✅ Saisie enregistrée et fichiers sauvegardés sur Google Drive !")

        if saved_paths:
            st.caption("Fichiers enregistrés :")
            for p in saved_paths:
                st.write(f"• {p}")

# =========================
# AFFICHAGE DES DONNÉES
# =========================
st.markdown("---")
st.subheader("📊 Historique des dépenses")

# Lire toutes les données depuis Google Sheet
data = worksheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    df["Montant_float"] = [parse_amount_to_float(x) for x in df["Montant"]]
    st.dataframe(df, use_container_width=True)
    st.metric(label="Total général", value=f"{df['Montant_float'].sum():,.2f} €" if not df['Montant_float'].isna().all() else "—")
else:
    st.info("Aucune donnée pour le moment.")

# Télécharger Excel
if not df.empty:
    excel_bytes = to_excel_bytes(df)
    st.download_button(
        label="📥 Télécharger l'Excel complet",
        data=excel_bytes,
        file_name="gasoil_records.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
