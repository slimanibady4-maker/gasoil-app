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
CSV_PATH = os.path.join(BASE_DIR, "gasoil_records.csv")
JUSTIF_DIR = os.path.join(BASE_DIR, "justifications")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(JUSTIF_DIR, exist_ok=True)

# =========================
# HELPERS
# =========================
def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ID", "Technicien", "Montant (€)", "Date", "Justification", "Photos"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def load_data() -> pd.DataFrame:
    """Charge d'abord depuis CSV (robuste), sinon tente Excel, sinon DF vide."""
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
        except Exception:
            df = pd.DataFrame()
    elif os.path.exists(EXCEL_PATH):
        try:
            # Tente openpyxl puis fallback auto
            try:
                df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
            except Exception:
                df = pd.read_excel(EXCEL_PATH)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    df = _ensure_columns(df)
    # Normalise la date (si texte)
    try:
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
    except Exception:
        pass
    return df

def save_data(df: pd.DataFrame):
    """Persistance principale en CSV (pas de dépendances)."""
    df.to_csv(CSV_PATH, index=False)

def to_excel_bytes(df: pd.DataFrame):
    """Essaie de produire un XLSX en mémoire. Fallback: None si moteur absent."""
    engine = None
    try:
        import openpyxl  # noqa: F401
        engine = "openpyxl"
    except Exception:
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except Exception:
            return None

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine=engine) as writer:
        df.to_excel(writer, index=False, sheet_name="Gasoil")
    buffer.seek(0)
    return buffer.getvalue()

def sanitize_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        name = name.replace(ch, "-")
    return (name.strip().replace(" ", "_") or "inconnu")

# =========================
# UI
# =========================
st.set_page_config(page_title="Gestion des dépenses de gasoil", page_icon="⛽", layout="wide")
st.title("⛽ Gestion des dépenses de gasoil – Saisie & Export")

with st.expander("⚙️ Emplacement des fichiers"):
    st.write(f"**Dossier des données :** `{BASE_DIR}`")
    st.write(f"**Fichier CSV (persistance) :** `{CSV_PATH}`")
    st.write(f"**Fichier Excel (export si possible) :** `{EXCEL_PATH}`")
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
        montant = st.text_input("Montant (€) *", placeholder="Ex: 150, 150.50, 150 € (texte libre)")
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

        # Un seul dossier par technicien -> centralise tous ses justificatifs
        tech_folder = sanitize_filename(technicien)
        dest_dir = os.path.join(JUSTIF_DIR, tech_folder)
        os.makedirs(dest_dir, exist_ok=True)

        saved_paths = []
        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                unique_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
                out_path = os.path.join(dest_dir, unique_name)
                with open(out_path, "wb") as out:
                    out.write(f.getbuffer())
                rel_path = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
                saved_paths.append(rel_path)

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant (€)": montant.strip(),   # texte libre
            "Date": pd.to_datetime(date_val).date(),
            "Justification": justification.strip(),
            "Photos": "; ".join(saved_paths) if saved_paths else ""
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Persistance robuste (CSV)
        save_data(df)
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

with st.expander("🔎 Filtres"):
    c1, c2, c3 = st.columns(3)
    with c1:
        techs = sorted([t for t in df["Technicien"].dropna().unique()]) if not df.empty else []
        tech_filter = st.multiselect("Techniciens", techs)
    with c2:
        date_min = st.date_input("Date min", value=(pd.to_datetime(df["Date"]).min().date() if not df.empty else datetime.today().date()))
    with c3:
        date_max = st.date_input("Date max", value=(pd.to_datetime(df["Date"]).max().date() if not df.empty else datetime.today().date()))

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

# Boutons de téléchargement
excel_bytes = to_excel_bytes(df)
if excel_bytes is not None:
    st.download_button(
        label="📥 Télécharger en Excel (.xlsx)",
        data=excel_bytes,
        file_name="gasoil_records.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    # Fallback CSV si aucun moteur Excel n'est dispo
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="📥 Télécharger en CSV (fallback)",
        data=csv_bytes,
        file_name="gasoil_records.csv",
        mime="text/csv",
    )
    st.info("ℹ️ Export Excel indisponible (ni openpyxl ni xlsxwriter). Export CSV proposé à la place.")

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
