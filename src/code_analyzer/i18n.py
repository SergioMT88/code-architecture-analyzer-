"""Internationalization support — pt (default) and en."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_SETTINGS_FILE = Path.home() / ".code-analyzer" / "settings.json"

_STRINGS: dict = {
    "pt": {
        # Welcome
        "welcome_title": "CODE ARCHITECTURE ANALYZER  -  Primeira execucao",
        "welcome_body": (
            "  3 coisas que voce precisa saber:\n"
            "\n"
            "  1. O score mede convencoes estruturais (SOLID, acoplamento, complexidade)\n"
            "     Nao detecta bugs de logica ou problemas em runtime.\n"
            "\n"
            "  2. O relatorio HTML e gerado automaticamente e aberto no seu navegador.\n"
            "\n"
            "  3. Responda s/n quando a ferramenta perguntar sobre um finding.\n"
            "     Ela aprende o que e relevante no SEU projeto ao longo do tempo."
        ),
        "welcome_footer": "Esta mensagem aparece apenas na primeira execucao.",
        # Next steps
        "next_steps_title": "O que fazer agora",
        "good_state_title": "Arquivo em bom estado",
        "good_state_detail": "Sem problemas criticos. Continue monitorando com cada commit.",
        "godclass_title": "GodClass: '{name}' ({lines} linhas) e o problema central",
        "godclass_title_nolines": "GodClass: '{name}' e o problema central",
        "godclass_detail": "Divida em servicos menores antes de qualquer outra refatoracao.",
        "circular_title": "Dependencias circulares detectadas",
        "circular_detail": "Resolva os imports circulares — dificultam testes e refatoracao.",
        "coupling_title": "Acoplamento critico detectado",
        "coupling_detail": "Considere o padrao Facade para isolar as dependencias externas.",
        "nesting_title": "Aninhamento profundo detectado",
        "nesting_detail": "Extraia os blocos aninhados em metodos separados (Early Return).",
        "il_new_title": "Intent Learning ainda nao foi ativado neste projeto",
        "il_new_detail": "Nas proximas analises, responda s/n quando a ferramenta perguntar.",
        "il_existing_title": "Veja o historico de aprendizado",
        "il_existing_detail": "code-analyze intent list  |  code-analyze health",
        # Browser
        "opening_browser": "Abrindo relatorio no navegador...",
        # Config
        "lang_set": "Idioma alterado para: Portugues (pt)",
        "lang_current": "Idioma atual: {lang}",
        "lang_usage": "Uso: code-analyze config lang [pt|en]",
        "setting_saved": "Configuracao salva.",
    },
    "en": {
        # Welcome
        "welcome_title": "CODE ARCHITECTURE ANALYZER  -  First run",
        "welcome_body": (
            "  3 things you need to know:\n"
            "\n"
            "  1. The score measures structural conventions (SOLID, coupling, complexity).\n"
            "     It does NOT detect logic bugs or runtime issues.\n"
            "\n"
            "  2. The HTML report is generated automatically and opened in your browser.\n"
            "\n"
            "  3. Answer y/n when the tool asks about a finding.\n"
            "     It learns what is relevant in YOUR project over time."
        ),
        "welcome_footer": "This message only appears on the first run.",
        # Next steps
        "next_steps_title": "What to do now",
        "good_state_title": "File in good shape",
        "good_state_detail": "No critical issues. Keep monitoring with each commit.",
        "godclass_title": "GodClass: '{name}' ({lines} lines) is the central problem",
        "godclass_title_nolines": "GodClass: '{name}' is the central problem",
        "godclass_detail": "Split into smaller services before any other refactoring.",
        "circular_title": "Circular dependencies detected",
        "circular_detail": "Fix circular imports — they make testing and refactoring harder.",
        "coupling_title": "Critical coupling detected",
        "coupling_detail": "Consider the Facade pattern to isolate external dependencies.",
        "nesting_title": "Deep nesting detected",
        "nesting_detail": "Extract nested blocks into separate methods (Early Return pattern).",
        "il_new_title": "Intent Learning has not been activated for this project yet",
        "il_new_detail": "In future analyses, answer y/n when the tool asks about findings.",
        "il_existing_title": "View your learning history",
        "il_existing_detail": "code-analyze intent list  |  code-analyze health",
        # Browser
        "opening_browser": "Opening report in browser...",
        # Config
        "lang_set": "Language changed to: English (en)",
        "lang_current": "Current language: {lang}",
        "lang_usage": "Usage: code-analyze config lang [pt|en]",
        "setting_saved": "Setting saved.",
    },
}


def get_lang() -> str:
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        return data.get("lang", "pt")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "pt"


def set_lang(lang: str) -> None:
    lang = lang.lower()
    if lang not in ("pt", "en"):
        raise ValueError(f"Idioma nao suportado: '{lang}'. Use 'pt' ou 'en'.")
    _set_setting("lang", lang)


def t(key: str, **kwargs: Any) -> str:
    """Return translated string for current language, falling back to Portuguese."""
    lang = get_lang()
    catalog = _STRINGS.get(lang, _STRINGS["pt"])
    text = catalog.get(key, _STRINGS["pt"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def get_setting(key: str, default: Any = None) -> Any:
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        return data.get(key, default)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def _set_setting(key: str, value: Any) -> None:
    try:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if _SETTINGS_FILE.exists():
            try:
                existing = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                _log.debug("Failed to parse settings file, starting fresh", exc_info=True)
        existing[key] = value
        _SETTINGS_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Nao foi possivel salvar configuracao: {exc}") from exc


set_setting = _set_setting
