"""
Hafta 4 — Streamlit Dashboard
Dosya bazli severity heat map + ozet metrikler + bulgu tablosu.

Calistirma:
    streamlit run streamlit_app.py
(Taranacak repo yolu kenar cubugundan secilir; varsayilan 'repo')
"""
import glob, os
from collections import Counter
import pandas as pd
import plotly.express as px
import streamlit as st

from pipeline import run as run_pipeline

LANG_OF = {".c": "c", ".py": "python", ".js": "javascript", ".java": "java"}
SEVS = ["P0", "P1", "P2", "P3"]


@st.cache_data
def scan_repo(repo: str):
    """Repo'yu tarayip bulgulari dict listesi olarak dondurur (cache'li)."""
    rows = []
    for path in sorted(glob.glob(os.path.join(repo, "*"))):
        ext = os.path.splitext(path)[1]
        if ext in LANG_OF:
            for f in run_pipeline(path, LANG_OF[ext]):
                rows.append({
                    "file": path.replace("\\", "/").split("/")[-1],
                    "line": f.line, "func": f.func or "-",
                    "severity": f.severity, "rule": f.rule.split("  ")[0],
                })
    return rows


def heatmap_matrix(rows):
    """Dosya x severity sayim matrisi (heat map icin)."""
    files = sorted({r["file"] for r in rows})
    data = {s: [sum(1 for r in rows if r["file"] == fn and r["severity"] == s)
                for fn in files] for s in SEVS}
    return pd.DataFrame(data, index=files)


# --- UI ---------------------------------------------------------------------
st.set_page_config(page_title="Technical Debt Dashboard", layout="wide")
st.title("Technical Debt Dashboard")

repo = st.sidebar.text_input("Repo klasoru", value="repo")
rows = scan_repo(repo)

if not rows:
    st.warning(f"'{repo}' klasorunde analiz edilecek dosya bulunamadi.")
    st.stop()

# Ozet metrikler
counts = Counter(r["severity"] for r in rows)
c0, c1, c2, c3, c4 = st.columns(5)
c0.metric("Toplam", len(rows))
c1.metric("P0 (kritik)", counts.get("P0", 0))
c2.metric("P1", counts.get("P1", 0))
c3.metric("P2", counts.get("P2", 0))
c4.metric("P3", counts.get("P3", 0))

# Heat map: dosya x severity
st.subheader("Dosya bazli heat map")
mat = heatmap_matrix(rows)
fig = px.imshow(mat, text_auto=True, color_continuous_scale="Reds",
                labels=dict(x="Onem", y="Dosya", color="Bulgu"),
                aspect="auto")
st.plotly_chart(fig, use_container_width=True)

# Bulgu tablosu
st.subheader("Tum bulgular")
df = pd.DataFrame(rows).sort_values(["severity", "file", "line"])
st.dataframe(df, use_container_width=True, hide_index=True)
