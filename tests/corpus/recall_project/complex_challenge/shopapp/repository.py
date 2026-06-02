"""Camada de acesso a dados."""

import sqlite3

from .security_utils import build_filter

# literal de status duplicado (shotgun surgery, ocorrência 2/3)
STATUS_DEFAULT = "PENDENTE"  # EXPECT: ShotgunSurgery


class SqlOrderRepository:
    """Repositório real: persiste pedidos em SQLite."""

    def __init__(self, conn=None):
        self.conn = conn or sqlite3.connect(":memory:")

    def all(self):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM orders")
        return cur.fetchall()

    def get(self, order_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return cur.fetchone()

    def search(self, user_value):
        # taint inter-procedural: user_value -> build_filter() -> query.
        # Detector de nó único vê só uma f-string com variável local.
        where = build_filter(user_value)
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM orders WHERE {where}")
        return cur.fetchall()

    def save(self, order):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO orders (status) VALUES (?)",
            (getattr(order, "status", STATUS_DEFAULT),),
        )
        self.conn.commit()


class TaxBracketSet:
    """ISCA DE FALSO POSITIVO: tem get/filter/all como um repositório,
    mas opera só em memória e não persiste nada. NÃO é Repository."""

    def __init__(self):
        self._brackets = [(0, 0.0), (1000, 0.1), (5000, 0.2)]

    def all(self):
        return list(self._brackets)

    def filter(self, minimo):
        return [b for b in self._brackets if b[0] >= minimo]

    def get(self, valor):
        escolhido = 0.0
        for limite, taxa in self._brackets:
            if valor >= limite:
                escolhido = taxa
        return escolhido
