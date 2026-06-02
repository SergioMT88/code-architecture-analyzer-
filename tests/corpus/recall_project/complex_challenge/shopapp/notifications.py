"""Sistema de notificações: barramento de eventos e canais."""

# literal de status duplicado (shotgun surgery, ocorrência 3/3)
STATUS_PENDING_LABEL = "PENDENTE"  # EXPECT: ShotgunSurgery


class EventBus:
    """Observer: assinantes registram callbacks, notify dispara todos.
    A ligação acontece em OUTRO módulo (services), exigindo grafo cross-file."""

    def __init__(self):
        self._subscribers = []

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def notify(self, event):
        for callback in self._subscribers:
            callback(event)


class EmailChannel:
    def send(self, message):
        return f"email: {message}"


class SmsChannel:
    def send(self, message):
        return f"sms: {message}"


def pick_channel(kind):
    canais = {"email": EmailChannel(), "sms": SmsChannel()}
    return canais.get(kind, EmailChannel())
