"""Cross-module taint tracking — source-to-sink data-flow analysis [B10, v7.4.2].

Builds on the SymbolIndex (B9c) to track how user-controlled data crosses module
boundaries and reaches security-sensitive sinks: SQL queries, shell commands,
eval, pickle deserialization, and file writes.

Intra-procedural pass: track_function() finds sinks reachable from sources
within a single function.

Cross-module pass: detect_taint_flows() uses the SymbolIndex to resolve
caller→callee chains and reports the full source→sink path.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from code_analyzer.analyzer.detectors import Finding

if TYPE_CHECKING:
    from code_analyzer.analyzer.project_index import SymbolIndex

_MAX_DEPTH = 3
_MAX_FINDINGS = 25
_CONFIDENCE_DIRECT = 0.8
_CONFIDENCE_CROSS = 0.6

SOURCES: dict[str, set[str]] = {
    "HTTP_INPUT": {
        "request.GET", "request.GET.get", "request.POST", "request.data", "request.FILES",
        "request.body", "request.META", "request.COOKIES",
        "request.args", "request.form", "request.json",
    },
    "USER_INPUT": {"input", "sys.argv", "sys.stdin"},
    "ENV": {"os.environ", "os.getenv", "environ.get"},
    "FILE_READ": {".read", ".read_text", "open", "pathlib.Path.read_text"},
    "NETWORK": {
        "requests.get", "requests.post", "requests.put", "requests.delete",
        "urllib.request.urlopen", "urlopen", "socket.recv", "socket.recvfrom",
    },
    "DESERIALIZE": {"json.loads", "json.load", "yaml.load", "yaml.safe_load"},
}

SINKS: dict[str, set[str]] = {
    "SQL_EXEC": {".raw", ".extra", ".execute", ".executemany"},
    "SHELL": {
        "os.system", "os.popen",
        "subprocess.run", "subprocess.Popen", "subprocess.call",
        "subprocess.check_call", "subprocess.check_output",
    },
    "CODE_EXEC": {"eval", "exec", "compile"},
    "PICKLE": {"pickle.load", "pickle.loads", "pickle.Unpickler"},
    "FILE_WRITE": {".write", ".writelines"},
}

_SINK_NAMES: dict[str, str] = {
    ".raw": "SQL executado sem parametrizacao",
    ".extra": "SQL executado sem parametrizacao",
    ".execute": "SQL executado sem parametrizacao",
    ".executemany": "SQL executado sem parametrizacao",
    "os.system": "comando de shell executado",
    "os.popen": "comando de shell executado",
    "subprocess.run": "comando de shell executado",
    "subprocess.Popen": "comando de shell executado",
    "subprocess.call": "comando de shell executado",
    "subprocess.check_call": "comando de shell executado",
    "subprocess.check_output": "comando de shell executado",
    "eval": "codigo avaliado dinamicamente",
    "exec": "codigo executado dinamicamente",
    "compile": "codigo compilado dinamicamente",
    "pickle.load": "dados de entrada desserializados com pickle",
    "pickle.loads": "dados de entrada desserializados com pickle",
    "pickle.Unpickler": "dados de entrada desserializados com pickle",
    ".write": "escrita de arquivo com dados potencialmente contaminados",
    ".writelines": "escrita de arquivo com dados potencialmente contaminados",
}

_SOURCE_NAMES: dict[str, str] = {
    "HTTP_INPUT": "entrada HTTP",
    "USER_INPUT": "entrada do usuario",
    "ENV": "variavel de ambiente",
    "FILE_READ": "leitura de arquivo",
    "NETWORK": "dados de rede",
    "DESERIALIZE": "desserializacao",
}


def _call_string(node: ast.Call) -> str:
    """Return a dotted string (e.g. 'request.GET' or 'os.system')."""
    func = node.func
    parts: list[str] = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    return ".".join(reversed(parts))


def _is_source_call(node: ast.Call) -> str | None:
    """Return source type label if *node* is a known taint source, else None."""
    name = _call_string(node)
    for stype, patterns in SOURCES.items():
        for pat in patterns:
            if name == pat or name.endswith("." + pat):
                return stype
    return None


def _is_sink_call(node: ast.Call) -> str | None:
    """Return sink label if *node* is a known taint sink, else None."""
    full = _call_string(node)
    for skey, patterns in SINKS.items():
        for pat in patterns:
            if full == pat or full.endswith(pat):
                return _SINK_NAMES.get(pat, skey)
    return None


def _collect_assignments(body: list[ast.stmt]) -> dict[str, ast.expr]:
    """Map local variable names to their defining expression."""
    assigns: dict[str, ast.expr] = {}
    for stmt in body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    assigns[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.value is not None:
                assigns[stmt.target.id] = stmt.value
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            assigns[stmt.target.id] = stmt.value
    return assigns


def _resolve_expr_vars(expr: ast.expr) -> set[str]:
    """Return set of variable names used in an expression."""
    return {
        node.id for node in ast.walk(expr)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _propagate_taint(
    assigns: dict[str, ast.expr],
    tainted_vars: set[str],
    taint_sources: dict[str, str],
) -> None:
    """Fixpoint: propagate taint through intermediate assignments.

    After direct sources are marked, walks the assignment chain to find
    variables that derive from tainted ones (e.g. ``cmd = data`` when
    ``data`` is already tainted). Also propagates source type.
    """
    changed = True
    while changed:
        changed = False
        for var, expr in assigns.items():
            if var in tainted_vars:
                continue
            deps = _resolve_expr_vars(expr) & tainted_vars
            if deps:
                tainted_vars.add(var)
                dep_source = next((taint_sources.get(d) for d in deps if taint_sources.get(d)), None)
                if dep_source and var not in taint_sources:
                    taint_sources[var] = dep_source
                changed = True


def track_function(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    filepath: str,
    lines: list[str],
) -> list[dict]:
    """Intra-procedural taint tracking.

    Returns list of finding dicts for sinks reachable from sources within this
    function. Each finding includes the source description, sink description,
    and intermediate variables involved.
    """
    params = {a.arg for a in func_node.args.args}
    param_list = [a.arg for a in func_node.args.args]

    assigns = _collect_assignments(func_node.body)
    tainted_vars: set[str] = set()
    taint_sources: dict[str, str] = {}
    findings: list[dict] = []

    for stmt in func_node.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue

            source_type = _is_source_call(node)
            if source_type is not None:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            tainted_vars.add(target.id)
                            if target.id not in taint_sources:
                                taint_sources[target.id] = source_type

    # Propagate taint through intermediate assignments
    _propagate_taint(assigns, tainted_vars, taint_sources)

    # Second pass: detect sinks
    for stmt in func_node.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue

            sink_label = _is_sink_call(node)
            if sink_label is None:
                continue

            all_args = list(node.args) + [kw.value for kw in node.keywords]
            for arg in all_args:
                arg_vars = _resolve_expr_vars(arg)
                if arg_vars & tainted_vars:
                    source_labels = sorted(set(
                        taint_sources.get(v, "desconhecida")
                        for v in (arg_vars & tainted_vars)
                    ))
                    findings.append({
                        "type": "direct",
                        "source": "; ".join(source_labels),
                        "sink": sink_label,
                        "line": node.lineno,
                        "variables": list(arg_vars & tainted_vars),
                        "confidence": _CONFIDENCE_DIRECT,
                    })

    # Detect entry points: parameter that reaches a sink
    for stmt in func_node.body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            sink_label = _is_sink_call(node)
            if sink_label is None:
                continue
            all_args = list(node.args) + [kw.value for kw in node.keywords]
            for arg in all_args:
                arg_vars = _resolve_expr_vars(arg)
                hit_params = arg_vars & params
                if hit_params:
                    findings.append({
                        "type": "entry_point",
                        "sink": sink_label,
                        "line": node.lineno,
                        "tainted_params": sorted(hit_params),
                        "param_index": [
                            param_list.index(p) for p in hit_params if p in param_list
                        ],
                        "confidence": _CONFIDENCE_DIRECT,
                    })

    return findings


def analyze_file_taint(
    tree: ast.AST,
    filepath: str,
    lines: list[str],
) -> list[dict]:
    """Single-file taint pass over *every* function, including class methods.

    Unlike detect_taint_flows (cross-module, top-level functions only via
    ast.iter_child_nodes), this walks the whole tree with ast.walk so methods
    defined inside classes are analysed too. Findings are *informational*:
    flagged with ``informational=True`` and never affect the score.

    Guards: returns [] for files over 20k lines; caps at _MAX_FINDINGS.
    Deduplicates by (line, sink, type) so functions nested inside other
    functions don't report the same sink twice.
    """
    if len(lines) > 20000:
        return []

    findings: list[dict] = []
    seen: set[tuple] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for fd in track_function(node, filepath, lines):
            key = (fd.get("line"), fd.get("sink"), fd.get("type"))
            if key in seen:
                continue
            seen.add(key)
            fd["function"] = node.name
            fd["criterion"] = "TaintFlow"
            fd["informational"] = True
            findings.append(fd)
            if len(findings) >= _MAX_FINDINGS:
                return findings

    return findings


def _find_callers(
    func_name: str,
    source_rel: str,
    trees: dict[Path, ast.AST],
    imports: dict[str, dict[str, str]],
    base: Path,
) -> list[tuple[Path, int, ast.Call]]:
    """Find all call sites of *func_name* across the project.

    Returns (filepath, lineno, call_node) for each call site.
    """
    call_sites: list[tuple[Path, int, ast.Call]] = []
    local_name: str | None = None

    for imps in imports.values():
        for alias, src in imps.items():
            if src == source_rel and alias == func_name:
                local_name = alias
                break
        if local_name is not None:
            break

    if local_name is None:
        for imps in imports.values():
            for alias, src in imps.items():
                if src == source_rel:
                    local_name = alias
                    break
            if local_name is not None:
                break

    if local_name is None:
        return call_sites

    for relpath, imps in imports.items():
        for alias, src in imps.items():
            if src != source_rel:
                continue
            if alias != func_name and local_name != alias:
                continue
            filepath = base / relpath
            tree = trees.get(filepath)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call_name = _call_string(node)
                if call_name == alias or call_name.endswith("." + alias):
                    call_sites.append((filepath, node.lineno, node))
    return call_sites


def detect_taint_flows(
    trees: dict[Path, ast.AST],
    symbol_index: SymbolIndex | None,
    base: Path,
    depth: int = 0,
) -> list[tuple[Path, dict]]:
    """Cross-module taint detection.

    1. Per-file intra-procedural pass: find sinks reachable from sources.
    2. Parameter entry-point pass: find functions whose params reach a sink.
    3. Cross-module pass: for each entry point, find callers and check if
       their arguments are tainted.

    Returns ``(abs_path, finding_dict)`` pairs.
    """
    if depth > _MAX_DEPTH:
        return []

    out: list[tuple[Path, dict]] = []
    entry_points: dict[str, list[dict]] = defaultdict(list)

    for filepath, tree in trees.items():
        rel = str(filepath.relative_to(base)) if filepath != base else filepath.name
        try:
            src_lines = filepath.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            src_lines = []

        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            findings = track_function(node, rel, src_lines)
            for fd in findings:
                if fd["type"] == "direct":
                    fd["file"] = rel
                    finding_obj = Finding(
                        criterion="TaintFlow",
                        location=f"linha {fd['line']}",
                        line=fd["line"],
                        severity="ALTA",
                        issue=(
                            f"Fluxo contaminado detectado: dados de entrada "
                            f"(tipo: {fd.get('source','desconhecida')}) alcancam "
                            f"{fd['sink']} na funcao {node.name}."
                        ),
                        suggestion=(
                            "Valide e sanitize a entrada antes de passa-la "
                            "para operacoes sensiveis."
                        ),
                        line_content=(
                            src_lines[fd["line"] - 1]
                            if fd["line"] <= len(src_lines)
                            else ""
                        ),
                        confidence=_CONFIDENCE_DIRECT,
                    )
                    fd_out = finding_obj.to_dict(str(filepath))
                    fd_out["file"] = rel
                    out.append((filepath, fd_out))
                elif fd["type"] == "entry_point":
                    fd["_relpath"] = rel
                    entry_points[node.name].append(fd)
                    finding_obj = Finding(
                        criterion="TaintFlow",
                        location=f"linha {fd['line']}",
                        line=fd["line"],
                        severity="ALTA",
                        issue=(
                            f"Funcao {node.name} recebe parametro que alcanca "
                            f"{fd['sink']} — chama-la com dados contaminados "
                            f"expoe a aplicacao."
                        ),
                        suggestion=(
                            "Valide/sanitize o parametro de entrada antes de "
                            "usa-lo em operacoes sensiveis."
                        ),
                        line_content=(
                            src_lines[fd["line"] - 1]
                            if fd["line"] <= len(src_lines)
                            else ""
                        ),
                        confidence=fd.get("confidence", _CONFIDENCE_DIRECT),
                    )
                    fd_out = finding_obj.to_dict(str(filepath))
                    fd_out["file"] = rel
                    out.append((filepath, fd_out))

    if symbol_index and depth < _MAX_DEPTH:
        for func_name, entry_list in entry_points.items():
            source_rel = entry_list[0].get("_relpath", "") if entry_list else ""
            for entry in entry_list:
                if not isinstance(entry, dict) or entry.get("type") != "entry_point":
                    continue
                source_rel = entry.get("_relpath", source_rel)
                callers = _find_callers(
                    func_name, source_rel, trees,
                    symbol_index.imports, base,
                )
                for caller_path, caller_line, call_node in callers:
                    param_indices: list[int] = entry.get("param_index", [])
                    for pi in param_indices:
                        if pi >= len(call_node.args):
                            continue
                        arg_vars = _resolve_expr_vars(call_node.args[pi])
                        if not arg_vars:
                            continue
                        try:
                            caller_rel = str(caller_path.relative_to(base))
                        except ValueError:
                            caller_rel = caller_path.name
                        try:
                            caller_lines = caller_path.read_text(
                                encoding="utf-8"
                            ).splitlines()
                        except (OSError, UnicodeDecodeError):
                            caller_lines = []
                        finding_obj = Finding(
                            criterion="TaintFlow",
                            location=f"linha {caller_line} (chamando {func_name})",
                            line=caller_line,
                            severity="ALTA",
                            issue=(
                                f"Fluxo contaminado cross-module: dados do "
                                f"chamador em {caller_rel}:{caller_line} "
                                f"alcancam {entry['sink']} via {func_name}."
                            ),
                            suggestion=(
                                "Valide a entrada antes de chamar esta funcao "
                                "ou adicione sanitizacao dentro dela."
                            ),
                            line_content=(
                                caller_lines[caller_line - 1]
                                if caller_line <= len(caller_lines)
                                else ""
                            ),
                            confidence=_CONFIDENCE_CROSS,
                        )
                        fd_out = finding_obj.to_dict(str(caller_path))
                        fd_out["file"] = caller_rel
                        fd_out["taint_path"] = [
                            f"{caller_rel}:{caller_line} (chamada)",
                            f"{source_rel}:{entry['line']} (sumidouro)",
                        ]
                        out.append((caller_path, fd_out))
                        if len(out) >= _MAX_FINDINGS:
                            return out

    return out
