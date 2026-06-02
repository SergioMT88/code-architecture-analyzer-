"""Modelos de domínio da loja."""

from .djangoish import Model


class Customer(Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = kwargs.get("name", "")
        self.email = kwargs.get("email", "")
        self.street = kwargs.get("street", "")
        self.number = kwargs.get("number", "")
        self.city = kwargs.get("city", "")
        self.state = kwargs.get("state", "")
        self.zip = kwargs.get("zip", "")


class Order(Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = kwargs.get("customer_id")
        self.customer_name = kwargs.get("customer_name", "")
        self.street = kwargs.get("street", "")
        self.number = kwargs.get("number", "")
        self.city = kwargs.get("city", "")
        self.state = kwargs.get("state", "")
        self.zip = kwargs.get("zip", "")
        self.total = kwargs.get("total", 0)
        # literal de status escrito direto (shotgun surgery, ocorrência 1/3)
        self.status = kwargs.get("status", "PENDENTE")  # EXPECT: ShotgunSurgery


class Invoice(Model):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.order_id = kwargs.get("order_id")
        self.amount = kwargs.get("amount", 0)
