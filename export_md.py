"""
S-Class EOS Markdown Exporter (export_md.py)

Automatically exports .json blueprints and interaction matrices to human-readable GitHub-flavored Markdown (.md) files in both .agents/ and project root.
"""

import os
import json
import logging

logger = logging.getLogger("sclass_export_md")


def export_blueprints_to_md(workspace_dir: str):
    """Exports design_blueprint.json and role_interaction_matrix.json to root .md files."""
    agent_dir = os.path.join(workspace_dir, ".agents")
    if not os.path.exists(agent_dir):
        return

    # 1. Export design_blueprint.md & Root Specifications
    bp_json_path = os.path.join(agent_dir, "design_blueprint.json")
    if os.path.exists(bp_json_path):
        try:
            with open(bp_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Generate SYSTEM_ARCHITECTURE.md
            b = data.get("backend_spec", {})
            arch_lines = ["# 🏛️ Enterprise System Architecture Blueprint\n"]
            arch_lines.append(f"- **Framework:** `{b.get('framework', 'N/A')}`")
            arch_lines.append(f"- **Base Path:** `{b.get('basePath', '/api')}`")
            auth = b.get("auth", {})
            arch_lines.append(f"- **Auth Guard:** `{auth.get('type', 'JWT')}` (Expiry: `{auth.get('accessTokenExpiry', '15m')}`)\n")
            arch_lines.append("### API Endpoints & Controller Matrix")
            arch_lines.append("| HTTP Verb | API Endpoint | Public | Description |")
            arch_lines.append("| --- | --- | --- | --- |")
            for ep in b.get("endpoints", []):
                is_pub = "Yes" if ep.get("public") else "No"
                arch_lines.append(f"| `{ep.get('method')}` | `{ep.get('path')}` | {is_pub} | {ep.get('description')} |")

            arch_md_path = os.path.join(workspace_dir, "SYSTEM_ARCHITECTURE.md")
            with open(arch_md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(arch_lines))

            # Generate DATABASE_SCHEMA.md
            db = data.get("db_schema", {})
            db_lines = [f"# 🗄️ Database Relational Schema Specification (`{db.get('provider', 'postgresql')}`)\n"]
            db_lines.append("| Entity Table Name | Description |")
            db_lines.append("| --- | --- |")
            for t in db.get("tables", []):
                db_lines.append(f"| `{t.get('name')}` | {t.get('description')} |")

            db_md_path = os.path.join(workspace_dir, "DATABASE_SCHEMA.md")
            with open(db_md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(db_lines))

            # Generate FRONTEND_DESIGN_SYSTEM.md
            fe = data.get("frontend_layout", {})
            fe_lines = ["# 🎨 Frontend Layout & UX Design System Specification\n"]
            fe_lines.append(f"- **Framework:** `{fe.get('framework', 'Next.js')}`")
            fe_lines.append(f"- **Styling:** `{fe.get('styling', 'Tailwind CSS')}`")
            fe_lines.append(f"- **Theme Tokens:** `{fe.get('theme', 'Dark Mode')}`\n")
            fe_lines.append("### Route Hierarchy & Screen Views")
            fe_lines.append("| Route Path | View Description |")
            fe_lines.append("| --- | --- |")
            for p in fe.get("pages", []):
                fe_lines.append(f"| `{p.get('path')}` | {p.get('description')} |")

            fe_md_path = os.path.join(workspace_dir, "FRONTEND_DESIGN_SYSTEM.md")
            with open(fe_md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(fe_lines))

            logger.info("Successfully exported root architecture, database, and frontend .md files")
        except Exception as e:
            logger.error(f"Failed exporting system design .md files: {e}")

    # 2. Export ROLE_INTERACTION_MATRIX.md
    rm_json_path = os.path.join(agent_dir, "role_interaction_matrix.json")
    rm_md_path = os.path.join(workspace_dir, "ROLE_INTERACTION_MATRIX.md")
    if os.path.exists(rm_json_path):
        try:
            with open(rm_json_path, "r", encoding="utf-8") as f:
                rdata = json.load(f)

            lines = ["# 🧠 Role-Coupled Cross-Domain Interaction Matrix\n"]
            lines.append("| User Role | Permitted Views | Actions | API Endpoints | DB Entities | Frontend Components |")
            lines.append("| --- | --- | --- | --- | --- | --- |")

            for r in rdata.get("roles", []):
                role = r.get("role", "N/A")
                views = "<br>".join([f"`{v}`" for v in r.get("permittedViews", [])])
                actions = "<br>".join(r.get("actions", []))
                apis = "<br>".join([f"`{a}`" for a in r.get("apiEndpoints", [])])
                dbs = "<br>".join([f"`{d}`" for d in r.get("dbEntities", [])])
                fecs = "<br>".join([f"`{c}`" for c in r.get("frontendComponents", [])])
                lines.append(f"| **{role}** | {views} | {actions} | {apis} | {dbs} | {fecs} |")

            with open(rm_md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logger.info(f"Exported ROLE_INTERACTION_MATRIX.md at {rm_md_path}")
        except Exception as e:
            logger.error(f"Failed exporting ROLE_INTERACTION_MATRIX.md: {e}")


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\dorni\OneDrive\Desktop\aa"
    export_blueprints_to_md(target)
