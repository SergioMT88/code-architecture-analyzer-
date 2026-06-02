"""Camada de serviço — orquestra repositório, eventos e notificações."""

from .models import Order, Customer
from .repository import SqlOrderRepository
from .security_utils import run_command
from .notifications import EventBus, pick_channel


class OrderService:
    def __init__(self):
        # DIP violado cross-file: depende da implementação CONCRETA,
        # importada e instanciada diretamente, não de uma abstração.
        self.repo = SqlOrderRepository()
        self.action = "ship"

    def enrich_all(self):
        # N+1 cross-file: itera repo.all() e consulta Customer por linha.
        resultado = []
        for order in self.repo.all():
            cliente = Customer.objects.get(id=order.customer_id)
            resultado.append((order, cliente))
        return resultado

    def format_label(self, order):
        # feature envy cross-file: só lê atributos de Order, nada de self.
        return (order.customer_name + ", " + order.street + " "
                + order.number + " - " + order.city + "/"
                + order.state + " CEP " + order.zip)

    def create_from_request(self, request):
        # mass assignment: repassa o payload cru sem allowlist.
        order = Order(**request.data)
        self.repo.save(order)
        return order

    def search_orders(self, user_query):
        # caller do sumidouro SQL — fecha o fluxo de taint inter-módulo.
        return self.repo.search(user_query)

    def cleanup_files(self, user_path):
        # caller do sumidouro de comando — taint vira command injection.
        run_command(["rm", "-rf", user_path])

    def handle(self):
        # string dispatch (método 1/2)
        if self.action == "ship":
            return "enviando"
        elif self.action == "refund":
            return "estornando"
        return "nada"

    def rollback(self):
        # string dispatch (método 2/2)
        if self.action == "ship":
            return "cancelando envio"
        elif self.action == "refund":
            return "revertendo estorno"
        return "nada"


class CheckoutFacade:
    """Facade cross-file: delega para 3 subsistemas em módulos distintos."""

    def __init__(self):
        self._service = OrderService()
        self._bus = EventBus()
        self._channel = pick_channel("email")

    def checkout(self, request):
        order = self._service.create_from_request(request)
        self._bus.notify("checkout")
        self._channel.send("pedido recebido")
        return order
