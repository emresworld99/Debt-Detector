"""
Hafta 4 — MCP Istemcisi
Sunucuya baglanir, araclari kesfeder ve bulgulari araclara dagitir.
MCP protokol turu: sunucuyu alt surec baslat -> initialize -> list_tools -> call_tool.

Kural: P0  -> hem PR yorumu HEM Jira ticket
       P1  -> sadece Jira ticket
       P2/P3 -> aksiyon yok (sadece raporda kalir)

Calistirma:
    python3 mcp_client.py repo
"""
import asyncio, glob, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pipeline import run as run_pipeline

LANG_OF = {".c": "c", ".py": "python", ".js": "javascript", ".java": "java"}


def scan_repo(repo):
    """Repo'yu tarayip bulgulari toplar (Hafta 2-3 pipeline'i)."""
    findings = []
    for path in sorted(glob.glob(os.path.join(repo, "*"))):
        ext = os.path.splitext(path)[1]
        if ext in LANG_OF:
            for f in run_pipeline(path, LANG_OF[ext]):
                f.file = path.replace("\\", "/").split("/")[-1]
                findings.append(f)
    return findings


def _text(result):
    """call_tool sonucundan metni cikarir."""
    return result.content[0].text if result.content else ""


async def dispatch(findings):
    # Sunucuyu stdio uzerinden alt surec olarak baslat
    # sys.executable: istemciyi calistiran Python'un tam yolu (venv). Windows'ta
    # "python3" yok; sys.executable her platformda dogru yorumlayiciyi verir.
    params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()                     # el sikisma

            tools = await session.list_tools()             # arac kesfi
            print("Kesfedilen MCP araclari:",
                  [t.name for t in tools.tools], "\n")

            for f in findings:
                loc = f"{f.func}()" if f.func else "(dosya genel)"
                if f.severity == "P0":
                    r = await session.call_tool("create_pr_comment", {
                        "file": f.file, "line": f.line,
                        "severity": f.severity, "message": f.message})
                    print(" ", _text(r))
                if f.severity in ("P0", "P1"):
                    r = await session.call_tool("create_ticket", {
                        "title": f"[{f.severity}] {f.rule.split('  ')[0]} in {f.file}",
                        "severity": f.severity,
                        "description": f"{f.file}:{f.line} {loc} — {f.message}"})
                    print(" ", _text(r))


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else "repo"
    findings = scan_repo(repo)
    actionable = [f for f in findings if f.severity in ("P0", "P1")]
    print(f"{len(findings)} bulgu, {len(actionable)} tanesi aksiyon gerektiriyor (P0/P1)\n")
    asyncio.run(dispatch(findings))
    print("\nSonuclar mcp_output/ klasorune yazildi.")
