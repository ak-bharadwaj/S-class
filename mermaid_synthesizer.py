"""
S-Class V12: Mermaid Diagram Synthesizer (mermaid_synthesizer.py)

Synthesizes Mermaid diagrams (flowcharts, sequence diagrams, class diagrams)
from Codebase Knowledge Graph queries and execution paths.
"""

import re
from typing import List, Dict, Any, Optional


class MermaidSynthesizer:
    """
    Translates Codebase Knowledge Graph slices into standards-compliant Mermaid markdown.
    """

    @staticmethod
    def sanitize_id(raw: str) -> str:
        """Sanitizes an arbitrary node ID into a valid Mermaid node identifier."""
        return re.sub(r"[^a-zA-Z0-9_]", "_", raw).strip("_")

    @classmethod
    def generate_flowchart(
        cls,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        direction: str = "TD",
        title: Optional[str] = None,
    ) -> str:
        """Generates a Mermaid graph TD/LR flowchart."""
        lines = []
        if title:
            lines.append(f"--- title: {title} ---")
        lines.append(f"graph {direction}")

        # Subgraph by file if possible, or declare nodes
        nodes_by_id = {n["id"]: n for n in nodes}

        for n in nodes:
            nid = cls.sanitize_id(n["id"])
            label = n.get("name") or n["id"]
            ntype = n.get("type", "").upper()

            if ntype == "ROUTE":
                lines.append(f'    {nid}(["🌐 {label}"])')
            elif ntype == "CLASS":
                lines.append(f'    {nid}[["🏛️ {label}"]]')
            elif ntype == "MODEL":
                lines.append(f'    {nid}[("💾 {label}")]')
            elif ntype == "ADR":
                lines.append(f'    {nid}{{"📜 {label}"}}')
            else:
                lines.append(f'    {nid}["⚡ {label}"]')

        sanitized_node_ids = {cls.sanitize_id(nid) for nid in nodes_by_id}
        for e in edges:
            src = cls.sanitize_id(e["source_id"])
            tgt = cls.sanitize_id(e["target_id"])
            rel = e.get("relation", "")
            if src in sanitized_node_ids and tgt in sanitized_node_ids:
                lines.append(f"    {src} -->|{rel}| {tgt}")

        return "\n".join(lines)

    @classmethod
    def generate_sequence_diagram(
        cls,
        call_chain: List[Dict[str, Any]],
        title: Optional[str] = None,
    ) -> str:
        """Generates a Mermaid sequence diagram from an execution path."""
        lines = ["sequenceDiagram", "    autonumber"]
        if not call_chain or len(call_chain) < 2:
            lines.append("    Note over System: Execution path too short for sequence diagram")
            return "\n".join(lines)

        participants = []
        for n in call_chain:
            p_alias = cls.sanitize_id(n["id"])
            p_name = n.get("name") or n["id"]
            if p_alias not in [p[0] for p in participants]:
                participants.append((p_alias, p_name))

        for p_alias, p_name in participants:
            lines.append(f'    participant {p_alias} as {p_name}')

        for idx in range(len(call_chain) - 1):
            caller = cls.sanitize_id(call_chain[idx]["id"])
            callee = cls.sanitize_id(call_chain[idx + 1]["id"])
            callee_name = call_chain[idx + 1].get("name", "invoke")
            lines.append(f"    {caller}->>+{callee}: call {callee_name}()")
            lines.append(f"    {callee}-->>-{caller}: return result")

        return "\n".join(lines)

    @classmethod
    def generate_class_diagram(
        cls,
        classes: List[Dict[str, Any]],
        relationships: List[Dict[str, Any]],
    ) -> str:
        """Generates a Mermaid class diagram."""
        lines = ["classDiagram"]
        for c in classes:
            cname = cls.sanitize_id(c.get("name") or c["id"])
            doc = c.get("docstring", "")
            lines.append(f"    class {cname} {{")
            if doc:
                lines.append(f"        +{doc[:30]}...")
            lines.append("    }")

        for r in relationships:
            src = cls.sanitize_id(r["source_id"])
            tgt = cls.sanitize_id(r["target_id"])
            rel = r.get("relation", "").upper()
            if rel == "INHERITS":
                lines.append(f"    {tgt} <|-- {src}")
            else:
                lines.append(f"    {src} ..> {tgt} : {rel}")

        return "\n".join(lines)
