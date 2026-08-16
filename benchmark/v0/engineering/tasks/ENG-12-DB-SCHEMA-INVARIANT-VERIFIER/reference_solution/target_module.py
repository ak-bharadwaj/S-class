# target_module.py
def verify_schema(schema_def: dict) -> list:
    violations = []
    tables = schema_def.get("tables", {})
    
    for tname, tspec in tables.items():
        pk = tspec.get("primary_key")
        if not pk:
            violations.append(f"MISSING_PK:{tname}")
        
        indexes = set(tspec.get("indexes", []))
        for fk in tspec.get("foreign_keys", []):
            fk_col = fk.get("column")
            if fk_col and fk_col not in indexes:
                violations.append(f"UNINDEXED_FK:{tname}:{fk_col}")
                
    return violations
