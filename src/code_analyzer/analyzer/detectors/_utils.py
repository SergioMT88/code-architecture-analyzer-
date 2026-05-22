"""Shared utilities for detectors — avoids duplication detected by cross-file analysis."""
from __future__ import annotations

import ast
from typing import List


def build_parent_map(tree: ast.AST) -> dict:
    """Map id(child) -> parent node for every node in the tree."""
    parent_map: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent_map[id(child)] = node
    return parent_map


def class_bases(node: ast.ClassDef) -> List[str]:
    """Return flat list of base class names for a ClassDef node.

    Includes both the short name (attr) and the full dotted name (e.g. 'models.Model')
    so callers can match against either form.
    """
    bases: List[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(base.attr)
            bases.append(ast.unparse(base))
    return bases
