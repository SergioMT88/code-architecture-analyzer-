"""Precision fixture: benign **kwargs forwarding. Must stay silent.

Forwarding **kwargs to super().__init__ and merging config dicts are idiomatic
and not mass assignment. A subclass __init__ with extra params is a legitimate
constructor override, not an LSP signature mismatch.
"""


class Base:
    def __init__(self, name):
        self.name = name


class Extended(Base):
    def __init__(self, name, extra=None, **kwargs):
        super().__init__(name, **kwargs)
        self.extra = extra


def merge_defaults(overrides):
    defaults = {"timeout": 30}
    return dict(defaults, **overrides)
