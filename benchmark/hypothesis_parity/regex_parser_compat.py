"""
S-Class EOS V11.2 - Standard Library Regex Parser Compatibility Layer.
Provides a portable, versioned AST parser interface across Python 3.10, 3.11, 3.12, 3.13, and 3.14.
Does not depend on or imitate Hypothesis internals.
"""

import sys
from typing import Any, List, Tuple

try:
    import re._parser as _sre_parser
except ImportError:
    import sre_parse as _sre_parser

# Canonical Opcode Constants
OP_LITERAL = _sre_parser.LITERAL
OP_NOT_LITERAL = getattr(_sre_parser, "NOT_LITERAL", None)
OP_RANGE = _sre_parser.RANGE
OP_IN = _sre_parser.IN
OP_BRANCH = _sre_parser.BRANCH
OP_SUBPATTERN = _sre_parser.SUBPATTERN
OP_MAX_REPEAT = _sre_parser.MAX_REPEAT
OP_MIN_REPEAT = _sre_parser.MIN_REPEAT
OP_ANY = _sre_parser.ANY
OP_AT = _sre_parser.AT
OP_CATEGORY = _sre_parser.CATEGORY
OP_NEGATE = getattr(_sre_parser, "NEGATE", None)
MAXREPEAT = _sre_parser.MAXREPEAT

# Anchor Types
AT_BEGINNING = getattr(_sre_parser, "AT_BEGINNING", "AT_BEGINNING")
AT_BEGINNING_STRING = getattr(_sre_parser, "AT_BEGINNING_STRING", "AT_BEGINNING_STRING")
AT_END = getattr(_sre_parser, "AT_END", "AT_END")
AT_END_STRING = getattr(_sre_parser, "AT_END_STRING", "AT_END_STRING")
AT_BOUNDARY = getattr(_sre_parser, "AT_BOUNDARY", "AT_BOUNDARY")
AT_NON_BOUNDARY = getattr(_sre_parser, "AT_NON_BOUNDARY", "AT_NON_BOUNDARY")


def parse_regex_ast(pattern: str, flags: int = 0) -> List[Tuple[Any, Any]]:
    """
    Parses a regular expression into a canonical list of (opcode, argument) tuples.
    Raises ValueError if the regular expression cannot be parsed.
    """
    try:
        parsed = _sre_parser.parse(pattern, flags=flags)
        return list(parsed)
    except Exception as err:
        raise ValueError(f"Failed to parse regular expression pattern '{pattern}': {err}") from err


def inspect_regex_anchors(ast_nodes: List[Tuple[Any, Any]]) -> Tuple[bool, bool, bool, bool]:
    """
    Inspects top-level AST nodes to determine anchor and boundary constraints.
    Returns (has_start_anchor, has_end_anchor, has_start_boundary, has_end_boundary).
    """
    has_start = False
    has_end = False
    has_start_boundary = False
    has_end_boundary = False

    if not ast_nodes:
        return False, False, False, False

    # Check first node
    first_op, first_av = ast_nodes[0]
    if first_op == OP_AT:
        av_str = str(first_av)
        if "BEGINNING" in av_str:
            has_start = True
        elif "BOUNDARY" in av_str and "NON" not in av_str:
            has_start_boundary = True

    # Check last node
    last_op, last_av = ast_nodes[-1]
    if last_op == OP_AT:
        av_str = str(last_av)
        if "END" in av_str:
            has_end = True
        elif "BOUNDARY" in av_str and "NON" not in av_str:
            has_end_boundary = True

    # Handle branch top-level
    if len(ast_nodes) == 1 and first_op == OP_BRANCH:
        _, branch_list = first_av
        branch_starts = []
        branch_ends = []
        branch_sb = []
        branch_eb = []
        for b in branch_list:
            b_s, b_e, b_sb, b_eb = inspect_regex_anchors(b)
            branch_starts.append(b_s)
            branch_ends.append(b_e)
            branch_sb.append(b_sb)
            branch_eb.append(b_eb)
        has_start = all(branch_starts) if branch_starts else False
        has_end = all(branch_ends) if branch_ends else False
        has_start_boundary = all(branch_sb) if branch_sb else False
        has_end_boundary = all(branch_eb) if branch_eb else False

    return has_start, has_end, has_start_boundary, has_end_boundary
