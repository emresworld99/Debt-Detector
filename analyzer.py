"""
Hafta 2 — Static Analyzer (kural tabanli, kendi dedektorlerimiz)
Hafta 1'in tree-sitter agacinin uzerine biner. Bir dosyayi tarayip
P0-P3 etiketli bulgu listesi uretir. C dahil her dilde, kurulumsuz calisir.
"""
import re
from dataclasses import dataclass, asdict, field
from tree_sitter import Parser
from ingest import ingest, SPECS, _text, _func_name   # Hafta 1'i yeniden kullaniyoruz


@dataclass
class Finding:
    severity: str          # "P0".."P3"
    rule: str              # kural kimligi
    line: int
    func: str | None
    message: str
    # --- Hafta 3'te eklendi: checkpointer serialize edebilsin diye TANIMLI alanlar ---
    file: str | None = None                 # tum repo taramasinda hangi dosya
    recurrences: list = field(default_factory=list)  # cross-file tekrarlar
    suggestion: str | None = None           # LLM refactor onerisi

SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

# Esikler (PDF'teki degerler)
COMPLEXITY_THRESHOLD = 10      # P2: cyclomatic complexity > 10
LONG_FUNC_LINES = 80           # P1: god function (orn. 80+ satir; PDF 500 der)


# --- AST gezme yardimcilari -------------------------------------------------

def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.children)

def _enclosing_func(node, spec, src):
    """Bir node hangi fonksiyonun icinde? Atalarda fonksiyon node'u ara."""
    p = node.parent
    while p is not None:
        if p.type in spec.func_nodes:
            return _func_name(p, spec, src)
        p = p.parent
    return None


# --- AST tabanli dedektorler (her biri Finding uretir) ----------------------

SECRET_RE = re.compile(
    r'sk-[A-Za-z0-9\-]{8,}|AKIA[0-9A-Z]{12,}|AIza[0-9A-Za-z\-_]{20,}|ghp_[A-Za-z0-9]{20,}'
)
SQL_KEYWORDS = re.compile(r'\b(SELECT|INSERT|UPDATE|DELETE)\b', re.I)
FORMAT_FUNCS = {"sprintf", "snprintf", "vsprintf", "strcpy", "strcat", "format"}
STRING_BUILD_FMT = re.compile(r'%s|%d|\{\}|\bf"')   # format yer tutucusu


def detect_hardcoded_secret(tree, src, spec):
    """P0: kaynak icine gomulu API key / token."""
    for n in _walk(tree.root_node):
        if n.type in ("string_literal", "string"):
            val = _text(n, src)
            if SECRET_RE.search(val):
                yield Finding("P0", "hardcoded_secret", n.start_point[0] + 1,
                              _enclosing_func(n, spec, src),
                              "Kaynak koda gomulu gizli anahtar/token tespit edildi.")

def detect_sql_injection(tree, src, spec):
    """P0: kullanici girdisini string birlestirme ile SQL'e gomme."""
    for n in _walk(tree.root_node):
        if n.type in ("call_expression", "call"):
            fn = n.child_by_field_name("function")
            fname = _text(fn, src) if fn else ""
            if fname in FORMAT_FUNCS:
                body = _text(n, src)
                if SQL_KEYWORDS.search(body) and STRING_BUILD_FMT.search(body):
                    yield Finding("P0", "sql_injection", n.start_point[0] + 1,
                                  _enclosing_func(n, spec, src),
                                  f"'{fname}' ile SQL sorgusu string birlestirilerek kuruluyor "
                                  "(prepared statement kullanin).")

def detect_infinite_loop(tree, src, spec):
    """P0: cikisi olmayan sonsuz dongu (while(1)/while(true) icinde break/return yok)."""
    EXITS = {"break_statement", "return_statement", "goto_statement"}
    for n in _walk(tree.root_node):
        if n.type == "while_statement":
            cond = n.child_by_field_name("condition")
            cond_txt = _text(cond, src).strip("() ") if cond else ""
            if cond_txt in ("1", "true"):
                has_exit = any(d.type in EXITS for d in _walk(n))
                if not has_exit:
                    yield Finding("P0", "infinite_loop", n.start_point[0] + 1,
                                  _enclosing_func(n, spec, src),
                                  "Cikis kosulu olmayan sonsuz dongu (break/return yok).")

def detect_todo(tree, src, spec):
    """P3: yorumda kalan TODO/FIXME."""
    for n in _walk(tree.root_node):
        if n.type == "comment" and re.search(r'\b(TODO|FIXME)\b', _text(n, src)):
            yield Finding("P3", "todo_comment", n.start_point[0] + 1,
                          _enclosing_func(n, spec, src),
                          "Cozulmemis TODO/FIXME notu.")

AST_DETECTORS = [detect_hardcoded_secret, detect_sql_injection,
                 detect_infinite_loop, detect_todo]


# --- Chunk (metadata) tabanli dedektorler -----------------------------------

def detect_chunk_level(chunks):
    """Hafta 1'in complexity/satir bilgisini kullanan dedektorler."""
    for c in chunks:
        if c.complexity > COMPLEXITY_THRESHOLD:
            yield Finding("P2", "high_complexity", c.line_start, c.func,
                          f"Yuksek cyclomatic complexity ({c.complexity} > {COMPLEXITY_THRESHOLD}).")
        if (c.line_end - c.line_start + 1) > LONG_FUNC_LINES:
            yield Finding("P1", "god_function", c.line_start, c.func,
                          f"Cok uzun fonksiyon ({c.line_end - c.line_start + 1} satir).")


# --- Ana API ----------------------------------------------------------------

def analyze(path, lang):
    spec = SPECS[lang]
    src = open(path, "rb").read()
    tree = Parser(spec.language).parse(src)

    findings = []
    for det in AST_DETECTORS:
        findings += list(det(tree, src, spec))
    findings += list(detect_chunk_level(ingest(path, lang)))

    # once siddet (P0->P3), sonra satir numarasina gore sirala
    findings.sort(key=lambda f: (SEVERITY_RANK[f.severity], f.line))
    return findings


if __name__ == "__main__":
    import sys
    path, lang = sys.argv[1], sys.argv[2]
    findings = analyze(path, lang)
    print(f"{path} icin {len(findings)} bulgu:\n")
    for f in findings:
        loc = f"{f.func}()" if f.func else "(dosya genel)"
        print(f"  [{f.severity}] {f.rule:18} satir {f.line:>3}  {loc}")
        print(f"        {f.message}")
