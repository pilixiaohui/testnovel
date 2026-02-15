import importlib
import importlib.util
import inspect

import pytest


def _import_module(module_path: str):
    try:
        spec = importlib.util.find_spec(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"{module_path} module is missing: {exc}", pytrace=False)
    if spec is None:
        pytest.fail(f"{module_path} module is missing", pytrace=False)
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def get_llm_engine_class():
    module = _import_module("app.services.llm_engine")
    if not hasattr(module, "LLMEngine"):
        pytest.fail("LLMEngine is missing in app.services.llm_engine", pytrace=False)
    return getattr(module, "LLMEngine")


def get_prompts_module():
    return _import_module("app.llm.prompts")


def get_prompt_submodule(name: str):
    return _import_module(f"app.llm.prompts.{name}")


def require_prompt(module, name: str) -> str:
    if not hasattr(module, name):
        pytest.fail(f"prompt {module.__name__}.{name} is missing", pytrace=False)
    value = getattr(module, name)
    if not isinstance(value, str):
        pytest.fail(
            f"prompt {module.__name__}.{name} must be a string", pytrace=False
        )
    if not value.strip():
        pytest.fail(
            f"prompt {module.__name__}.{name} must not be empty", pytrace=False
        )
    return value


def require_async_method(cls: type, name: str):
    if not hasattr(cls, name):
        pytest.fail(f"LLMEngine.{name} is missing", pytrace=False)
    method = getattr(cls, name)
    if not inspect.iscoroutinefunction(method):
        pytest.fail(f"LLMEngine.{name} must be async", pytrace=False)
    return method


def assert_messages_use_prompt(messages, prompt: str) -> None:
    if not isinstance(messages, list) or not messages:
        pytest.fail("messages must be a non-empty list", pytrace=False)
    first = messages[0]
    if first.get("role") != "system":
        pytest.fail("messages[0].role must be 'system'", pytrace=False)
    if first.get("content") != prompt:
        pytest.fail("messages[0].content must match prompt", pytrace=False)
    has_user = any(
        item.get("role") == "user" and str(item.get("content", "")).strip()
        for item in messages
    )
    if not has_user:
        pytest.fail("messages must include a non-empty user message", pytrace=False)
