"""SQLGlot SQL Schema and AST Analysis Integration.

Parses SQL files, extracts table schemas and dialect validations to feed
TargetSnapshot and verification obligations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SQLTableSchema:
    table_name: str
    columns: tuple[str, ...]
    source_file: str


class SQLGlotAnalyzer:
    """Parses SQL files and extracts table schemas."""

    def __init__(self, workspace_root: Path | str = "."):
        self.workspace_root = Path(workspace_root).resolve()

    def analyze_schemas(self) -> list[SQLTableSchema]:
        """Scans .sql files and extracts table definitions."""
        schemas: list[SQLTableSchema] = []

        for path in self.workspace_root.rglob("*.sql"):
            if any(part.startswith((".", "__")) for part in path.parts):
                continue
            try:
                rel_path = str(path.relative_to(self.workspace_root)).replace("\\", "/")
                content = path.read_text(encoding="utf-8", errors="ignore")
                parsed = self.parse_sql_content(content, rel_path)
                schemas.extend(parsed)
            except (UnicodeDecodeError, OSError):
                continue

        return schemas

    @staticmethod
    def parse_sql_content(sql_text: str, source_file: str = "inline.sql") -> list[SQLTableSchema]:
        """Parses CREATE TABLE statements from SQL text."""
        # Check if sqlglot is installed
        try:
            import sqlglot
            from sqlglot import exp

            results: list[SQLTableSchema] = []
            for expression in sqlglot.parse(sql_text):
                if isinstance(expression, exp.Create) and expression.kind == "TABLE":
                    table_name = expression.this.this.name if hasattr(expression.this, "this") else str(expression.this)
                    cols: list[str] = []
                    schema = expression.this
                    if hasattr(schema, "expressions"):
                        for col_def in schema.expressions:
                            if isinstance(col_def, exp.ColumnDef):
                                cols.append(f"{col_def.this.name} {col_def.kind.name}")
                    results.append(
                        SQLTableSchema(
                            table_name=table_name,
                            columns=tuple(cols),
                            source_file=source_file,
                        )
                    )
            if results:
                return results
        except (ImportError, AttributeError, ValueError, TypeError):
            pass

        # Robust regex fallback
        results_fallback: list[SQLTableSchema] = []
        pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?(\w+)["`]?\s*\(([^;]+)\);',
            re.IGNORECASE | re.DOTALL,
        )
        for t_name, body in pattern.findall(sql_text):
            cols = []
            for line in body.splitlines():
                line_s = line.strip().rstrip(",")
                if line_s and not line_s.upper().startswith(
                    ("PRIMARY", "FOREIGN", "KEY", "CONSTRAINT", "UNIQUE", "CHECK", "INDEX", "--")
                ):
                    parts = line_s.split()
                    if len(parts) >= 2:
                        cols.append(f"{parts[0]} {parts[1]}")
            results_fallback.append(
                SQLTableSchema(
                    table_name=t_name,
                    columns=tuple(cols),
                    source_file=source_file,
                )
            )

        return results_fallback
