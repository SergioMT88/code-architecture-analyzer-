"""Stubs mínimos de ORM/request para o pacote importar sem Django real."""


class _Manager:
    def __init__(self, model):
        self._model = model
        self._rows = []

    def all(self):
        return list(self._rows)

    def get(self, **filtros):
        return self._model(**filtros)

    def filter(self, **filtros):
        return [self._model(**filtros)]

    def create(self, **dados):
        obj = self._model(**dados)
        self._rows.append(obj)
        return obj


class ModelMeta(type):
    def __new__(mcs, nome, bases, ns):
        cls = super().__new__(mcs, nome, bases, ns)
        cls.objects = _Manager(cls)
        return cls


class Model(metaclass=ModelMeta):
    def __init__(self, **kwargs):
        for chave, valor in kwargs.items():
            setattr(self, chave, valor)


class Request:
    """Simula um request HTTP com dados crus do usuário."""

    def __init__(self, data):
        self.data = data
