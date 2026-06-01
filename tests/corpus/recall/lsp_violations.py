"""Recall fixture: two textbook LSP violations.

1. Square/Rectangle — the canonical Liskov example: the override strengthens the
   precondition by raising an exception the base never raises.
2. A concrete subclass that refuses an inherited method with NotImplementedError.
"""


class Rectangle:
    def __init__(self, w, h):
        self.w = w
        self.h = h

    def scale(self, w, h):
        self.w = w
        self.h = h


class Square(Rectangle):
    def scale(self, w, h):  # EXPECT: LSP
        if w != h:
            raise ValueError("um quadrado precisa de lados iguais")
        self.w = w
        self.h = h


class RepoBase:
    def save(self, obj):
        raise NotImplementedError

    def export_csv(self):
        raise NotImplementedError


class MemoryRepo(RepoBase):
    def save(self, obj):
        self._obj = obj

    def export_csv(self):  # EXPECT: LSP
        raise NotImplementedError("repositorio em memoria nao exporta CSV")
