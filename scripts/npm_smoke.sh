#!/usr/bin/env bash
# Smoke test do wrapper npm (bin/cli.js) — valida o contrato wrapper <-> motor Python.
# Roda local (Git Bash/WSL) e no CI (job npm-sanity).
set -euo pipefail

cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FALHOU: $1" >&2; exit 1; }
parse_json() { python -c "import sys, json; json.load(sys.stdin)" || fail "$1 nao retornou JSON valido"; }

# f-string sem placeholder: canario do refactorer — se --no-refactor vazar, o arquivo muda.
cat > "$TMP/sample.py" <<'EOF'
def greet(name):
    msg = f"hello"
    return msg + name


def add(a, b):
    return a + b
EOF

cat > "$TMP/other.py" <<'EOF'
def add2(a, b):
    return a + b
EOF

echo "[1/7] check --json e JSON parseavel"
node bin/cli.js check "$TMP/sample.py" --json --no-html | parse_json "check --json"

echo "[2/7] analyze --no-refactor NAO modifica o arquivo"
cp "$TMP/sample.py" "$TMP/sample.orig.py"
node bin/cli.js analyze "$TMP/sample.py" --no-refactor --no-html --quiet > /dev/null
diff "$TMP/sample.py" "$TMP/sample.orig.py" || fail "--no-refactor vazou: arquivo foi modificado pela analise"

echo "[3/7] history --json e JSON parseavel"
node bin/cli.js history "$TMP/sample.py" --json | parse_json "history --json"

echo "[4/7] dup --json e JSON parseavel"
node bin/cli.js dup "$TMP/sample.py" "$TMP/other.py" --json | parse_json "dup --json"

echo "[5/7] project --threshold --json (scan de duplicacao) e JSON parseavel"
node bin/cli.js project "$TMP" --threshold 0.9 --json | parse_json "project --threshold --json"

echo "[6/7] project --json (pipeline cross-file completo) e JSON parseavel"
node bin/cli.js project "$TMP" --json | parse_json "project --json"

# --agent e o modo PRIMARIO para agentes: o stdout tem que ser o envelope JSON
# puro (sem header/spinner/footer do wrapper). Regressao se algo poluir o stdout.
echo "[7/7] check --agent emite envelope JSON puro (schema_version presente)"
node bin/cli.js check "$TMP/sample.py" --agent --no-html \
  | python -c "import sys, json; e=json.load(sys.stdin); assert e['schema_version'], 'sem schema_version'" \
  || fail "check --agent nao emitiu envelope JSON puro"

# DX: --help dos subcomandos tem que orientar a acao (exemplos + caminho do agente),
# nao so listar flags. Um agente/usuario roda --help e sabe o que fazer.
echo "[+] check --help orienta a acao (COMECE ASSIM + AGENTE)"
help_out="$(node bin/cli.js check --help 2>&1)"
echo "$help_out" | grep -q "COMECE ASSIM" || fail "check --help sem bloco 'COMECE ASSIM'"
echo "$help_out" | grep -q -- "--agent" || fail "check --help nao menciona o caminho do agente"

# Erros nunca sao becos sem saida: carregam um proximo passo (hint).
# (|| true: o comando sai 1 de proposito — e um erro; queremos o stdout JSON.)
echo "[+] erro sem arquivo carrega hint (--json)"
err_json="$(node bin/cli.js check --json 2>/dev/null || true)"
echo "$err_json" \
  | python -c "import sys, json; e=json.load(sys.stdin); assert not e['success'] and e.get('hint'), 'erro sem hint'" \
  || fail "check --json sem arquivo nao trouxe hint"

echo "OK: smoke test do wrapper npm passou."
