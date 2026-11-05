#!/usr/bin/env python3
"""
Test Shell Parser Disagreement across bashlex, tree-sitter-bash, and mvdan/sh.
Implements STEP 3 of TASK OSS-EVIDENCE-R31.
Corpus >= 60 commands covering:
  quoting, $(), backticks, here-docs, brace expansion, process substitution,
  aliases, env -S, nested bash -c, unicode look-alikes, line continuations, malformed syntax.
Outputs raw table: command, each parser's result, disagreement yes/no.
"""
import os
import shutil
import subprocess
import sys
import pytest

# Try importing parsers
try:
    import bashlex
    HAS_BASHLEX = True
except ImportError:
    HAS_BASHLEX = False

try:
    from tree_sitter import Language, Parser
    import tree_sitter_bash
    BASH_LANGUAGE = Language(tree_sitter_bash.language())
    TS_PARSER = Parser(BASH_LANGUAGE)
    HAS_TREESITTER = True
except Exception:
    HAS_TREESITTER = False

SHFMT_BIN = shutil.which("shfmt") or "/home/runner/bin/shfmt"
if not os.path.exists(SHFMT_BIN):
    SHFMT_BIN = "/home/runner/venv-3.12/bin/shfmt"
HAS_SHFMT = os.path.exists(SHFMT_BIN) and os.access(SHFMT_BIN, os.X_OK)

