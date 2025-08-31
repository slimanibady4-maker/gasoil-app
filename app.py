import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
from io import BytesIO
import uuid

# =========================
# CONFIG
# =========================
BASE_DIR = r"C:\Users\slima\Desktop\BHM\gasoil\gasoil_site_data"
EXCEL_PATH = os.path.join(BASE_DIR, "gasoil_records.xlsx")
CSV_PATH = os.path.join(BASE_DIR, "gasoil_records.csv")  # (optionnel si tu veux aussi du CSV)
JUSTIF_DIR = os.path.join(BASE_DIR, "justifications")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(JUSTIF_DIR, exist_ok=True)

# =========================
# HELPERS
# =========================
def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ID", "Technicien", "Montant", "Date", "Justification", "Photos"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def _to_date_series(s):
    """Convertit une série en datetime.date (en ignorant les valeurs invalides)."""
    return pd.to_datetime(s, errors="coerce").dt.date

def load_data():
    # Charge depuis Excel si présent, sinon DF vide
    if os.path.exists(EXCEL_PATH):
        try:
            df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    df = _ensure_cols(df)
    # Normaliser la colonne Date en datetime.date
    df["Date"] = _to_date_series(df["Date"])
    return df

def save_excel(df: pd.DataFrame):
    # Sauvegarde robuste en Excel (openpyxl requis dans ton venv local)
    df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")

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
    name = name.strip().replace(" ", "_")
    return name or "inconnu"

def parse_amount_to_float(txt: str):
    """Essaie d'extraire un nombre depuis un montant texte (ex: '150 €', '150,50'). Retourne None si impossible."""
    if txt is None:
        return None
    s = str(txt)
    # Nettoyage basique: enlever € et espaces, remplacer virgule décimale par point
    s = s.replace("€", "").replace("EUR", "").replace("eur", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

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

# Charger les données existantes
st.session_state.setdefault("df", load_data())

# =========================
# FORMULAIRE DE SAISIE
# =========================
st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *", placeholder="Ex: Ahmed B.")
        montant = st.text_input("Montant (€) *", placeholder="Ex: 50, 50.00, 50 € (texte libre)")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
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

        # Dossier par technicien (centralise tous ses justificatifs)
        tech_folder = sanitize_filename(technicien)
        dest_dir = os.path.join(JUSTIF_DIR, tech_folder)
        os.makedirs(dest_dir, exist_ok=True)

        saved_paths = []
        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                unique_name = f"{date_val.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}{ext}"
                out_path = os.path.join(dest_dir, unique_name)
                with open(out_path, "wb") as out:
                    out.write(f.getbuffer())
                rel_path = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
                saved_paths.append(rel_path)

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),          # <-- texte libre conservé
            "Date": date_val,                    # <-- déjà un datetime.date
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

df = st.session_state["df"].copy()
# S'assurer que la colonne Date est bien en date (au cas où)
df["Date"] = _to_date_series(df["Date"])

# Valeurs par défaut pour les filtres (toujours des 'date')
if df.empty or df["Date"].dropna().empty:
    default_min = default_max = date.today()
else:
    default_min = df["Date"].dropna().min()
    default_max = df["Date"].dropna().max()

with st.expander("🔎 Filtres"):
    c1, c2, c3 = st.columns(3)
    with c1:
        techs = sorted([t for t in df["Technicien"].dropna().unique()]) if not df.empty else []
        tech_filter = st.multiselect("Techniciens", techs)
    with c2:
        date_min = st.date_input("Date min", value=default_min)
    with c3:
        date_max = st.date_input("Date max", value=default_max)

# Application des filtres (tout en datetime.date)
fdf = df.copy()
if not fdf.empty:
    fdf["Date"] = _to_date_series(fdf["Date"])
    if tech_filter:
        fdf = fdf[fdf["Technicien"].isin(tech_filter)]
    if date_min:
        fdf = fdf[fdf["Date"] >= date_min]
    if date_max:
        fdf = fdf[fdf["Date"] <= date_max]

st.dataframe(fdf, use_container_width=True)

# Total montant filtré (conversion souple)
if not fdf.empty:
    amounts = [parse_amount_to_float(x) for x in fdf["Montant"]]
    amounts = [x for x in amounts if x is not None]
    if amounts:
        total = sum(amounts)
        st.metric(label="Total (filtré)", value=f"{total:,.2f} €")
    else:
        st.metric(label="Total (filtré)", value="—")
        st.info("Aucun montant numérique détecté dans la sélection (saisie libre).")

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
import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
from io import BytesIO
import uuid

