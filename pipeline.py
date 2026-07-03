"""
Hafta 2 — Birlesik statik analiz pipeline'i (nihai cikti)
Bulgulari uc kaynaktan toplar, tekrarlari eler, P0-P3 siralar,
istege bagli olarak LLM aciklamasi ekler.

Kullanim:
    python3 pipeline.py repo/db.c c
    python3 pipeline.py repo/db.c c --explain     # LLM aciklamalariyla (API key gerekir)
"""
import sys
from analyzer import analyze, Finding, SEVERITY_RANK
from tools import run_semgrep, run_bandit
from explain import explain


def _bucket(rule: str) -> str:
    """Farkli araclarin ayni soruna verdigi isimleri ortak bir kovaya indir."""
    r = rule.lower()
    if "secret" in r or "b105" in r: return "secret"
    if "sql" in r:                   return "sql"
    if "loop" in r:                  return "infinite_loop"
    if "complex" in r:               return "complexity"
    if "todo" in r:                  return "todo"
    if "god" in r or "long" in r:    return "size"
    return r


def _dedup(findings: list[Finding]) -> list[Finding]:
    """
    Ayni (satir, kova) ikilisini tek bulguda birlestir.
    Temsilciyi sec: once en yuksek siddet, sonra fonksiyon adi olan.
    """
    groups: dict[tuple, list[Finding]] = {}
    for f in findings:
        groups.setdefault((f.line, _bucket(f.rule)), []).append(f)

    merged = []
    for group in groups.values():
        best = min(group, key=lambda f: (SEVERITY_RANK[f.severity], 0 if f.func else 1))
        # hangi araclarin isaretledigini rule alanina yaz (seffaflik)
        tools = sorted({(f.rule.split(":")[0] if ":" in f.rule else "ast") for f in group})
        best.rule = best.rule + f"  [kaynak: {', '.join(tools)}]"
        merged.append(best)

    merged.sort(key=lambda f: (SEVERITY_RANK[f.severity], f.line))
    return merged


def run(path: str, lang: str, do_explain: bool = False) -> list[Finding]:
    findings = analyze(path, lang)          # (a) kendi AST dedektorlerimiz
    findings += run_semgrep(path)           # (b) semgrep
    if lang == "python":
        findings += run_bandit(path)        # (b) bandit (yalnizca Python)

    findings = _dedup(findings)             # tekrarlari birlestir

    if do_explain:                          # (c) LLM aciklamasi (yalnizca P0)
        src_lines = open(path, encoding="utf8").read().splitlines()
        for f in findings:
            if f.severity == "P0":
                lo = max(0, f.line - 3); hi = min(len(src_lines), f.line + 3)
                snippet = "\n".join(src_lines[lo:hi])
                f.message += _explain_or_note(f, snippet)
    return findings


def _explain_or_note(f, snippet):
    text = explain(f, snippet)
    return f"\n        -> Aciklama: {text}" if text else ""


if __name__ == "__main__":
    path, lang = sys.argv[1], sys.argv[2]
    do_explain = "--explain" in sys.argv

    findings = run(path, lang, do_explain)
    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    ozet = ", ".join(f"{k}:{counts[k]}" for k in sorted(counts))
    print(f"\n{path}  —  {len(findings)} bulgu  ({ozet})\n")
    for f in findings:
        loc = f"{f.func}()" if f.func else "(dosya genel)"
        print(f"  [{f.severity}] {f.rule}")
        print(f"        satir {f.line}  {loc}")
        print(f"        {f.message}\n")
