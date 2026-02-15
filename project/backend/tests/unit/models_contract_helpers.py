import importlib
import importlib.util
import inspect

import pytest
from pydantic import BaseModel


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


def get_models_module():
    return _import_module("app.models")


def require_model(name: str) -> type:
    module = get_models_module()
    if not hasattr(module, name):
        pytest.fail(f"models.{name} is missing", pytrace=False)
    cls = getattr(module, name)
    if not inspect.isclass(cls):
        pytest.fail(f"models.{name} must be a class", pytrace=False)
    if not issubclass(cls, BaseModel):
        pytest.fail(f"models.{name} must inherit BaseModel", pytrace=False)
    return cls
