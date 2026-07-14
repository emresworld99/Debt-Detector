"""
Hafta 4 — MCP Sunucusu (FastMCP)
GitHub ve Jira araclarini MCP protokolu uzerinden sunar.

Gercek GitHub/Jira MCP sunuculari API token + gercek hesap ister. Demo icin
ayni ARAC ARAYUZUNU sunan ama sonuclari yerel JSON'a yazan bir sunucu yaziyoruz.
Protokol acisindan fark yok: istemci araclari kesfeder ve cagirir.
Gercege gecis = sadece istemcideki sunucu adresini degistirmek.

Calistirma (istemci bunu otomatik alt surec olarak baslatir):
    python3 mcp_server.py
"""
import json, os
from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("debt-detector-actions")

OUT_DIR = "mcp_output"
os.makedirs(OUT_DIR, exist_ok=True)


def _append(fname: str, record: dict) -> int:
    """Kaydi JSON dosyasina ekler, toplam kayit sayisini doner."""
    path = os.path.join(OUT_DIR, fname)
    data = []
    if os.path.exists(path):
        with open(path, encoding="utf8") as f:
            data = json.load(f)
    record["created_at"] = datetime.now().isoformat(timespec="seconds")
    data.append(record)
    with open(path, "w", encoding="utf8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return len(data)


# --- MCP ARACLARI -----------------------------------------------------------
# @mcp.tool() dekoratoru fonksiyonu MCP araci olarak ILAN eder.
# Fonksiyon adi  -> arac adi
# Docstring      -> aracin aciklamasi (LLM bunu okur)
# Tip ipuclari   -> JSON sema (parametre tipleri)

@mcp.tool()
def create_pr_comment(file: str, line: int, severity: str, message: str) -> str:
    """Tespit edilen soruna GitHub pull request yorumu ekler.

    Args:
        file: Sorunun bulundugu dosya adi
        line: Satir numarasi
        severity: Onem derecesi (P0-P3)
        message: Yorum metni
    """
    n = _append("github_pr_comments.json", {
        "file": file, "line": line, "severity": severity, "body": message,
    })
    return f"PR yorumu eklendi: {file}:{line} (toplam {n} yorum)"


@mcp.tool()
def create_ticket(title: str, severity: str, description: str) -> str:
    """Jira'da yeni bir issue (ticket) olusturur. P0-P1 bulgular icin kullanilir.

    Args:
        title: Ticket basligi
        severity: Onem derecesi (P0-P3)
        description: Detayli aciklama
    """
    n = _append("jira_tickets.json", {
        "key": f"DEBT-{n_next():03d}", "title": title,
        "priority": {"P0": "Highest", "P1": "High",
                     "P2": "Medium", "P3": "Low"}.get(severity, "Medium"),
        "severity": severity, "description": description,
    })
    return f"Jira ticket olusturuldu: {title} (toplam {n} ticket)"


def n_next() -> int:
    path = os.path.join(OUT_DIR, "jira_tickets.json")
    if not os.path.exists(path):
        return 1
    with open(path, encoding="utf8") as f:
        return len(json.load(f)) + 1


if __name__ == "__main__":
    mcp.run(transport="stdio")   # istemci ile standart girdi/cikti uzerinden konusur
