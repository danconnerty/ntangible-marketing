import importlib


def test_app_bootstrap_imports():
    module = importlib.import_module("app.main")
    assert module.app.title == "NTangible Marketing Engine"
    assert callable(module.verify_api_key)
