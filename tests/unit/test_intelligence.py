"""
Unit Tests for S-Class Intelligence Subsystem (Batch I).
Covers:
- ASTSymbolParser (symbol extraction for Python & JS/TS)
- RepositoryMapBuilder (compact, budgeted codebase map)
- SymbolImpactEstimator (impacted files and reference search)
"""

import os
import pytest

from sclass.intelligence.parser import ASTSymbolParser, CodeSymbol
from sclass.intelligence.repository import RepositoryMapBuilder
from sclass.intelligence.impact import SymbolImpactEstimator


@pytest.fixture
def workspace_with_code(tmp_path):
    ws = tmp_path / "repo"
    ws.mkdir(parents=True, exist_ok=True)

    # File 1: models.py
    (ws / "models.py").write_text(
        "class UserModel:\n    pass\n\ndef get_user():\n    return UserModel()\n",
        encoding="utf-8",
    )

    # File 2: service.py
    (ws / "service.py").write_text(
        "from models import UserModel, get_user\n\ndef handle_request():\n    return get_user()\n",
        encoding="utf-8",
    )

    return str(ws)


def test_ast_symbol_parser(workspace_with_code):
    models_file = os.path.join(workspace_with_code, "models.py")
    symbols = ASTSymbolParser.parse_file(models_file)

    assert len(symbols) == 2
    names = {s.name for s in symbols}
    assert "UserModel" in names
    assert "get_user" in names

    cls_sym = next(s for s in symbols if s.name == "UserModel")
    assert cls_sym.kind == "class"

    fn_sym = next(s for s in symbols if s.name == "get_user")
    assert fn_sym.kind == "function"


def test_repository_map_builder(workspace_with_code):
    builder = RepositoryMapBuilder(workspace_with_code)
    repo_map = builder.build_map(max_files=10, max_chars=4000)

    assert "Codebase Symbol Map" in repo_map
    assert "models.py" in repo_map
    assert "service.py" in repo_map
    assert "UserModel" in repo_map
    assert "handle_request" in repo_map


def test_symbol_impact_estimator(workspace_with_code):
    estimator = SymbolImpactEstimator(workspace_with_code)

    # Search impact for get_user
    impact = estimator.estimate_impact("get_user")
    assert impact.target == "get_user"
    assert impact.impact_count >= 1
    assert any("service.py" in f for f in impact.impacted_files)

    # Search impact for models.py
    impact_mod = estimator.estimate_impact("models.py")
    assert any("service.py" in f for f in impact_mod.impacted_files)
