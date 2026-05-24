"""config subcommand — code-analyze config lang [pt|en]."""
from __future__ import annotations

import sys
from typing import List


def run_config_cli(argv: List[str]) -> int:
    from code_analyzer.i18n import get_lang, set_lang, t

    if not argv:
        lang = get_lang()
        print(t("lang_current", lang=lang))
        print(t("lang_usage"))
        return 0

    sub = argv[0].lower()

    if sub == "lang":
        if len(argv) < 2:
            lang = get_lang()
            print(t("lang_current", lang=lang))
            print(t("lang_usage"))
            return 0
        new_lang = argv[1].lower()
        try:
            set_lang(new_lang)
        except ValueError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        from code_analyzer.i18n import t as t2
        print(t2("lang_set"))
        return 0

    print(f"Subcomando desconhecido: '{sub}'", file=sys.stderr)
    print("Subcomandos disponíveis: lang")
    return 1
