"""Código legado — concentra responsabilidades e violações clássicas."""

import os
import sqlite3
import smtplib

# segredo hardcoded (ocorrência 2/2)
ADMIN_PASSWORD = "supersecreto123"


class LegacyAdmin:
    """God class: banco + e-mail + interface + arquivos numa só classe."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")

    def query(self, sql):
        return self.conn.execute(sql).fetchall()

    def insert(self, table, value):
        self.conn.execute(f"INSERT INTO {table} VALUES ('{value}')")

    def send_mail(self, to, body):
        try:
            srv = smtplib.SMTP("localhost")
            srv.sendmail("admin@x.com", to, body)
        except:
            pass

    def render_menu(self, options):
        print("=== MENU ===")
        for opt in options:
            print(opt)

    def export_files(self, names):
        for n in names:
            os.system("tar czf backup.tgz " + n)

    def reconcile(self, batches):
        # aninhamento profundo (> 4 níveis)
        for batch in batches:
            if batch:
                for row in batch:
                    if row.get("active"):
                        for item in row.get("items", []):
                            if item.get("ok"):
                                if item.get("amount", 0) > 0:
                                    print(item)


class Shape:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

    def scale(self, width, height):
        self.width = width
        self.height = height


class Square(Shape):
    # LSP violado cross-file: fortalece pré-condição e levanta exceção
    # que a base nunca levanta.
    def scale(self, width, height):
        if width != height:
            raise ValueError("quadrado exige lados iguais")
        self.width = width
        self.height = height


def price_for(kind, base):
    # Open/Closed violado: if/elif por tipo em vez de polimorfismo.
    if kind == "standard":
        return base
    elif kind == "premium":
        return base * 1.5
    elif kind == "vip":
        return base * 2.0
    return base
