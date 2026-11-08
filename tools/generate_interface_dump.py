#!/usr/bin/env python3
"""Generate INTERFACE-DUMP.md for Blocks 3-9 (Task G6 / Round 10).

Dumps public function signatures, parameters, defaults, and authority contracts.
Output: delivery-global/INTERFACE-DUMP.md
"""

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCT_DIR = REPO_ROOT / "src" / "sclass" / "product"
OUT_FILE = REPO_ROOT / "delivery-global" / "INTERFACE-DUMP.md"

BLOCK_MODULES = {
    "Block 3 (Lanes F4, E, P11, P0A, P0B, P1P4, P3A, P3B, P3C, P5, P6, P7)": [
        "f4_lane_selection.py", "f8_step_pack.py", "lifecycle_p11.py",
        "lifecycle_p0a.py", "lifecycle_p0b.py", "lifecycle_p1_p4.py",
        "lifecycle_p3a.py", "lifecycle_p3b.py", "lifecycle_p3c_p8_p10.py",
        "lifecycle_p5.py", "lifecycle_p6.py", "lifecycle_p7.py", "replay.py"
    ],
    "Block 4 (Lanes B4-A to B4-F)": [
        "adapter_qualification_contract.py", "adapter_diff_spec_anchors.py",
        "stratum_sampling_compatibility.py", "execution_flow_testinput.py",
        "context_resume_threats.py"
    ],
    "Block 5 (Lane B5)": [
        "enforcement_workspace_gate.py"
    ],
    "Block 6 (Lanes B6-A & B6-B)": [
        "wire_session_consequential_gate.py", "lifecycle_phase_admission.py"
    ],
    "Block 7 (Lanes B7-A & B7-B)": [
        "threat_eval_regression_gate.py", "knowledge_package_quarantine.py"
    ],
    "Block 8 (Lane B8)": [
        "notification_skill_normalization.py"
    ],
    "Block 9 (Lanes B9-A, B9-B, B9-C)": [
        "oss_qualification_playbook.py", "erratum_issue_registry.py", "isolation_claims.py"
    ]
}

def format_arg(arg, default_val=None, is_kwonly=False):
    s = arg.arg
    if arg.annotation:
        s += f": {ast.unparse(arg.annotation)}"
    if default_val is not None:
        s += f" = {ast.unparse(default_val)}"
    return s

def dump_module(py_path: Path) -> list[str]:
    text = py_path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(py_path))
    lines = []
    lines.append(f"### Module `{py_path.name}`\n")

    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    if not functions:
        lines.append("_No public top-level functions._\n")
        return lines

    for fn in functions:
        doc = ast.get_docstring(fn) or "No docstring provided."
        doc_summary = doc.split("\n\n")[0].replace("\n", " ").strip()

        # Build signature string
        args_str = []
        # Positional / standard args
        def_offset = len(fn.args.args) - len(fn.args.defaults)
        for idx, a in enumerate(fn.args.args):
            d = fn.args.defaults[idx - def_offset] if idx >= def_offset else None
            args_str.append(format_arg(a, d))

        # Keyword-only args
        if fn.args.kwonlyargs:
            args_str.append("*")
            for idx, a in enumerate(fn.args.kwonlyargs):
                d = fn.args.kw_defaults[idx] if idx < len(fn.args.kw_defaults) else None
                args_str.append(format_arg(a, d, is_kwonly=True))

        ret_ann = f" -> {ast.unparse(fn.returns)}" if fn.returns else ""
        sig = f"def {fn.name}({', '.join(args_str)}){ret_ann}"

        # Authority status
        has_auth = any(a.arg == "authority" for a in fn.args.kwonlyargs + fn.args.args)
        auth_note = "Keyword-only `authority=None`" if any(a.arg == "authority" for a in fn.args.kwonlyargs) else ("Present" if has_auth else "None")

        lines.append(f"#### `{fn.name}` (line {fn.lineno})")
        lines.append("```python")
        lines.append(sig)
        lines.append("```")
        lines.append(f"- **Authority Parameter**: `{auth_note}`")
        lines.append(f"- **Description**: {doc_summary}\n")

    return lines

def main():
    md = []
    md.append("# INTERFACE DUMP: Blocks 3 through 9 Public Evaluators (Task G6)\n")
    md.append("Machine-generated AST interface sheet for CL and GPT audit review.\n")

    total_funcs = 0
    for block_name, modules in BLOCK_MODULES.items():
        md.append(f"## {block_name}\n")
        for mod_name in modules:
            p = PRODUCT_DIR / mod_name
            if p.exists():
                mod_lines = dump_module(p)
                md.extend(mod_lines)
            else:
                md.append(f"### Module `{mod_name}`: MISSING ON DISK\n")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Generated {OUT_FILE}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
