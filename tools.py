"""
Hafta 2 — Harici arac adaptorleri
semgrep ve bandit'i calistirip ciktilarini bizim Finding formatimiza cevirir.
Boylece bizim AST dedektorlerimizle AYNI listede birlesebilirler.
"""
import json, subprocess, shutil
from analyzer import Finding

# Harici araclarin siddet etiketlerini bizim P0-P3 semamiza esle
SEMGREP_SEV = {"ERROR": "P0", "WARNING": "P2", "INFO": "P3"}
BANDIT_SEV  = {"HIGH": "P1", "MEDIUM": "P2", "LOW": "P3"}


def run_semgrep(path, rules="semgrep_rules/c_rules.yaml"):
    """semgrep'i verilen kural dosyasiyla calistirip Finding listesi dondurur."""
    if shutil.which("semgrep") is None:
        return []   # semgrep kurulu degilse sessizce atla
    try:
        out = subprocess.run(
            ["semgrep", "--config", rules, path, "--json",
             "--metrics=off", "--disable-version-check"],
            capture_output=True, text=True, timeout=120,
        )
        data = json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return []
    findings = []
    for r in data.get("results", []):
        sev = SEMGREP_SEV.get(r["extra"]["severity"], "P2")
        findings.append(Finding(
            severity=sev,
            rule="semgrep:" + r["check_id"].split(".")[-1],
            line=r["start"]["line"],
            func=None,   # semgrep fonksiyon adi vermez
            message=r["extra"]["message"].strip(),
        ))
    return findings


def run_bandit(path):
    """bandit'i calistirir (yalnizca Python dosyalari icin anlamli)."""
    if shutil.which("bandit") is None:
        return []
    try:
        out = subprocess.run(
            ["bandit", "-f", "json", path],
            capture_output=True, text=True, timeout=120,
        )
        data = json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return []
    findings = []
    for r in data.get("results", []):
        sev = BANDIT_SEV.get(r["issue_severity"], "P3")
        findings.append(Finding(
            severity=sev,
            rule="bandit:" + r["test_id"],
            line=r["line_number"],
            func=None,
            message=r["issue_text"].strip(),
        ))
    return findings
