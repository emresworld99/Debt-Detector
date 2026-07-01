"""
Hafta 2 — LLM aciklama katmani
Bir bulgu + ilgili kod parcasi alir, Claude'dan "neden riskli + nasil duzeltilir"
aciklamasi urettir. API anahtari yoksa None doner (pipeline yine calisir).

Kendi makinende: setx ANTHROPIC_API_KEY "sk-ant-..." yaptiktan sonra otomatik devreye girer.
"""
import os

MODEL = "claude-sonnet-4-6"   # aciklama icin sonnet yeterli; istersen degistir


def explain(finding, code_snippet: str) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None   # anahtar yok -> aciklama uretme, pipeline devam etsin

    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    client = Anthropic()   # anahtari ortam degiskeninden okur
    prompt = (
        f"Asagidaki kod parcasinda '{finding.rule}' turunde bir sorun tespit edildi "
        f"(satir {finding.line}). Kisa ve teknik bir sekilde: (1) bu neden risklidir, "
        f"(2) nasil duzeltilir. En fazla 4 cumle.\n\n"
        f"Sorun: {finding.message}\n\nKod:\n{code_snippet}"
    )
    try:
        msg = client.messages.create(
            model=MODEL, max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None
