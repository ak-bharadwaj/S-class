import os
import sys
import json
import pytest

# Add parent directory to sys.path to import runtime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import runtime


def test_semantic_search_basic(tmp_path):
    workspace = str(tmp_path)
    
    # Learn multiple fixes with distinct patterns
    runtime.MemoryManager.learn_fix(
        pattern="Turbopack CSS syntax error unmatched brace",
        fix_description="Remove rogue closing brace in globals.css Counterfactual panel",
        file_path="frontend/app/globals.css",
        solution_code=".counterfactual-panel { padding: 10px; }",
        workspace_dir=workspace
    )
    runtime.MemoryManager.learn_fix(
        pattern="DeprecationWarning datetime.utcnow() deprecated",
        fix_description="Replace datetime.utcnow() with datetime.now(timezone.utc)",
        file_path="backend/world_model/world_state.py",
        solution_code="from datetime import datetime, timezone; datetime.now(timezone.utc)",
        workspace_dir=workspace
    )
    runtime.MemoryManager.learn_fix(
        pattern="ImportError cannot import name EthicalWeights",
        fix_description="Rename EthicalWeights to PolicyWeights in __init__.py",
        file_path="backend/execution_governance/__init__.py",
        solution_code="from .dap import DAPResult, PolicyWeights",
        workspace_dir=workspace
    )
    
    # Semantic search should find the CSS fix for a related query
    results = runtime.MemoryManager.semantic_search(
        "Build failed because of CSS brace error in Turbopack",
        workspace_dir=workspace
    )
    assert len(results) > 0
    assert results[0]["filePath"] == "frontend/app/globals.css"
    
    # Semantic search should find the deprecation fix somewhere in results
    results = runtime.MemoryManager.semantic_search(
        "DeprecationWarning datetime utcnow deprecated replace with timezone",
        workspace_dir=workspace
    )
    assert len(results) > 0
    # Verify the deprecation fix appears somewhere in the results
    deprecation_found = any(
        "utcnow" in r.get("pattern", "").lower() or "deprecation" in r.get("pattern", "").lower()
        for r in results
    )
    assert deprecation_found, f"Deprecation fix not found in results: {results}"


def test_semantic_search_empty(tmp_path):
    workspace = str(tmp_path)
    
    # No memory file -> empty results
    results = runtime.MemoryManager.semantic_search("some error", workspace_dir=workspace)
    assert results == []
    
    # Empty query -> empty results
    runtime.MemoryManager.learn_fix("test", "test fix", "test.py", "pass", workspace_dir=workspace)
    results = runtime.MemoryManager.semantic_search("", workspace_dir=workspace)
    assert results == []


def test_semantic_search_top_k(tmp_path):
    workspace = str(tmp_path)
    
    # Learn 5 fixes
    for i in range(5):
        runtime.MemoryManager.learn_fix(
            pattern=f"Error type {i} in module {i}",
            fix_description=f"Fix for error type {i}",
            file_path=f"module_{i}.py",
            solution_code=f"fix_{i}()",
            workspace_dir=workspace
        )
    
    # top_k=2 should return at most 2
    results = runtime.MemoryManager.semantic_search(
        "Error type 3 in module",
        workspace_dir=workspace,
        top_k=2
    )
    assert len(results) <= 2


def test_memory_schema_v2(tmp_path):
    workspace = str(tmp_path)
    
    runtime.MemoryManager.learn_fix(
        pattern="test pattern",
        fix_description="test fix",
        file_path="test.py",
        solution_code="pass",
        workspace_dir=workspace
    )
    
    # Verify schema version is written
    memory_file = runtime.MemoryManager.get_memory_file(workspace)
    with open(memory_file, "r", encoding="utf-8") as f:
        memory = json.load(f)
    assert memory["version"] == 2


def test_memory_v1_auto_migration(tmp_path):
    workspace = str(tmp_path)
    agents_dir = os.path.join(workspace, ".agents")
    os.makedirs(agents_dir, exist_ok=True)
    
    # Write a v1 memory file (no version key)
    v1_memory = {
        "fixes": [
            {
                "pattern": "old fix pattern",
                "fixDescription": "legacy fix",
                "filePath": "old.py",
                "solutionCode": "old_fix()",
                "timestamp": "2026-01-01T00:00:00Z"
            }
        ]
    }
    memory_file = os.path.join(agents_dir, "learning_memory.json")
    with open(memory_file, "w", encoding="utf-8") as f:
        json.dump(v1_memory, f)
    
    # Loading should auto-migrate to v2
    memory = runtime.MemoryManager._load_memory(workspace)
    assert memory["version"] == 2
    assert len(memory["fixes"]) == 1
    assert memory["fixes"][0]["pattern"] == "old fix pattern"


def test_tfidf_cosine_scores():
    corpus = [
        "CSS syntax error in globals stylesheet",
        "Python import error cannot find module",
        "Database migration failed sqlite locked",
        "Fix the CSS stylesheet syntax error"  # query
    ]
    scores = runtime.MemoryManager._tfidf_cosine_scores(corpus)
    
    # The CSS document should score highest against the CSS query
    assert len(scores) == 3
    assert scores[0] > scores[1]  # CSS doc > Python doc
    assert scores[0] > scores[2]  # CSS doc > DB doc
