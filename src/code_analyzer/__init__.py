"""code_analyzer — Deep Python architecture analysis with automatic refactoring."""
from __future__ import annotations

from code_analyzer.analyzer import run_analysis, prune_criteria
from code_analyzer.refactorer import refactor_file
from code_analyzer.report_generator import generate_reports
from code_analyzer.validator import validate_file
from code_analyzer.config import load_config

__version__ = "2.1.5"
__all__ = [
    "run_analysis",
    "prune_criteria",
    "refactor_file",
    "generate_reports",
    "validate_file",
    "load_config",
]