# =========================
# CONFIG
# =========================
BASE_DIR = r"C:\Users\slima\Desktop\BHM\gasoil\gasoil_site_data"
EXCEL_PATH = os.path.join(BASE_DIR, "gasoil_records.xlsx")
CSV_PATH = os.path.join(BASE_DIR, "gasoil_records.csv")  # (optionnel si tu veux aussi du CSV)
JUSTIF_DIR = os.path.join(BASE_DIR, "justifications")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(JUSTIF_DIR, exist_ok=True)

# =========================
# HELPERS
# =========================
def _ensure_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ID", "Technicien", "Montant", "Date", "Justification", "Photos"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]

def _to_date_series(s):
    """Convertit une série en datetime.date (en ignorant les valeurs invalides)."""
    return pd.to_datetime(s, errors="coerce").dt.date

def load_data():
    # Charge depuis Excel si présent, sinon DF vide
    if os.path.exists(EXCEL_PATH):
        try:
            df = pd.read_excel(EXCEL_PATH, engine="openpyxl")
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    df = _ensure_cols(df)
    # Normaliser la colonne Date en datetime.date
    df["Date"] = _to_date_series(df["Date"])
    return df

def save_excel(df: pd.DataFrame):
    # Sauvegarde robuste en Excel (openpyxl requis dans ton venv local)
    df.to_excel(EXCEL_PATH, index=False, engine="openpyxl")

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
    name = name.strip().replace(" ", "_")
    return name or "inconnu"

def parse_amount_to_float(txt: str):
    """Essaie d'extraire un nombre depuis un montant texte (ex: '150 €', '150,50'). Retourne None si impossible."""
    if txt is None:
        return None
    s = str(txt)
    # Nettoyage basique: enlever € et espaces, remplacer virgule décimale par point
    s = s.replace("€", "").replace("EUR", "").replace("eur", "").replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

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

# Charger les données existantes
st.session_state.setdefault("df", load_data())

# =========================
# FORMULAIRE DE SAISIE
# =========================
st.subheader("📝 Nouvelle saisie")
with st.form("form_saisie", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        technicien = st.text_input("Nom du technicien *", placeholder="Ex: Ahmed B.")
        montant = st.text_input("Montant (€) *", placeholder="Ex: 50, 50.00, 50 € (texte libre)")
    with col2:
        date_val = st.date_input("Date *", value=date.today())
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

        # Dossier par technicien (centralise tous ses justificatifs)
        tech_folder = sanitize_filename(technicien)
        dest_dir = os.path.join(JUSTIF_DIR, tech_folder)
        os.makedirs(dest_dir, exist_ok=True)

        saved_paths = []
        if fichiers:
            for f in fichiers:
                ext = os.path.splitext(f.name)[1].lower()
                unique_name = f"{date_val.strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}{ext}"
                out_path = os.path.join(dest_dir, unique_name)
                with open(out_path, "wb") as out:
                    out.write(f.getbuffer())
                rel_path = os.path.relpath(out_path, BASE_DIR).replace("\\", "/")
                saved_paths.append(rel_path)

        new_row = {
            "ID": rec_id,
            "Technicien": technicien.strip(),
            "Montant": montant.strip(),          # <-- texte libre conservé
            "Date": date_val,                    # <-- déjà un datetime.date
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

df = st.session_state["df"].copy()
# S'assurer que la colonne Date est bien en date (au cas où)
df["Date"] = _to_date_series(df["Date"])

# Valeurs par défaut pour les filtres (toujours des 'date')
if df.empty or df["Date"].dropna().empty:
    default_min = default_max = date.today()
else:
    default_min = df["Date"].dropna().min()
    default_max = df["Date"].dropna().max()

with st.expander("🔎 Filtres"):
    c1, c2, c3 = st.columns(3)
    with c1:
        techs = sorted([t for t in df["Technicien"].dropna().unique()]) if not df.empty else []
        tech_filter = st.multiselect("Techniciens", techs)
    with c2:
        date_min = st.date_input("Date min", value=default_min)
    with c3:
        date_max = st.date_input("Date max", value=default_max)

# Application des filtres (tout en datetime.date)
fdf = df.copy()
if not fdf.empty:
    fdf["Date"] = _to_date_series(fdf["Date"])
    if tech_filter:
        fdf = fdf[fdf["Technicien"].isin(tech_filter)]
    if date_min:
        fdf = fdf[fdf["Date"] >= date_min]
    if date_max:
        fdf = fdf[fdf["Date"] <= date_max]

st.dataframe(fdf, use_container_width=True)

# Total montant filtré (conversion souple)
if not fdf.empty:
    amounts = [parse_amount_to_float(x) for x in fdf["Montant"]]
    amounts = [x for x in amounts if x is not None]
    if amounts:
        total = sum(amounts)
        st.metric(label="Total (filtré)", value=f"{total:,.2f} €")
    else:
        st.metric(label="Total (filtré)", value="—")
        st.info("Aucun montant numérique détecté dans la sélection (saisie libre).")

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
