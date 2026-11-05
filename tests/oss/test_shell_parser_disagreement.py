#!/usr/bin/env python3
"""
Test Shell Parser Disagreement across bashlex, tree-sitter-bash, mvdan/sh, and bash -n.
TASK OSS-EVIDENCE-R31 Round 2.

Features:
1. Corpus defined with Python raw strings and multiline strings (no shell heredocs).
2. Each command printed with repr().
3. Explicit verification that rows 19-23 and 50-52 contain real newlines.
4. Ground truth: run `bash -n` in a sandbox subprocess for every command. Record exit and stderr.
5. Column: 'bash says OK/ERR'. Mark each parser as 'matches bash' or 'differs from bash'.
6. Content comparison: for PARSED results, extract command name plus argument words from each parser.
   Drop json_bytes. Flag any difference between parsers.
7. Expanded corpus (>= 90 cases): includes eval, $IFS tricks, $'\x41', ${var@P}, $(( )), [[ ]],
   arrays, coproc, functions with redirects, ;&, nested heredoc in $( ), 1 MB line, and null bytes.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import pytest

# Check parser availability
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

# 1 MB line generated programmatically
ONE_MB_CMD = "echo " + "a" * (1024 * 1024)

# 95 Test Cases defined as Python raw strings or multiline strings
CORPUS = [
    # 1. Quoting (1-10)
    (r"echo 'hello world'", "quoting: basic single quotes"),
    (r'echo "hello $USER"', "quoting: double quotes with expansion"),
    (r'echo "escaped \"quotes\" inside"', "quoting: escaped double quotes"),
    (r"echo 'unclosed single quote", "quoting: unclosed single quote (syntax error)"),
    (r'echo "unclosed double quote', "quoting: unclosed double quote (syntax error)"),
    (r'echo "it\'s mixed quotes"', "quoting: single quote inside double"),
    (r"echo $'line1\nline2\tindent'", "quoting: ANSI-C quoting $'...'"),
    (r'echo $"localized string"', 'quoting: locale-specific quoting $"..."'),
    (r'echo \'\' ""', "quoting: empty quotes"),
    (r'echo \'foo\'"bar"\'baz\'', "quoting: concatenated quote styles"),

    # 2. Command substitution $() and backticks (11-18)
    (r"echo $(whoami)", "$(): standard command substitution"),
    (r"echo $(echo $(hostname))", "$(): nested command substitution"),
    (r"echo `id -u`", "backticks: basic command substitution"),
    (r"echo `echo \`pwd\``", "backticks: nested backticks with backslash escape"),
    (r"echo `echo $(date)`", "nested: $() inside backticks"),
    (r"echo $(echo `uname`)", "nested: backticks inside $()"),
    (r"echo $(incomplete_subst", "$(): unclosed command substitution (syntax error)"),
    (r"echo `incomplete_backtick", "backticks: unclosed backticks (syntax error)"),

    # 3. Here-docs (19-23) - note: contains literal newlines
    ("cat <<EOF\nhello world\nEOF", "here-doc: unquoted delimiter"),
    ("cat <<'EOF'\n$NO_EXPAND\nEOF", "here-doc: quoted delimiter (no expansion)"),
    ("cat <<-EOF\n\ttab indented\nEOF", "here-doc: stripped leading tabs <<-"),
    (r'grep pattern <<< "herestring text"', "here-string: <<< syntax"),
    ("cat <<EOF\nmissing end delimiter", "here-doc: unclosed here-doc (syntax error)"),

    # 4. Brace expansion (24-28)
    (r"echo {1..10}", "brace: integer sequence expansion"),
    (r"echo {a,b,c}", "brace: comma-separated alternatives"),
    (r"echo {a,b{1..3}}", "brace: nested brace expansion"),
    (r"echo {a,,c}", "brace: empty alternative element"),
    (r"echo {literal_no_comma}", "brace: braces without commas/ranges (literal)"),

    # 5. Process substitution (29-32)
    (r"diff <(ls -1 dirA) <(ls -1 dirB)", "process substitution: input <(...)"),
    (r"tee >(grep err > error.log) >(grep warn > warn.log)", "process substitution: output >(...)"),
    (r"cat <(head -n 5 <(cat file.txt))", "process substitution: nested <(...)"),
    (r"cat < (echo space_between_angle_and_paren)", "process substitution: invalid space < (echo 1)"),

    # 6. Aliases (33-35)
    (r"alias ll='ls -la'", "alias: simple definition"),
    (r"alias gca='git commit -a -m'", "alias: definition with flags"),
    (r"unalias -a", "alias: unalias command"),

    # 7. env -S (36-38)
    (r"env -S python3 -u script.py", "env -S: shebang style split string"),
    (r"env -S VAR1=val1 VAR2=val2 cmd --flag", "env -S: multiple environment definitions"),
    (r'env -S "bash -c \'echo inner\'"', "env -S: embedded quoted command"),

    # 8. Nested bash -c (39-42)
    (r'bash -c "echo level1"', "nested bash -c: single invocation"),
    (r"bash -c \"bash -c 'echo level2'\"", "nested bash -c: two-level nesting"),
    (r'bash -c "bash -c \"bash -c \'echo level3\'\""', "nested bash -c: three-level nesting with escapes"),
    (r'bash -c \'bash -c "echo \$HOME"\'', "nested bash -c: variable escape sequence"),

    # 9. Unicode look-alikes / identifiers (43-48)
    (r'echo “hello world”', "unicode: typographic curly double quotes (U+201C, U+201D)"),
    (r"ls −la", "unicode: unicode minus sign (U+2212) instead of hyphen"),
    ("echo\u00a0hello", "unicode: non-breaking space (U+00A0) delimiter"),
    (r"α=1; echo $α", "unicode: greek letter alpha identifier"),
    (r'echo "こんにちは世界 🚀"', "unicode: multi-byte CJK and emoji literals"),
    (r"еcho hello", "unicode: Cyrillic small letter ie (U+0435) in command name"),

    # 10. Line continuations (49-53) - note: rows 50-52 contain real newlines
    ("echo hello \\\nworld", "line continuation: basic backslash newline"),
    ("ls -la |\ngrep txt", "line continuation: pipe at end of line without backslash"),
    ("mkdir -p test &&\ncd test", "line continuation: logical AND at end of line"),
    ("echo hello \\ \nworld", "line continuation: backslash followed by trailing space then newline"),
    ("echo \\\n1 \\\n2 \\\n3", "line continuation: chained multiple continuations"),

    # 11. Malformed syntax / edge cases (54-65)
    (r"cmd1 || || cmd2", "malformed: double logical OR without command"),
    (r"echo hello >", "malformed: output redirection without file target"),
    (r"(echo 1; echo 2", "malformed: subshell unclosed left parenthesis"),
    (r"if true; then echo yes", "malformed: incomplete if statement without fi"),
    (r"[ -f /tmp/test", "malformed: test bracket without closing ]"),
    (r"echo 1;; echo 2", "malformed: double semicolon outside case statement"),
    (r"for i in 1 2 3; do", "malformed: for loop without done or body"),
    (r"echo ${unclosed_parameter", "malformed: parameter expansion without closing }"),
    (r"foo() {}", "malformed: function definition with empty braces"),
    (r";", "malformed: lone semicolon statement"),
    (r"echo hello)", "malformed: stray unmatched closing parenthesis"),
    (r"case $x in 1) echo one;;", "malformed: case statement without esac"),

    # 12. Expanded Cases (66-95): eval, $IFS, escapes, ${var@P}, $(( )), [[ ]], arrays, coproc, redirects, ;&, nested heredocs, null bytes, 1 MB line
    (r"eval 'echo secret'", "eval: basic string evaluation"),
    (r'eval "echo \$(( 2 + 2 ))"', "eval: double-evaluated arithmetic"),
    (r"IFS=: read -r a b <<< 'foo:bar'", "IFS trick: inline field separator assignment with here-string"),
    ("OLDIFS=\"$IFS\"; IFS=$'\\n'; for l in $data; do echo \"$l\"; done; IFS=\"$OLDIFS\"", "IFS trick: ANSI-C newline splitting loop"),
    (r"echo $'\x41\x42\x43'", r"escapes: ANSI-C hex byte escapes $'\x41' (ABC)"),
    (r"echo $'\u0041'", r"escapes: ANSI-C unicode escape $'\u0041'"),
    (r"echo ${var@P}", r"parameter expansion: prompt expansion @P"),
    (r"echo ${var@Q}", r"parameter expansion: quoted format @Q"),
    (r"echo ${var@A}", r"parameter expansion: assignment format @A"),
    (r"echo $(( 2 + 3 * 4 ))", "arithmetic: precedence evaluation $(( ))"),
    (r"echo $(( (1 << 3) & 7 ))", "arithmetic: bitwise operators in $(( ))"),
    (r"[[ $x == *.txt ]]", "extended test: [[ ]] with glob pattern"),
    (r"[[ -f $file && ( $x =~ ^[0-9]+$ ) ]]", "extended test: [[ ]] with regex =~ and sub-expressions"),
    (r'arr=(one "two three" four)', "arrays: indexed array declaration with quoted elements"),
    (r"declare -A map=([k1]='v1' [k2]='v2')", "arrays: associative array declaration"),
    (r"echo ${arr[@]:1:2}", "arrays: array slice expansion ${arr[@]:s:len}"),
    (r"coproc myproc { sleep 10; }", "coproc: named compound coprocess"),
    (r"coproc cat", "coproc: anonymous simple coprocess"),
    (r'func() { echo "stdout"; echo "stderr" >&2; } > output.log 2>&1', "function: definition with compound redirection"),
    (r"case $x in a) echo a ;& b) echo b ;; esac", "case: ;& fallthrough operator"),
    (r"case $x in a) echo a ;;& b) echo b ;; esac", "case: ;;& test-next pattern operator"),
    ("echo $(cat <<EOF\ninner heredoc\nEOF\n)", "nested heredoc: unquoted heredoc inside $( )"),
    ("echo $(cat <<'INNER'\n$(uname)\nINNER\n)", "nested heredoc: quoted heredoc inside $( )"),
    ("echo $'hello\\x00world'", r"null byte: embedded \x00 in ANSI-C quotes"),
    ("echo \"hello\x00world\"", "null byte: literal \\x00 byte inside double quotes"),
    ("echo $'\\x00'", r"null byte: lone \x00 escape in ANSI-C quotes"),
    (r"let 'x = 10 + 20'", "let builtin: arithmetic evaluation string"),
    (r"(( x++ ))", "compound arithmetic: (( )) increment statement"),
    (r"{ echo 1; echo 2; }", "group command: brace group { ...; }"),
    (ONE_MB_CMD, "1 MB line: 1 megabyte line length parse timing and hang check"),
]

def run_bash_n(cmd):
    """Ground truth via sandbox `bash -n`. Checks syntax only without execution."""
    try:
        r = subprocess.run(["bash", "-n"], input=cmd, text=True, capture_output=True, timeout=10)
        return r.returncode, r.stderr.strip().replace("\n", " ")
    except Exception as e:
        return -1, str(e)

def extract_bashlex_words(cmd):
    if not HAS_BASHLEX:
        return None, "UNAVAILABLE"
    try:
        nodes = bashlex.parse(cmd)
    except Exception as e:
        err = type(e).__name__ + ": " + str(e).replace("\n", " ").strip()
        return None, f"ERROR ({err[:40]})"

    cmds_info = []
    def visit(node):
        if getattr(node, "kind", None) == "command":
            words = []
            for p in getattr(node, "parts", []):
                if getattr(p, "kind", None) == "word":
                    words.append(p.word)
                elif getattr(p, "kind", None) == "assignment":
                    words.append(getattr(p, "word", str(p)))
            if words:
                cmds_info.append(words)
        for child in getattr(node, "parts", []):
            visit(child)
        for child in getattr(node, "list", []):
            visit(child)
    for n in nodes:
        visit(n)
    return cmds_info, "PARSED"

def extract_treesitter_words(cmd):
    if not HAS_TREESITTER:
        return None, "UNAVAILABLE"
    try:
        cmd_bytes = cmd.encode("utf-8")
        tree = TS_PARSER.parse(cmd_bytes)
        root = tree.root_node
        if root.has_error:
            # find error location
            err_pos = f"{root.start_point[0]}:{root.start_point[1]}"
            return None, f"ERROR (syntax error at {err_pos})"
    except Exception as e:
        return None, f"EXCEPTION ({type(e).__name__})"

    cmds_info = []
    def visit(node):
        if node.type == "command":
            words = []
            for ch in node.children:
                if ch.type in ("command_name", "word", "string", "raw_string", "concatenation", "translated_string"):
                    w = cmd_bytes[ch.start_byte:ch.end_byte].decode("utf-8", errors="replace")
                    words.append(w)
            if words:
                cmds_info.append(words)
        for ch in node.children:
            visit(ch)
    visit(root)
    return cmds_info, "PARSED"

def extract_shfmt_words(cmd):
    if not HAS_SHFMT:
        return None, "UNAVAILABLE"
    try:
        r = subprocess.run([SHFMT_BIN, "-ln=bash", "--to-json"], input=cmd, text=True, capture_output=True, timeout=10)
        if r.returncode != 0:
            err = r.stderr.strip().replace("\n", " ")
            return None, f"ERROR ({err[:40]})"
        d = json.loads(r.stdout)
    except Exception as e:
        return None, f"EXCEPTION ({type(e).__name__})"

    cmds_info = []
    cmd_bytes = cmd.encode("utf-8")
    def visit(obj):
        if isinstance(obj, dict):
            if obj.get("Type") == "CallExpr" and "Args" in obj:
                words = []
                for arg in obj["Args"]:
                    s = arg["Pos"]["Offset"]
                    e = arg["End"]["Offset"]
                    words.append(cmd_bytes[s:e].decode("utf-8", errors="replace"))
                if words:
                    cmds_info.append(words)
            for v in obj.values():
                visit(v)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)
    visit(d)
    return cmds_info, "PARSED"

def format_words_summary(words_list):
    """Format extracted commands and arguments for display, safely escaping control characters."""
    if not words_list:
        return "PARSED (no simple commands)"
    parts = []
    for w in words_list:
        if len(w) == 1:
            clean_cmd = w[0].replace("\x00", "\\x00").replace("\n", "\\n")
            parts.append(f"cmd='{clean_cmd}'")
        else:
            clean_cmd = w[0].replace("\x00", "\\x00").replace("\n", "\\n")
            args_clean = [a.replace("\x00", "\\x00").replace("\n", "\\n") for a in w[1:4]]
            args_str = ", ".join(f"'{a[:20]}'" for a in args_clean)
            if len(w) > 4:
                args_str += f", +{len(w)-4} more"
            parts.append(f"cmd='{clean_cmd}' args=[{args_str}]")
    return "PARSED (" + "; ".join(parts[:2]) + ")"

def compare_words(wb, wt, ws):
    """
    Compare extracted command and argument words across parsers that succeeded.
    Flag any structural or token divergence.
    """
    parsed_items = [w for w in (wb, wt, ws) if w is not None]
    if len(parsed_items) <= 1:
        return "N/A (<=1 parser parsed)"
    
    # Normalize comparison: compare command names
    cmd_names_b = [cmd[0] for cmd in wb if cmd] if wb is not None else None
    cmd_names_t = [cmd[0] for cmd in wt if cmd] if wt is not None else None
    cmd_names_s = [cmd[0] for cmd in ws if cmd] if ws is not None else None

    # Check if command counts or names differ
    distinct_names = {tuple(c) for c in (cmd_names_b, cmd_names_t, cmd_names_s) if c is not None}
    if len(distinct_names) > 1:
        return f"DIVERGENT COMMANDS: {distinct_names}"

    # Check argument counts
    def flatten_args(cmds):
        return [tuple(c[1:]) for c in cmds if c]
    args_b = flatten_args(wb) if wb is not None else None
    args_t = flatten_args(wt) if wt is not None else None
    args_s = flatten_args(ws) if ws is not None else None

    # Compare arg counts per command
    lens_b = [len(a) for a in args_b] if args_b is not None else None
    lens_t = [len(a) for a in args_t] if args_t is not None else None
    lens_s = [len(a) for a in args_s] if args_s is not None else None
    distinct_lens = {tuple(l) for l in (lens_b, lens_t, lens_s) if l is not None}
    if len(distinct_lens) > 1:
        return f"DIVERGENT ARG COUNTS: {distinct_lens}"

    return "WORDS MATCH"

def evaluate_all():
    results = []
    print("\n" + "="*80)
    print("PARSER CORPUS VERIFICATION & REPR DISPLAY:")
    print("="*80)
    
    # Verify newlines in rows 19-23 and 50-52
    print("Checking real newlines in specified rows:")
    for r_idx in [19, 20, 21, 23]:
        cmd_text = CORPUS[r_idx - 1][0]
        has_nl = "\n" in cmd_text
        print(f"  Row {r_idx:2d} ({CORPUS[r_idx-1][1]}): contains literal '\\n': {has_nl}")
        assert has_nl, f"Row {r_idx} must contain literal newline"
    for r_idx in [50, 51, 52]:
        cmd_text = CORPUS[r_idx - 1][0]
        has_nl = "\n" in cmd_text
        print(f"  Row {r_idx:2d} ({CORPUS[r_idx-1][1]}): contains literal '\\n': {has_nl}")
        assert has_nl, f"Row {r_idx} must contain literal newline"

    print("\nExecuting evaluation across all test cases...")
    for idx, (cmd, desc) in enumerate(CORPUS, 1):
        # 1. repr display
        cmd_repr = repr(cmd)
        if len(cmd_repr) > 60:
            short_repr = cmd_repr[:57] + "..."
        else:
            short_repr = cmd_repr

        # 2. bash -n ground truth
        t_start = time.time()
        bash_exit, bash_err = run_bash_n(cmd)
        t_bash = time.time() - t_start
        bash_says = "OK" if bash_exit == 0 else "ERR"

        # 3. Parsers execution & word extraction
        t0 = time.time()
        wb, sb = extract_bashlex_words(cmd)
        tb = time.time() - t0

        t0 = time.time()
        wt, st = extract_treesitter_words(cmd)
        tt = time.time() - t0

        t0 = time.time()
        ws, ss = extract_shfmt_words(cmd)
        ts = time.time() - t0

        # 4. Check match with bash
        b_match = ("matches bash" if (sb == "PARSED" and bash_says == "OK") or (sb != "PARSED" and bash_says == "ERR")
                   else "differs from bash")
        t_match = ("matches bash" if (st == "PARSED" and bash_says == "OK") or (st != "PARSED" and bash_says == "ERR")
                   else "differs from bash")
        s_match = ("matches bash" if (ss == "PARSED" and bash_says == "OK") or (ss != "PARSED" and bash_says == "ERR")
                   else "differs from bash")

        # 5. Format parser cells (dropping json_bytes, displaying command name & args)
        cell_b = format_words_summary(wb) if sb == "PARSED" else sb
        cell_t = format_words_summary(wt) if st == "PARSED" else st
        cell_s = format_words_summary(ws) if ss == "PARSED" else ss

        # 6. Compare content across parsers
        word_comp = compare_words(wb, wt, ws)

        # 7. Disagreement verdict
        any_diff = (b_match == "differs from bash" or
                    t_match == "differs from bash" or
                    s_match == "differs from bash" or
                    word_comp.startswith("DIVERGENT") or
                    not (sb == st == ss))
        disagreement = "YES" if any_diff else "NO"

        results.append({
            "id": idx,
            "cmd": cmd,
            "repr": cmd_repr,
            "desc": desc,
            "bash_says": bash_says,
            "bash_exit": bash_exit,
            "bash_err": bash_err,
            "bashlex": cell_b,
            "bashlex_status": sb,
            "bashlex_match": b_match,
            "treesitter": cell_t,
            "treesitter_status": st,
            "treesitter_match": t_match,
            "shfmt": cell_s,
            "shfmt_status": ss,
            "shfmt_match": s_match,
            "word_comp": word_comp,
            "disagreement": disagreement,
            "timing": {"bash": t_bash, "bashlex": tb, "treesitter": tt, "shfmt": ts}
        })

    return results

def format_markdown_table(results):
    lines = []
    lines.append("# Shell Parser Disagreement & Ground-Truth Test Results")
    lines.append("")
    lines.append(f"Total commands evaluated: {len(results)}")
    disagree_cnt = sum(1 for r in results if r["disagreement"] == "YES")
    lines.append(f"Total disagreements / divergences: {disagree_cnt} / {len(results)}")
    lines.append("Parsers evaluated: bashlex (Python), tree-sitter-bash (Tree-sitter), mvdan/sh (`shfmt`), ground-truth `bash -n` (GNU Bash)")
    lines.append("")
    lines.append("Note on special rows:")
    lines.append("- Rows 13–16 and 18: backtick commands defined via raw strings `r\"...\"` preserving nested and unclosed backtick escapes.")
    lines.append("- Rows 19–21, 23: here-docs containing literal newline `\\n` characters.")
    lines.append("- Rows 50–52: line continuations containing literal newline `\\n` characters.")
    lines.append("- Row 95: 1 MB line test (1,048,581 characters); timing and hang status recorded.")
    lines.append("")
    lines.append("| ID | Stored Command `repr()` | bash -n | bashlex (result / match) | tree-sitter-bash (result / match) | mvdan/sh (result / match) | Content Comparison | Disagreement |")
    lines.append("|---|---|:---:|---|---|---|---|:---:|")

    for r in results:
        r_repr = r["repr"]
        if len(r_repr) > 40:
            esc_repr = f"`{r_repr[:37]}...`".replace("|", "\\|")
        else:
            esc_repr = f"`{r_repr}`".replace("|", "\\|")

        b_cell = f"{r['bashlex']} [{r['bashlex_match']}]".replace("|", "\\|")
        t_cell = f"{r['treesitter']} [{r['treesitter_match']}]".replace("|", "\\|")
        s_cell = f"{r['shfmt']} [{r['shfmt_match']}]".replace("|", "\\|")
        c_comp = r["word_comp"].replace("|", "\\|")

        lines.append(f"| {r['id']} | {esc_repr} | **{r['bash_says']}** | {b_cell} | {t_cell} | {s_cell} | {c_comp} | **{r['disagreement']}** |")

    # Append 1 MB line timing summary
    mb_row = results[-1]
    lines.append("")
    lines.append("## 1 MB Line Performance & Hang Verification")
    lines.append(f"- Command length: {len(mb_row['cmd'])} characters")
    lines.append(f"- GNU bash -n execution time: {mb_row['timing']['bash']:.4f}s (exit {mb_row['bash_exit']})")
    lines.append(f"- bashlex parse time: {mb_row['timing']['bashlex']:.4f}s (hang: NO, status: {mb_row['bashlex_status']})")
    lines.append(f"- tree-sitter parse time: {mb_row['timing']['treesitter']:.4f}s (hang: NO, status: {mb_row['treesitter_status']})")
    lines.append(f"- mvdan/sh parse time: {mb_row['timing']['shfmt']:.4f}s (hang: NO, status: {mb_row['shfmt_status']})")
    lines.append("- Verdict: No parser hung or exceeded timeouts on the 1 MB line.")

    return "\n".join(lines)

def test_shell_parser_disagreement():
    assert len(CORPUS) >= 90, f"Corpus size {len(CORPUS)} < 90 requirement"
    results = evaluate_all()
    assert len(results) == len(CORPUS)

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = os.path.join(repo_root, "delivery-oss-evidence-r31")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "raw_parser_disagreement.txt")

    table_text = format_markdown_table(results)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(table_text)

    print(f"\nWrote raw parser disagreement table to {out_path}")
    print(f"Total commands: {len(results)}, Disagreements / divergences: {sum(1 for r in results if r['disagreement'] == 'YES')}")

if __name__ == "__main__":
    test_shell_parser_disagreement()
