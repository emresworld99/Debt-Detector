"""
Hafta 1 — Ingestion Layer
Bir kaynak dosyayi tree-sitter ile parse eder, fonksiyon bazli chunk'lara boler,
her chunk icin metadata + cyclomatic complexity uretir.
"""
import os
from dataclasses import dataclass, asdict
from tree_sitter import Language, Parser, Node
import tree_sitter_c, tree_sitter_python, tree_sitter_javascript, tree_sitter_java


# --- Dil konfigurasyonu -----------------------------------------------------
# Her dil icin: grammar, "fonksiyon" sayilan node tipleri, "class" node tipleri,
# ve cyclomatic complexity'de +1 sayilan karar-noktasi node tipleri.

@dataclass(frozen=True)
class LangSpec:
    language: Language
    func_nodes: set          # fonksiyon/metot tanimi node tipleri
    class_nodes: set         # class/struct node tipleri (method ayrimi icin)
    decision_nodes: set      # complexity'de +1 sayilan node tipleri
    bool_op_node: str        # &&/|| operatorlerini tasiyan node tipi
    name_field: str          # fonksiyon ismini tutan field adi ("" ise ozel cikar)

SPECS = {
    "c": LangSpec(
        Language(tree_sitter_c.language()),
        func_nodes={"function_definition"},
        class_nodes=set(),
        decision_nodes={"if_statement", "for_statement", "while_statement",
                        "do_statement", "case_statement", "conditional_expression"},
        bool_op_node="binary_expression",
        name_field="",  # C'de isim declarator agacinda gomulu, ozel cikariyoruz
    ),
    "python": LangSpec(
        Language(tree_sitter_python.language()),
        func_nodes={"function_definition"},
        class_nodes={"class_definition"},
        decision_nodes={"if_statement", "elif_clause", "for_statement",
                        "while_statement", "except_clause", "conditional_expression"},
        bool_op_node="boolean_operator",
        name_field="name",
    ),
    "javascript": LangSpec(
        Language(tree_sitter_javascript.language()),
        func_nodes={"function_declaration", "method_definition",
                    "function_expression", "arrow_function"},
        class_nodes={"class_declaration"},
        decision_nodes={"if_statement", "for_statement", "for_in_statement",
                        "while_statement", "do_statement", "switch_case",
                        "catch_clause", "ternary_expression"},
        bool_op_node="binary_expression",
        name_field="name",
    ),
    "java": LangSpec(
        Language(tree_sitter_java.language()),
        func_nodes={"method_declaration", "constructor_declaration"},
        class_nodes={"class_declaration"},
        decision_nodes={"if_statement", "for_statement", "enhanced_for_statement",
                        "while_statement", "do_statement", "switch_label",
                        "catch_clause", "ternary_expression"},
        bool_op_node="binary_expression",
        name_field="name",
    ),
}


@dataclass
class Chunk:
    file: str
    func: str
    is_method: bool
    class_name: str | None
    line_start: int
    line_end: int
    complexity: int
    lang: str
    code: str


# --- Yardimcilar ------------------------------------------------------------

def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf8", errors="replace")


def _func_name(node: Node, spec: LangSpec, src: bytes) -> str:
    """Fonksiyon ismini cikarir. Cogu dilde 'name' field'i var; C'de degil."""
    if spec.name_field:
        n = node.child_by_field_name(spec.name_field)
        if n is not None:
            return _text(n, src)
    # C fallback: declarator -> function_declarator -> declarator (identifier)
    decl = node.child_by_field_name("declarator")
    while decl is not None:
        if decl.type == "identifier":
            return _text(decl, src)
        decl = decl.child_by_field_name("declarator")
    return "<anonymous>"


def _enclosing_class(node: Node, spec: LangSpec, src: bytes):
    """Bu fonksiyon bir class icinde mi? Atalar boyunca yukari yuru."""
    p = node.parent
    while p is not None:
        if p.type in spec.class_nodes:
            name = p.child_by_field_name("name")
            return _text(name, src) if name else "<anon-class>"
        p = p.parent
    return None


def _count_complexity(func: Node, spec: LangSpec, src: bytes) -> int:
    """
    Cyclomatic complexity = karar noktasi sayisi + 1.
    Ic ice tanimli fonksiyonlara INMEZ (onlarin complexity'si kendilerine ait).
    """
    count = 0
    # func'un govdesini gez ama nested function node'larina girme
    stack = list(func.children)
    while stack:
        n = stack.pop()
        if n.type in spec.func_nodes:
            continue  # nested fonksiyon -> atla
        if n.type in spec.decision_nodes:
            count += 1
        elif n.type == spec.bool_op_node:
            # sadece && / || kisa-devre operatorleri sayilir (bitwise & | degil)
            op = n.child_by_field_name("operator")
            if op is not None and _text(op, src) in ("&&", "||", "and", "or"):
                count += 1
        stack.extend(n.children)
    return count + 1


def _walk_functions(root: Node, spec: LangSpec):
    """AST'teki tum fonksiyon node'larini verir (nested dahil)."""
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in spec.func_nodes:
            yield n
        stack.extend(n.children)


# --- Ana API ----------------------------------------------------------------

def ingest(path: str, lang: str) -> list[Chunk]:
    spec = SPECS[lang]
    with open(path, "rb") as f:
        src = f.read()
    tree = Parser(spec.language).parse(src)

    chunks = []
    for fn in _walk_functions(tree.root_node, spec):
        cls = _enclosing_class(fn, spec, src)
        chunks.append(Chunk(
            file=path.replace("\\", "/").split("/")[-1],   # platform-bagimsiz basename
            func=_func_name(fn, spec, src),
            is_method=cls is not None,
            class_name=cls,
            line_start=fn.start_point[0] + 1,   # tree-sitter 0-index, +1 ile insan-okunur
            line_end=fn.end_point[0] + 1,
            complexity=_count_complexity(fn, spec, src),
            lang=lang,
            code=_text(fn, src),
        ))
    return chunks


if __name__ == "__main__":
    import sys, json
    path, lang = sys.argv[1], sys.argv[2]
    for c in ingest(path, lang):
        d = asdict(c)
        d["code"] = d["code"][:40].replace("\n", " ") + " ..."  # ozet
        print(json.dumps(d, ensure_ascii=False))
