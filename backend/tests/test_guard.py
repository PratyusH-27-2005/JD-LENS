"""A guard only protects the paths it sits on: every LLM call must go through
app/llm/client.py, so no other module may import an LLM SDK."""

import ast
from pathlib import Path

APP = Path(__file__).parents[1] / "app"
ALLOWED = APP / "llm" / "client.py"
LLM_SDKS = ("google.genai", "google.generativeai", "openai", "anthropic", "litellm")


def _imported_modules(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            # "from google import genai" imports google.genai
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def _is_sdk(module: str) -> bool:
    return any(module == sdk or module.startswith(sdk + ".") for sdk in LLM_SDKS)


def test_only_llm_client_imports_an_llm_sdk():
    offenders = [
        f"{path.relative_to(APP.parent)} imports {module}"
        for path in APP.rglob("*.py")
        if path != ALLOWED
        for module in _imported_modules(ast.parse(path.read_text(encoding="utf-8")))
        if _is_sdk(module)
    ]
    assert offenders == []


def test_guard_actually_detects_sdk_imports():
    for source in ("import openai", "from google import genai", "from google.genai import types"):
        assert any(_is_sdk(mod) for mod in _imported_modules(ast.parse(source))), source


def test_client_is_where_the_sdk_lives():
    tree = ast.parse(ALLOWED.read_text(encoding="utf-8"))
    assert any(_is_sdk(mod) for mod in _imported_modules(tree))
