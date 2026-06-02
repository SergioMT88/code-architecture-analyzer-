"""Testes do checkout.

Dois casos com 'dor de teste' proposital + um teste limpo (isca):
o detector NÃO deve penalizar test_tax_bracket_lookup.
"""

import unittest
from unittest.mock import patch, MagicMock

from shopapp.services import CheckoutFacade, OrderService
from shopapp.repository import SqlOrderRepository, TaxBracketSet
from shopapp.djangoish import Request


class TestCheckout(unittest.TestCase):

    @patch("shopapp.services.run_command")
    @patch("shopapp.services.pick_channel")
    @patch("shopapp.services.EventBus")
    def test_checkout_flow(self, mock_bus, mock_channel, mock_cmd):
        # 6 mocks no total (3 @patch + 2 MagicMock + 1 patch.object)
        fake_repo = MagicMock()
        fake_request = MagicMock()
        fake_request.data = {"status": "PENDENTE"}
        facade = CheckoutFacade()
        with patch.object(facade._service, "repo", fake_repo):
            facade._service = OrderService()
            facade.checkout(Request({"status": "PENDENTE"}))
        self.assertIsNotNone(facade)

    def test_persists_to_real_db(self):
        # NÃO isola: cria e usa um banco SQLite de verdade.
        repo = SqlOrderRepository()
        repo.conn.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, status TEXT)")
        repo.conn.execute("INSERT INTO orders (status) VALUES ('PENDENTE')")
        repo.conn.commit()
        linhas = repo.all()
        self.assertEqual(len(linhas), 1)

    def test_tax_bracket_lookup(self):
        # ISCA: teste limpo, rápido, isolado, sem mock e sem I/O.
        # Não deve gerar nenhum alerta de 'test pain'.
        brackets = TaxBracketSet()
        self.assertEqual(brackets.get(0), 0.0)
        self.assertEqual(brackets.get(2000), 0.1)
        self.assertEqual(brackets.get(9000), 0.2)


if __name__ == "__main__":
    unittest.main()
