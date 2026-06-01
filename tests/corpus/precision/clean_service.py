"""Precision fixture: small, cohesive, idiomatic class. Must stay silent.

Guards against false positives on well-formed code: a focused class whose
methods share state, a proper super().__init__ call, secrets read from the
environment, and a generator (not a list comp) inside any().
"""

import os


class PriceCalculator:
    def __init__(self, tax_rate):
        self.tax_rate = tax_rate
        self.items = []

    def add(self, price):
        self.items.append(price)

    def subtotal(self):
        return sum(self.items)

    def total(self):
        return self.subtotal() * (1 + self.tax_rate)


class DiscountedCalculator(PriceCalculator):
    def __init__(self, tax_rate, discount):
        super().__init__(tax_rate)
        self.discount = discount

    def total(self):
        return super().total() * (1 - self.discount)


def get_api_key():
    return os.environ["BILLING_API_KEY"]


def any_expensive(prices, limit):
    return any(p > limit for p in prices)
