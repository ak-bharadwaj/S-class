import pytest
import target_module

def test_schema_invariant_verifier():
    schema = {
        "tables": {
            "users": {"primary_key": "id", "indexes": ["id"]},
            "orders": {
                "primary_key": None, # Missing PK
                "foreign_keys": [{"column": "user_id", "references": "users.id"}],
                "indexes": [] # Unindexed FK
            }
        }
    }
    violations = target_module.verify_schema(schema)
    assert "MISSING_PK:orders" in violations
    assert "UNINDEXED_FK:orders:user_id" in violations