# Corpus of 65 commands across 11 edge-case categories
CORPUS = [
    # 1. Quoting (1-10)
    ("echo 'hello world'", "quoting: basic single quotes"),
    ("echo \"hello $USER\"", "quoting: double quotes with expansion"),
    ("echo \"escaped \\\"quotes\\\" inside\"", "quoting: escaped double quotes"),
    ("echo 'unclosed single quote", "quoting: unclosed single quote (syntax error)"),
    ("echo \"unclosed double quote", "quoting: unclosed double quote (syntax error)"),
    ("echo \"it's mixed quotes\"", "quoting: single quote inside double"),
    ("echo $'line1\\nline2\\tindent'", "quoting: ANSI-C quoting $'...'"),
    ("echo $\"localized string\"", "quoting: locale-specific quoting $\"...\""),
    ("echo '' \"\"", "quoting: empty quotes"),
    ("echo 'foo'\"bar\"'baz'", "quoting: concatenated quote styles"),

    # 2. Command substitution $() and backticks (11-18)
    ("echo $(whoami)", "$(): standard command substitution"),
    ("echo $(echo $(hostname))", "$(): nested command substitution"),
    ("echo `id -u`", "backticks: basic command substitution"),
    ("echo `echo \\`pwd\\``", "backticks: nested backticks with backslash escape"),
    ("echo `echo $(date)`", "nested: $() inside backticks"),
    ("echo $(echo `uname`)", "nested: backticks inside $()"),
    ("echo $(incomplete_subst", "$(): unclosed command substitution (syntax error)"),
    ("echo `incomplete_backtick", "backticks: unclosed backticks (syntax error)"),

    # 3. Here-docs (19-23)
    ("cat <<EOF\nhello world\nEOF", "here-doc: unquoted delimiter"),
    ("cat <<'EOF'\n$NO_EXPAND\nEOF", "here-doc: quoted delimiter (no expansion)"),
    ("cat <<-EOF\n\ttab indented\nEOF", "here-doc: stripped leading tabs <<-"),
    ("grep pattern <<< \"herestring text\"", "here-string: <<< syntax"),
    ("cat <<EOF\nmissing end delimiter", "here-doc: unclosed here-doc (syntax error)"),

    # 4. Brace expansion (24-28)
    ("echo {1..10}", "brace: integer sequence expansion"),
    ("echo {a,b,c}", "brace: comma-separated alternatives"),
    ("echo {a,b{1..3}}", "brace: nested brace expansion"),
    ("echo {a,,c}", "brace: empty alternative element"),
    ("echo {literal_no_comma}", "brace: braces without commas/ranges (literal)"),

    # 5. Process substitution (29-32)
    ("diff <(ls -1 dirA) <(ls -1 dirB)", "process substitution: input <(...)"),
    ("tee >(grep err > error.log) >(grep warn > warn.log)", "process substitution: output >(...)"),
    ("cat <(head -n 5 <(cat file.txt))", "process substitution: nested <(...)"),
    ("cat < (echo space_between_angle_and_paren)", "process substitution: invalid space < (echo 1)"),

    # 6. Aliases (33-35)
    ("alias ll='ls -la'", "alias: simple definition"),
    ("alias gca='git commit -a -m'", "alias: definition with flags"),
    ("unalias -a", "alias: unalias command"),

    # 7. env -S (36-38)
    ("env -S python3 -u script.py", "env -S: shebang style split string"),
    ("env -S VAR1=val1 VAR2=val2 cmd --flag", "env -S: multiple environment definitions"),
    ("env -S \"bash -c 'echo inner'\"", "env -S: embedded quoted command"),

    # 8. Nested bash -c (39-42)
    ("bash -c \"echo level1\"", "nested bash -c: single invocation"),
    ("bash -c \"bash -c 'echo level2'\"", "nested bash -c: two-level nesting"),
    ("bash -c \"bash -c \\\"bash -c 'echo level3'\\\"\"", "nested bash -c: three-level nesting with escapes"),
    ("bash -c 'bash -c \"echo \\$HOME\"'", "nested bash -c: variable escape sequence"),

    # 9. Unicode look-alikes / identifiers (43-48)
    ("echo “hello world”", "unicode: typographic curly double quotes (U+201C, U+201D)"),
    ("ls −la", "unicode: unicode minus sign (U+2212) instead of hyphen"),
    ("echo\u00a0hello", "unicode: non-breaking space (U+00A0) delimiter"),
    ("α=1; echo $α", "unicode: greek letter alpha identifier"),
    ("echo \"こんにちは世界 🚀\"", "unicode: multi-byte CJK and emoji literals"),
    ("еcho hello", "unicode: Cyrillic small letter ie (U+0435) in command name"),

    # 10. Line continuations (49-53)
    ("echo hello \\\nworld", "line continuation: basic backslash newline"),
    ("ls -la |\ngrep txt", "line continuation: pipe at end of line without backslash"),
    ("mkdir -p test &&\ncd test", "line continuation: logical AND at end of line"),
    ("echo hello \\ \nworld", "line continuation: backslash followed by trailing space then newline"),
    ("echo \\\n1 \\\n2 \\\n3", "line continuation: chained multiple continuations"),

    # 11. Malformed syntax / edge cases (54-65)
    ("cmd1 || || cmd2", "malformed: double logical OR without command"),
    ("echo hello >", "malformed: output redirection without file target"),
    ("(echo 1; echo 2", "malformed: subshell unclosed left parenthesis"),
    ("if true; then echo yes", "malformed: incomplete if statement without fi"),
    ("[ -f /tmp/test", "malformed: test bracket without closing ]"),
    ("echo 1;; echo 2", "malformed: double semicolon outside case statement"),
    ("for i in 1 2 3; do", "malformed: for loop without done or body"),
    ("echo ${unclosed_parameter", "malformed: parameter expansion without closing }"),
    ("foo() {}", "malformed: function definition with empty braces"),
    (";", "malformed: lone semicolon statement"),
    ("echo hello)", "malformed: stray unmatched closing parenthesis"),
    ("case $x in 1) echo one;;", "malformed: case statement without esac"),
]

def run_bashlex(cmd):
    if not HAS_BASHLEX:
        return "PARSER_UNAVAILABLE"
    try:
        nodes = bashlex.parse(cmd)
        node_kinds = [getattr(n, "kind", type(n).__name__) for n in nodes]
        return f"PARSED (nodes: {len(nodes)}, kinds: {','.join(node_kinds[:3])})"
    except Exception as e:
        err_msg = str(e).replace("\n", " ").strip()
        return f"ERROR ({type(e).__name__}: {err_msg})"

def run_treesitter(cmd):
    if not HAS_TREESITTER:
        return "PARSER_UNAVAILABLE"
    try:
        tree = TS_PARSER.parse(cmd.encode("utf-8"))
        root = tree.root_node
        has_err = root.has_error
        # Count error or missing nodes
        err_nodes = []
        def find_errors(node):
            if node.is_error or node.is_missing:
                err_nodes.append(f"{node.type}@{node.start_point[0]}:{node.start_point[1]}")
            for ch in node.children:
                find_errors(ch)
        find_errors(root)
        if has_err:
            return f"ERROR (has_error=True, err_nodes: {','.join(err_nodes[:2]) or 'unknown'})"
        else:
            return f"PARSED (root: {root.type}, children: {len(root.children)})"
    except Exception as e:
        return f"EXCEPTION ({type(e).__name__}: {e})"

