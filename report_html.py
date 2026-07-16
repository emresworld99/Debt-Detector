"""
Hafta 4 — Debt Raporu (Markdown + HTML) + trend takibi
Repo'yu tarar, ozet cikarir, gecmisi saklar ve bir onceki calismaya gore
debt artti mi azaldi mi hesaplar. reports/ klasorune yazar.

Calistirma:
    python3 report_html.py repo
"""
import glob, json, os, sys
from datetime import datetime
from collections import Counter
from pipeline import run as run_pipeline

LANG_OF = {".c": "c", ".py": "python", ".js": "javascript", ".java": "java"}
REPORTS = "reports"
HISTORY = os.path.join(REPORTS, "history.json")
SEV_COLOR = {"P0": "#d32f2f", "P1": "#f57c00", "P2": "#fbc02d", "P3": "#7cb342"}


def scan_repo(repo):
    findings = []
    for path in sorted(glob.glob(os.path.join(repo, "*"))):
        ext = os.path.splitext(path)[1]
        if ext in LANG_OF:
            for f in run_pipeline(path, LANG_OF[ext]):
                f.file = path.replace("\\", "/").split("/")[-1]
                findings.append(f)
    return findings


def load_history():
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf8") as f:
            return json.load(f)
    return []


def trend_line(current_total, history):
    """Bir onceki calismayla karsilastir."""
    if not history:
        return "Ilk calisma — karsilastirma yok."
    prev = history[-1]["total"]
    diff = current_total - prev
    if diff > 0:
        return f"Debt ARTTI: onceki {prev} -> simdi {current_total} (+{diff})"
    if diff < 0:
        return f"Debt AZALDI: onceki {prev} -> simdi {current_total} ({diff})"
    return f"Debt AYNI: {current_total}"


def build(repo):
    os.makedirs(REPORTS, exist_ok=True)
    findings = scan_repo(repo)
    counts = Counter(f.severity for f in findings)
    by_file = Counter(f.file for f in findings)
    total = len(findings)

    history = load_history()
    trend = trend_line(total, history)
    history.append({"time": datetime.now().isoformat(timespec="seconds"),
                    "total": total, "counts": dict(counts)})
    with open(HISTORY, "w", encoding="utf8") as f:
        json.dump(history, f, indent=2)

    # --- Markdown ---
    md = [f"# Technical Debt Raporu", f"_{datetime.now():%Y-%m-%d %H:%M}_", "",
          f"**Toplam bulgu:** {total}  ", f"**Trend:** {trend}", "",
          "## Onem dagilimi",
          "| Onem | Adet |", "|---|---|"]
    for s in ["P0", "P1", "P2", "P3"]:
        md.append(f"| {s} | {counts.get(s, 0)} |")
    md += ["", "## Dosya bazli", "| Dosya | Bulgu |", "|---|---|"]
    for fname, c in by_file.most_common():
        md.append(f"| {fname} | {c} |")
    md += ["", "## Bulgular", "| Onem | Dosya:Satir | Kural |", "|---|---|---|"]
    for f in sorted(findings, key=lambda x: (x.severity, x.file, x.line)):
        md.append(f"| {f.severity} | {f.file}:{f.line} | {f.rule.split('  ')[0]} |")
    md_text = "\n".join(md)
    with open(os.path.join(REPORTS, "debt_report.md"), "w", encoding="utf8") as f:
        f.write(md_text)

    # --- HTML ---
    rows = ""
    for f in sorted(findings, key=lambda x: (x.severity, x.file, x.line)):
        rows += (f"<tr><td><b style='color:{SEV_COLOR[f.severity]}'>{f.severity}</b></td>"
                 f"<td>{f.file}:{f.line}</td><td>{f.func or '-'}</td>"
                 f"<td>{f.rule.split('  ')[0]}</td></tr>")
    bars = ""
    for s in ["P0", "P1", "P2", "P3"]:
        c = counts.get(s, 0)
        bars += (f"<div style='margin:4px 0'><span style='display:inline-block;width:40px'>{s}</span>"
                 f"<span style='display:inline-block;background:{SEV_COLOR[s]};height:16px;"
                 f"width:{c*30+2}px'></span> {c}</div>")
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Technical Debt Raporu</title>
<style>body{{font-family:system-ui,Arial;margin:40px;color:#222}}
table{{border-collapse:collapse;margin-top:12px}}td,th{{border:1px solid #ccc;padding:6px 10px}}
th{{background:#2E75B6;color:#fff}}.trend{{padding:10px;background:#f4f4f4;border-radius:6px}}</style>
</head><body>
<h1>Technical Debt Raporu</h1>
<p>{datetime.now():%Y-%m-%d %H:%M} — Toplam <b>{total}</b> bulgu</p>
<p class="trend">Trend: {trend}</p>
<h2>Onem dagilimi</h2>{bars}
<h2>Bulgular</h2>
<table><tr><th>Onem</th><th>Konum</th><th>Fonksiyon</th><th>Kural</th></tr>{rows}</table>
</body></html>"""
    with open(os.path.join(REPORTS, "debt_report.html"), "w", encoding="utf8") as f:
        f.write(html)

    print(f"{total} bulgu. {trend}")
    print(f"Yazildi: reports/debt_report.md ve reports/debt_report.html")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "repo")
