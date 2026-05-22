"""Min-score gate — pre-commit hook support."""
from __future__ import annotations

from typing import Any, Dict, Optional

from code_analyzer.terminal_ui import ScoreBundle


def check_min_score(
    sb: ScoreBundle,
    min_score_arg: Optional[float],
    config: Dict[str, Any],
    quiet: bool = False,
    json_mode: bool = False,
) -> int:
    threshold = min_score_arg if min_score_arg is not None else config.get("min_score")
    if threshold is None:
        return 0
    if sb.avg_score < threshold:
        if not json_mode:
            msg = (
                f"\n  \033[91m[BLOQUEADO]\033[0m Score medio {sb.avg_score}/10 "
                f"abaixo do minimo exigido {threshold}/10.\n"
                f"  Corrija os problemas acima antes de commitar."
            )
            print(msg)
        return 1
    return 0