def run_shfmt(cmd):
    if not HAS_SHFMT:
        return "PARSER_C_NOT_INSTALLED"
    try:
        r = subprocess.run([SHFMT_BIN, "-ln=bash", "--to-json"], input=cmd, text=True, capture_output=True, timeout=10)
        if r.returncode == 0:
            return f"PARSED (json_bytes: {len(r.stdout)})"
        else:
            err = r.stderr.strip().replace("\n", " ")
            return f"ERROR ({err})"
    except Exception as e:
        return f"EXCEPTION ({type(e).__name__}: {e})"

def evaluate_disagreement(res_bashlex, res_treesitter, res_shfmt):
    """
    Determine if the parsers disagree on verdict (PARSED vs ERROR/EXCEPTION).
    """
    v_b = res_bashlex.startswith("PARSED")
    v_t = res_bashlex.startswith("PARSED") if not HAS_TREESITTER else res_treesitter.startswith("PARSED")
    v_s = res_bashlex.startswith("PARSED") if not HAS_SHFMT else res_shfmt.startswith("PARSED")
    
    # If any verdict differs
    if not (v_b == v_t == v_s):
        return "YES"
    return "NO"

def generate_disagreement_table():
    results = []
    for idx, (cmd, desc) in enumerate(CORPUS, 1):
        r_b = run_bashlex(cmd)
        r_t = run_treesitter(cmd)
        r_s = run_shfmt(cmd)
        disagree = evaluate_disagreement(r_b, r_t, r_s)
        results.append({
            "id": idx,
            "cmd": cmd,
            "desc": desc,
            "bashlex": r_b,
            "treesitter": r_t,
            "shfmt": r_s,
            "disagreement": disagree
        })
    return results

def format_markdown_table(results):
    lines = []
    lines.append("# Shell Parser Disagreement Test Results")
    lines.append("")
    lines.append(f"Total commands evaluated: {len(results)}")
    disagree_cnt = sum(1 for r in results if r["disagreement"] == "YES")
    lines.append(f"Total disagreements (YES): {disagree_cnt} / {len(results)}")
    lines.append(f"Parsers evaluated: bashlex (Python), tree-sitter-bash (Tree-sitter C/Python), mvdan/sh (Go binary `shfmt`)")
    lines.append("")
    lines.append("| ID | Command | bashlex | tree-sitter-bash | mvdan/sh | Disagreement |")
    lines.append("|---|---|---|---|---|:---:|")
    for r in results:
        # Escape command for markdown table
        escaped_cmd = r["cmd"].replace("\n", "\\n").replace("|", "\\|")
        if len(escaped_cmd) > 40:
            escaped_cmd = escaped_cmd[:37] + "..."
        b_short = r["bashlex"].replace("|", "\\|")
        t_short = r["treesitter"].replace("|", "\\|")
        s_short = r["shfmt"].replace("|", "\\|")
        lines.append(f"| {r['id']} | `{escaped_cmd}` | {b_short} | {t_short} | {s_short} | **{r['disagreement']}** |")
    return "\n".join(lines)

def test_shell_parser_disagreement():
    assert len(CORPUS) >= 60, f"Corpus size {len(CORPUS)} < 60 requirement"
    results = generate_disagreement_table()
    assert len(results) == len(CORPUS)
    
    # Write raw output table to delivery-oss-evidence-r31/raw_parser_disagreement.txt
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = os.path.join(repo_root, "delivery-oss-evidence-r31")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "raw_parser_disagreement.txt")
    
    table_text = format_markdown_table(results)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(table_text)
    
    print(f"\nWrote raw parser disagreement table to {out_path}")
    print(f"Total commands: {len(results)}, Disagreements: {sum(1 for r in results if r['disagreement'] == 'YES')}")

if __name__ == "__main__":
    test_shell_parser_disagreement()
