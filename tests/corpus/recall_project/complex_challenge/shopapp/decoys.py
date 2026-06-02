"""ISCAS DE FALSO POSITIVO.

Tudo aqui é código CORRETO. Uma ferramenta bem calibrada NÃO deve
levantar achado nenhum neste arquivo (salvo, no máximo, tamanho de
função em `parse_record`, que é legítimo e coeso).
"""

import os

# segredo carregado do ambiente — NÃO é hardcoded, não deve ser flagado
API_KEY = os.environ.get("API_KEY", "")

# constante nomeada — NÃO é "magic number"
HTTP_OK = 200


def safe_append(value, items=None):
    # default mutável EVITADO corretamente — não deve ser flagado
    if items is None:
        items = []
    items.append(value)
    return items


def classify(value):
    # uso CORRETO de isinstance — não confundir com `type(x) == str`
    if isinstance(value, str):
        return "texto"
    if isinstance(value, (int, float)):
        return "numero"
    return "outro"


def normalize(items):
    # list comprehension ÚTIL (transforma) — não é a inútil `[x for x in xs]`
    return [str(x).strip().upper() for x in items]


def status_ok(code):
    # comparação contra constante nomeada — não é magic number
    return code == HTTP_OK


def parse_line(line):
    # except específico que loga e RE-LEVANTA — aceitável, não é bare except
    try:
        return int(line)
    except ValueError as exc:
        print("linha inválida:", exc)
        raise


class Circle:
    # subclasse que respeita o contrato da base (Shape) — LSP OK
    def __init__(self, radius):
        self.radius = radius

    def area(self):
        return 3.14159 * self.radius * self.radius

    def scale(self, factor, _ignored=None):
        self.radius *= factor


def parse_record(raw):
    # função longa porém COESA: um único parser sequencial de um registro.
    # Pode disparar regra de tamanho (legítimo), mas NÃO SRP/God class.
    record = {}
    record["id"] = raw.get("id")
    record["name"] = (raw.get("name") or "").strip()
    record["email"] = (raw.get("email") or "").strip().lower()
    record["phone"] = (raw.get("phone") or "").replace(" ", "")
    record["street"] = (raw.get("street") or "").strip()
    record["number"] = (raw.get("number") or "").strip()
    record["city"] = (raw.get("city") or "").strip()
    record["state"] = (raw.get("state") or "").strip().upper()
    record["zip"] = (raw.get("zip") or "").replace("-", "")
    record["country"] = (raw.get("country") or "BR").upper()
    record["created"] = raw.get("created")
    record["updated"] = raw.get("updated")
    record["active"] = bool(raw.get("active", True))
    record["score"] = float(raw.get("score") or 0.0)
    record["tags"] = [t.strip() for t in (raw.get("tags") or [])]
    record["notes"] = (raw.get("notes") or "").strip()
    record["currency"] = (raw.get("currency") or "BRL").upper()
    record["discount"] = float(raw.get("discount") or 0.0)
    record["balance"] = float(raw.get("balance") or 0.0)
    record["verified"] = bool(raw.get("verified", False))
    return record
