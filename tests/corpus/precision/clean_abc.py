"""Precision fixture: legitimate ABC + Strategy pattern. Must stay silent.

Guards against the LSP false-positive (NotImplementedError in an abstract base
is the correct idiom, not a violation — fixed in v4.3.1) and against flagging a
clean, intentional Strategy implementation.
"""

from abc import ABC, abstractmethod


class ShippingStrategy(ABC):
    @abstractmethod
    def cost(self, weight):
        raise NotImplementedError


class StandardShipping(ShippingStrategy):
    def cost(self, weight):
        return weight * 1.5


class ExpressShipping(ShippingStrategy):
    def cost(self, weight):
        return weight * 3.0


def shipping_cost(strategy, weight):
    return strategy.cost(weight)
