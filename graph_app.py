"""
Hafta 3 — LangGraph Orkestrasyon (tam surum)
Node'lar:
  supervisor       : sirada ne var karar verir (kosullu edge)
  static_analyzer  : Hafta 2 pipeline'ini tum repoya uygular
  semantic_searcher: her P0 fonksiyonu icin "bu pattern baska nerede?" (cross-file)
  refactor_advisor : her P0 icin LLM'den duzeltme onerisi (anahtar yoksa atlar)
  human_approval   : kritik (P0) bulgular varsa interrupt ile insan onayi bekler
  report_generator : onceliklendirilmis nihai rapor
"""
import glob, os
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

from pipeline import run as run_pipeline
from analyzer import SEVERITY_RANK
from ingest import ingest
from embed_store import build_store, most_similar
from explain import explain

LANG_OF = {".c": "c", ".py": "python", ".js": "javascript", ".java": "java"}
SIM_THRESHOLD = 0.5


class State(TypedDict):
    repo: str
    findings: list
    report: str
    approved: bool
    analyzed: bool
    searched: bool
    advised: bool
    asked: bool
    reported: bool


def _all_chunks(repo):
    chunks = []
    for path in sorted(glob.glob(os.path.join(repo, "*"))):
        ext = os.path.splitext(path)[1]
        if ext in LANG_OF:
            chunks += ingest(path, LANG_OF[ext])
    return chunks


def supervisor(state: State) -> dict:
    return {}


def static_analyzer(state: State) -> dict:
    findings = []
    for path in sorted(glob.glob(os.path.join(state["repo"], "*"))):
        ext = os.path.splitext(path)[1]
        if ext in LANG_OF:
            for f in run_pipeline(path, LANG_OF[ext]):
                f.file = path.replace("\\", "/").split("/")[-1]   # platform-bagimsiz
                findings.append(f)
    print(f"[static_analyzer] {len(findings)} bulgu")
    return {"findings": findings, "analyzed": True}


def semantic_searcher(state: State) -> dict:
    chunks = _all_chunks(state["repo"])
    by_key = {(c.file, c.func): c for c in chunks}
    client = build_store(chunks)
    for f in state["findings"]:
        f.recurrences = []
        if f.severity != "P0" or f.func is None:
            continue
        chunk = by_key.get((f.file, f.func))
        if not chunk:
            continue
        for hit in most_similar(client, chunk.code, k=5):
            p = hit.payload
            if not (p["file"] == f.file and p["func"] == f.func) and hit.score >= SIM_THRESHOLD:
                f.recurrences.append((p["file"], p["func"], round(hit.score, 2)))
    total = sum(len(getattr(f, "recurrences", [])) for f in state["findings"])
    print(f"[semantic_searcher] {total} cross-file tekrar bulundu")
    return {"findings": state["findings"], "searched": True}


def refactor_advisor(state: State) -> dict:
    chunks = {(c.file, c.func): c for c in _all_chunks(state["repo"])}
    n = 0
    for f in state["findings"]:
        f.suggestion = None
        if f.severity != "P0":
            continue
        snippet = chunks.get((f.file, f.func))
        code = snippet.code if snippet else f.message
        f.suggestion = explain(f, code)
        if f.suggestion:
            n += 1
    print(f"[refactor_advisor] {n} oneri uretildi (0 ise API anahtari yok)")
    return {"findings": state["findings"], "advised": True}


def human_approval(state: State) -> dict:
    p0 = [f for f in state["findings"] if f.severity == "P0"]
    if not p0:
        return {"approved": True, "asked": True}
    decision = interrupt({
        "soru": f"{len(p0)} adet P0 bulgu var. Rapor/aksiyon uretilsin mi?",
        "ornekler": [f"{f.file}:{f.line} {f.rule}" for f in p0[:3]],
    })
    print(f"[human_approval] insan karari: {decision}")
    return {"approved": (decision == "approve"), "asked": True}


def report_generator(state: State) -> dict:
    if not state.get("approved"):
        report = "Onay verilmedi; rapor uretilmedi."
    else:
        fs = sorted(state["findings"], key=lambda f: (SEVERITY_RANK[f.severity], f.file, f.line))
        lines = [f"REPO RAPORU  —  {len(fs)} bulgu\n"]
        for f in fs:
            loc = f"{f.func}()" if f.func else "(dosya genel)"
            lines.append(f"[{f.severity}] {f.file}:{f.line}  {loc}  — {f.rule}")
            for (rf, rfunc, sc) in getattr(f, "recurrences", []):
                lines.append(f"        -> ayni pattern: {rf}:{rfunc}() (benzerlik {sc})")
            if getattr(f, "suggestion", None):
                lines.append(f"        -> oneri: {f.suggestion}")
        report = "\n".join(lines)
    print("[report_generator] rapor uretildi")
    return {"report": report, "reported": True}


def route(state: State) -> str:
    if not state.get("analyzed"):  return "static_analyzer"
    if not state.get("searched"):  return "semantic_searcher"
    if not state.get("advised"):   return "refactor_advisor"
    if not state.get("asked"):     return "human_approval"
    if not state.get("reported"):  return "report_generator"
    return END


def build_graph():
    g = StateGraph(State)
    for name, fn in [("supervisor", supervisor), ("static_analyzer", static_analyzer),
                     ("semantic_searcher", semantic_searcher), ("refactor_advisor", refactor_advisor),
                     ("human_approval", human_approval), ("report_generator", report_generator)]:
        g.add_node(name, fn)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route, {
        "static_analyzer": "static_analyzer", "semantic_searcher": "semantic_searcher",
        "refactor_advisor": "refactor_advisor", "human_approval": "human_approval",
        "report_generator": "report_generator", END: END,
    })
    for n in ["static_analyzer", "semantic_searcher", "refactor_advisor",
              "human_approval", "report_generator"]:
        g.add_edge(n, "supervisor")
    return g.compile(checkpointer=InMemorySaver())


if __name__ == "__main__":
    import sys
    repo = sys.argv[1] if len(sys.argv) > 1 else "repo"
    app = build_graph()
    config = {"configurable": {"thread_id": "demo-1"}}

    print("=== 1) CALISTIR (interrupt'a kadar) ===")
    result = app.invoke({"repo": repo, "findings": [], "report": "",
                         "approved": False, "analyzed": False, "searched": False,
                         "advised": False, "asked": False, "reported": False}, config)

    if "__interrupt__" in result:
        intr = result["__interrupt__"][0]
        print("\n=== 2) AKIS DURDU — INSAN ONAYI BEKLENIYOR ===")
        print("Soru:", intr.value["soru"])
        for e in intr.value["ornekler"]:
            print("  -", e)
        print("\n=== 3) INSAN 'approve' DIYOR — DEVAM ===")
        final = app.invoke(Command(resume="approve"), config)
        print("\n=== NIHAI RAPOR ===")
        print(final["report"])
    else:
        print(result.get("report", "(interrupt olmadi)"))
