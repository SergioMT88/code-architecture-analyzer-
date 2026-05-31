"""Design pattern detectors — auto-discovered registry.

Each module in this package exports a ``detect(tree, code)`` function that
returns ``Optional[PatternDetection]``.  The ``PatternAnalyzer`` calls all
registered detectors via ``get_detectors()``.
"""
from __future__ import annotations

import ast
import importlib
import pkgutil
from typing import Callable, List, Optional

from code_analyzer.pattern_analysis import PatternDetection

# Type alias for detector functions
DetectorFunc = Callable[[ast.AST, str], Optional[PatternDetection]]

_REGISTRY: List[DetectorFunc] = []


def register(func: DetectorFunc) -> DetectorFunc:
    """Decorator that adds a detector function to the registry."""
    _REGISTRY.append(func)
    return func


def get_detectors() -> List[DetectorFunc]:
    """Return all registered detector functions."""
    if not _REGISTRY:
        _autoload_detectors()
    return list(_REGISTRY)


def _autoload_detectors() -> None:
    """Import all modules in this package to trigger @register decorators."""
    package = __package__
    if package is None:
        return
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{package}.{module_info.name}")


# Shared utilities for detectors ------------------------------------------------

def get_all_classes(tree: ast.AST) -> List[ast.ClassDef]:
    """Return all ClassDef nodes in the tree."""
    return [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def get_all_functions(tree: ast.AST) -> List[ast.FunctionDef]:
    """Return all FunctionDef nodes in the tree."""
    return [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def get_all_methods(tree: ast.AST) -> List[ast.FunctionDef]:
    """Return all methods (FunctionDef inside ClassDef) in the tree."""
    methods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item)
    return methods


def class_has_method(cls: ast.ClassDef, name: str) -> bool:
    """Check if a class has a method with the given name."""
    for item in cls.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name == name:
                return True
    return False


def class_method_count(cls: ast.ClassDef) -> int:
    """Count the number of methods in a class."""
    return sum(
        1 for item in cls.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
