import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO
import uuid

# =========================
# CONFIG
# =========================
BASE_DIR = "gasoil_site_data"
EXCEL_PATH = os.path.join(BASE_DIR, "gasoil_records.xlsx")
JUSTIF_DIR = os.path.join(BASE_DIR, "justifications")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(JUSTIF_DIR, exist_ok=True)

# =========================
# HELPERS
# =========================
def load_data():
    if os.path.exists(EXCEL_PATH):
        try:
            df = pd.read_excel(EXCEL_PATH)
        except Exception:
            df = pd.DataFrame(columns=["ID", "Technicien", "Montant", "Date", "Justification", "Photos"])
    else:
        df = pd.DataFrame(columns=["ID", "Technicien", "Montant", "Date", "Justification", "Photos"])
    expected_cols = ["ID", "Technicien", "Montant", "Date", "Justification", "Photos"]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = None
    return df[expected_cols]

def save_excel(df: pd.DataFrame):
    df.to_excel(EXCEL_PATH, index=False)

def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Gasoil")
    buffer.seek(0)
    return buffer.getvalue()

def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "-")
    return name.strip().replace(" ", "_") or "inconnu"

# =========================
# UI
# =========================
st.set_page_config(page_title="Gestion des dépenses de gasoil", page_icon="⛽", layout="wide")
st.title("⛽ Gestion des dépenses de gasoil – Saisie & Export Excel")

with st.expander("⚙️ Emplacement des fichiers (cliquer pour voir)"):
    st.write(f"**Dossier des données :** `{BASE_DIR}`")
    st.write(f"**Fichier Excel :** `{EXCEL_PATH}`")
    st.write(f"**Dossier des justificatifs :** `{JUSTIF_DIR}`")

st.markdown("---")

# Load existing data
st.session_state.setdefault("df", load_data())

# =========================
# FORMULAIRE DE SAISIE
# =========================
st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *", placeholder="Ex: Ahmed B.")
        montant = st.text_input("Montant * (ex: 150, 20.5 €, etc.)")
    with col2:
        date_val = st.date_input("Date *", datetime.today())
        justification = st.text_area("Justification *", placeholder="Détails de la dépense, station, véhicule, etc.")
    fichiers = st.file_uploader(
        "Photos justificatives (plusieurs possibles)",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        accept_multiple_files=True,
        help="Ajoutez autant de fichiers que nécessaire (images ou PDF)."
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
        df = st.session_state["df"].copy()
        rec_id = str(uuid.uuid4())[:8]

        # Dossier unique par technicien pour regrouper les justificatifs
        tech_folder = sanitize_filename(technicien)
        dest_dir = os.path.join(JUSTIF_DIR, tech_folder)
        os.makedirs(dest_dir, exist_ok=True)

        saved_paths = []
        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                unique_name = f"{date_val}_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
                out_path = os.path.join(dest_dir, unique_name)
                with open(out_path, "wb") as out:
                    out.write(f.getbuffer())
                rel_path = os.path.relpath(out_path, BASE_DIR)
                saved_paths.append(rel_path.replace("\\", "/"))

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),
            "Date": pd.to_datetime(date_val).date(),
            "Justification": justification.strip(),
            "Photos": "; ".join(saved_paths) if saved_paths else ""
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Sauvegarde
        save_excel(df)
        st.session_state["df"] = df
        st.success("✅ Saisie enregistrée et fichiers sauvegardés !")

        if saved_paths:
            st.caption("Fichiers enregistrés :")
            for p in saved_paths:
                st.write(f"• `{p}`")

# =========================
# TABLEAU & EXPORT
# =========================
st.markdown("---")
st.subheader("📊 Historique des dépenses")

df = st.session_state["df"]

# Filtres
with st.expander("🔎 Filtres"):
    c1, c2, c3 = st.columns(3)
    with c1:
        techs = sorted([t for t in df["Technicien"].dropna().unique()]) if not df.empty else []
        tech_filter = st.multiselect("Techniciens", techs)
    with c2:
        date_min = st.date_input("Date min", value=df["Date"].min() if not df.empty else datetime.today())
    with c3:
        date_max = st.date_input("Date max", value=df["Date"].max() if not df.empty else datetime.today())

fdf = df.copy()
if not fdf.empty:
    fdf["Date"] = pd.to_datetime(fdf["Date"]).dt.date
    if tech_filter:
        fdf = fdf[fdf["Technicien"].isin(tech_filter)]
    if date_min:
        fdf = fdf[fdf["Date"] >= date_min]
    if date_max:
        fdf = fdf[fdf["Date"] <= date_max]

st.dataframe(fdf, use_container_width=True)

# Download Excel
excel_bytes = to_excel_bytes(df)
st.download_button(
    label="📥 Télécharger l'Excel complet",
    data=excel_bytes,
    file_name="gasoil_records.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# =========================
# APERCU DES PHOTOS
# =========================
st.markdown("---")
st.subheader("🖼️ Aperçu rapide des justificatifs récents")

if not df.empty:
    recent = df.tail(10)
    imgs = []
    for paths in recent["Photos"].fillna(""):
        for p in [x.strip() for x in paths.split(";") if x.strip()]:
            full = os.path.join(BASE_DIR, p)
            if os.path.exists(full) and os.path.splitext(full)[1].lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                imgs.append(full)
    if imgs:
        cols = st.columns(5)
        for i, img in enumerate(imgs[:20]):
            with cols[i % 5]:
                st.image(img, use_container_width=True)
    else:
        st.info("Pas d'images à afficher pour le moment (ou fichiers PDF uniquement).")
else:
    st.info("Aucune donnée encore. Utilisez le formulaire ci-dessus pour commencer.")
