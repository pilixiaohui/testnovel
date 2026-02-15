import importlib
import importlib.util
import inspect
from unittest.mock import Mock

import pytest


def load_module(module_path: str):
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
    except ImportError as exc:
        pytest.fail(f"failed to import {module_path}: {exc}", pytrace=False)


def require_class(module, name: str) -> type:
    if not hasattr(module, name):
        pytest.fail(f"{module.__name__}.{name} is missing", pytrace=False)
    cls = getattr(module, name)
    if not inspect.isclass(cls):
        pytest.fail(f"{module.__name__}.{name} must be a class", pytrace=False)
    return cls


def require_async_method(cls: type, name: str):
    if not hasattr(cls, name):
        pytest.fail(f"{cls.__name__}.{name} is missing", pytrace=False)
    method = getattr(cls, name)
    if not inspect.iscoroutinefunction(method):
        pytest.fail(f"{cls.__name__}.{name} must be async", pytrace=False)
    return method


def require_init_params(cls: type, required: set[str]) -> None:
    sig = inspect.signature(cls.__init__)
    param_names = [
        param.name
        for param in sig.parameters.values()
        if param.name != "self"
        and param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
    ]
    missing = sorted(name for name in required if name not in param_names)
    if missing:
        pytest.fail(
            f"{cls.__name__}.__init__ missing params: {missing}", pytrace=False
        )


def build_instance(cls: type):
    sig = inspect.signature(cls.__init__)
    kwargs = {}
    for param in sig.parameters.values():
        if param.name == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        if param.default is inspect._empty:
            kwargs[param.name] = Mock()
    return cls(**kwargs)
