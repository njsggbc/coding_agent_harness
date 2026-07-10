# tests/test_scaffolding.py
def test_imports():
    import harness
    from harness.core import task
    from harness.adapters import base
    from harness.tools import registry
    from harness.sandbox import base as sandbox_base
    from harness.storage import db
    from harness.observer import base as observer_base
    from harness.report import generator
    from harness.cli import main
