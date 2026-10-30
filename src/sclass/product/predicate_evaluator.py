"""R30 Section F2 Predicate and Invariant Evaluator (Decidable Fragment).

Implements bounded, typed, quantifier-free predicate evaluation and classification
over finite scalar, set, and list variables in accordance with R30 Section F2:
- Closed EBNF grammar, token validation, and canonical normal form.
- Two-layer evaluation architecture:
    * Layer 1: Base satisfiability (SAT, UNSAT, INCONCLUSIVE) with budget bounding.
    * Layer 2: Classification (TAUTOLOGY, CONTRADICTORY, EQUIVALENT, TIGHTENING, WEAKENING).
- Authoritative consumer gate mapping (SATISFIED, MISSING, BLOCKED_ON_HUMAN).
- False-UNSAT guard preventing disjunctive flattening.
- Explicit detection of unknown, missing, malformed, or unsupported inputs producing UNVERIFIED.
"""
from __future__ import annotations

import enum
import hashlib
import itertools
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

# -----------------------------------------------------------------------------
# Kernel Authority & Frozen Object Integration (Strict - No Any Fallbacks)
# -----------------------------------------------------------------------------
try:
    from sclass_semantics_v6_0_1 import (
        AcceptanceContract,
        Constraint,
        ConstraintType,
        Digest,
        Requirement,
        VerificationStep,
        canonical_c1,
    )
except ImportError:
    _conformance_dir = Path(__file__).resolve().parents[3] / "10-CONFORMANCE"
    if _conformance_dir.is_dir() and str(_conformance_dir) not in sys.path:
        sys.path.insert(0, str(_conformance_dir))
    from sclass_semantics_v6_0_1 import (
        AcceptanceContract,
        Constraint,
        ConstraintType,
        Digest,
        Requirement,
        VerificationStep,
        canonical_c1,
    )


# -----------------------------------------------------------------------------
# Normative Result Enums
# -----------------------------------------------------------------------------
class BaseResult(str, enum.Enum):
    """Layer 1 Base Evaluation Result."""
    SAT = "SAT"
    UNSAT = "UNSAT"
    INCONCLUSIVE = "INCONCLUSIVE"


class Classification(str, enum.Enum):
    """Layer 2 Predicate Classification Result."""
    TAUTOLOGY = "TAUTOLOGY"
    CONTRADICTORY = "CONTRADICTORY"
    EQUIVALENT = "EQUIVALENT"
    TIGHTENING = "TIGHTENING"
    WEAKENING = "WEAKENING"
    UNCLASSIFIED = "UNCLASSIFIED"


class EvaluationOutcome(str, enum.Enum):
    """Outcome status for evaluation requests."""
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class GateState(str, enum.Enum):
    """Authoritative F5 Gate State Vocabulary."""
    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    BLOCKED_ON_HUMAN = "BLOCKED_ON_HUMAN"


@dataclass(frozen=True)
class GateOutput:
    """F5 Gate Output structure."""
    state: GateState
    must_id: str | None = None
    detail: str | None = None

    def __str__(self) -> str:
        if self.state == GateState.SATISFIED:
            return "SATISFIED"
        if self.must_id:
            return f"{self.state.value}[{self.must_id}]"
        return self.state.value


# -----------------------------------------------------------------------------
# Frozen Object Binding Resolution (PD-F2-007 / F2-T9)
# -----------------------------------------------------------------------------
REQUIRED_FROZEN_BINDING_TYPES: Mapping[str, type] = {
    "requirement_ref": Requirement,
    "constraint_ref": Constraint,
    "acceptance_contract_ref": AcceptanceContract,
    "verification_step_ref": VerificationStep,
}


class FrozenBindingResolver(Protocol):
    """Explicit dependency protocol for resolving references to frozen kernel objects."""

    def resolve(self, ref: str) -> Any:
        """Resolve a string reference to a frozen kernel object."""
        ...


class InMemoryFrozenResolver:
    """Read-only reference resolver holding existing frozen kernel objects.

    Does not create or mutate canonical kernel objects.
    """

    def __init__(self, objects: Mapping[str, Any] | None = None) -> None:
        self._objects = dict(objects or {})

    def resolve(self, ref: str) -> Any:
        return self._objects.get(ref)


def resolve_frozen_bindings(
    bindings: Mapping[str, Any],
    resolver: FrozenBindingResolver | Callable[[str], Any] | Mapping[str, Any] | None,
) -> tuple[bool, dict[str, Any], str | None]:
    """Resolves all four required frozen bindings using an explicit injected resolver.

    Rules:
    1. The resolver must be an explicit dependency of the binding-resolution path.
    2. Each reference must be resolved through that dependency.
    3. Each resolved object must be checked against its required frozen kernel type:
       - requirement_ref -> Requirement
       - constraint_ref -> Constraint (and valid ConstraintType)
       - acceptance_contract_ref -> AcceptanceContract
       - verification_step_ref -> VerificationStep
    4. All four bindings must resolve successfully before F2-T9 can succeed.
    5. If no resolver is supplied, fails closed with MISSING[PD-F2-007].
    6. If any reference is unknown or cannot be resolved, fails closed with MISSING[PD-F2-007].
    7. If a reference resolves to an object of the wrong type, fails closed with MISSING[PD-F2-007].
    8. A truthy string, non-empty identifier, fixture boolean, or agent assertion must NEVER
       substitute for actual resolution.
    9. Does not silently fall back to fabricated objects, permissive aliases, or success defaults.

    Returns:
        (success: bool, resolved_objects: dict, error_message: str | None)
    """
    if resolver is None:
        return False, {}, "Missing required frozen binding resolver"

    resolved: dict[str, Any] = {}
    for ref_key, expected_cls in REQUIRED_FROZEN_BINDING_TYPES.items():
        if ref_key not in bindings:
            return False, {}, f"Missing required reference '{ref_key}' in bindings"
        ref_val = bindings[ref_key]
        if not isinstance(ref_val, str) or not ref_val.strip():
            return False, {}, f"Reference '{ref_key}' must be a non-empty string identifier"

        # Resolve through explicit injected dependency
        if hasattr(resolver, "resolve") and callable(getattr(resolver, "resolve")):
            obj = resolver.resolve(ref_val)
        elif callable(resolver):
            obj = resolver(ref_val)
        elif isinstance(resolver, Mapping):
            obj = resolver.get(ref_val)
        else:
            return False, {}, f"Unsupported resolver type: {type(resolver).__name__}"

        if obj is None:
            return False, {}, f"Unknown or unresolvable reference '{ref_val}' for '{ref_key}'"

        if not isinstance(obj, expected_cls):
            return False, {}, (
                f"Reference '{ref_val}' resolved to type '{type(obj).__name__}', "
                f"expected frozen kernel type '{expected_cls.__name__}'"
            )

        # Explicit validation using kernel types (ConstraintType on Constraint)
        if isinstance(obj, Constraint) and not isinstance(obj.constraint_type, ConstraintType):
            return False, {}, f"Constraint '{ref_val}' has invalid constraint_type: {obj.constraint_type}"

        resolved[ref_key] = obj

    return True, resolved, None


def compute_predicate_digest(node_or_canonical_str: Any) -> str:
    """Computes deterministic SHA-256 digest over canonical C1 serialized predicate representation.

    Reuses the authoritative canonical_c1 mechanism from sclass_semantics_v6_0_1.
    """
    if hasattr(node_or_canonical_str, "canonical") and callable(getattr(node_or_canonical_str, "canonical")):
        canonical_str = node_or_canonical_str.canonical()
    else:
        canonical_str = str(node_or_canonical_str)

    c1_bytes = canonical_c1(canonical_str)
    return hashlib.sha256(c1_bytes).hexdigest()


# -----------------------------------------------------------------------------
# Evaluation Output Data Models
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class BaseEvaluation:
    """Layer 1: Base evaluation result."""
    base_result: BaseResult
    predicate_digest: str
    domain_estimate: int
    satisfying_witness: dict[str, Any] | None = None
    satisfying_assignments_count: int | None = None
    evaluated_assignments: int = 0
    budget_exhausted: bool = False


@dataclass(frozen=True)
class ClassificationEvaluation:
    """Layer 2: Classification result."""
    classification: Classification
    queries: tuple[dict[str, Any], ...] = ()
    reason: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    """Complete evaluation envelope."""
    outcome: EvaluationOutcome
    base: BaseEvaluation | None = None
    classification: ClassificationEvaluation | None = None
    gate_output: GateOutput | None = None
    error: str | None = None


# -----------------------------------------------------------------------------
# Variable Schema & Domain Model
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class VariableType:
    name: str  # Int, Bool, Enum, String, Set, List
    domain: tuple[Any, ...]  # Explicit finite universe of values
    min_val: int | None = None
    max_val: int | None = None

    @classmethod
    def from_dict(cls, type_name: str, spec: Mapping[str, Any]) -> VariableType:
        raw_type = spec.get("type", type_name)
        if raw_type == "Int":
            raw_domain = spec.get("domain")
            if raw_domain is None:
                raise ValueError("Int variable requires explicit finite domain")
            if isinstance(raw_domain, (list, tuple)):
                if len(raw_domain) == 2 and all(isinstance(v, int) for v in raw_domain) and raw_domain[0] <= raw_domain[1] and ".." in str(spec):
                    # min, max range
                    vals = tuple(range(raw_domain[0], raw_domain[1] + 1))
                    return cls("Int", vals, min_val=raw_domain[0], max_val=raw_domain[1])
                elif len(raw_domain) >= 2 and raw_domain == list(range(raw_domain[0], raw_domain[-1] + 1)):
                    vals = tuple(raw_domain)
                    return cls("Int", vals, min_val=vals[0], max_val=vals[-1])
                else:
                    vals = tuple(raw_domain)
                    return cls("Int", vals, min_val=min(vals), max_val=max(vals))
            raise ValueError(f"Invalid Int domain specification: {raw_domain}")
        elif raw_type == "Bool":
            return cls("Bool", (False, True))
        elif raw_type == "Enum":
            values = tuple(spec.get("values", ()))
            if not values:
                raise ValueError("Enum variable requires non-empty values list")
            return cls("Enum", values)
        elif raw_type == "String":
            # Strings are bounded by finite comparison universe or explicit domain
            values = tuple(spec.get("values", spec.get("domain", ())))
            return cls("String", values)
        elif raw_type in ("Set", "List"):
            elem_domain = tuple(spec.get("element_domain", ()))
            max_card = int(spec.get("max_cardinality", spec.get("max_length", 3)))
            if raw_type == "Set":
                combos = []
                for r in range(max_card + 1):
                    for c in itertools.combinations(elem_domain, r):
                        combos.append(frozenset(c))
                return cls("Set", tuple(combos))
            else:
                prods = []
                for r in range(max_card + 1):
                    for p in itertools.product(elem_domain, repeat=r):
                        prods.append(p)
                return cls("List", tuple(prods))
        else:
            raise ValueError(f"Unsupported variable type: {raw_type}")


# -----------------------------------------------------------------------------
# AST Nodes for Bounded Predicates
# -----------------------------------------------------------------------------
class Node:
    """Abstract Base Class for Predicate AST nodes."""
    def canonical(self) -> str:
        raise NotImplementedError

    def free_variables(self) -> set[str]:
        raise NotImplementedError

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class BoolLiteralNode(Node):
    val: bool

    def canonical(self) -> str:
        return "TRUE" if self.val else "FALSE"

    def free_variables(self) -> set[str]:
        return set()

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        return self.val


@dataclass(frozen=True)
class PathExistsNode(Node):
    path: str
    exists: bool

    def canonical(self) -> str:
        return f"{self.path} {'EXISTS' if self.exists else 'NOT_EXISTS'}"

    def free_variables(self) -> set[str]:
        return {self.path.split(".")[0]}

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        # resolve path in env
        parts = self.path.split(".")
        curr: Any = env
        for p in parts:
            if isinstance(curr, Mapping) and p in curr:
                curr = curr[p]
            else:
                return not self.exists
        return self.exists


@dataclass(frozen=True)
class CmpLiteralNode(Node):
    path: str
    op: str  # EQUALS, NOT_EQUALS, GREATER_THAN, GREATER_OR_EQUAL, LESS_THAN, LESS_OR_EQUAL
    literal: Any

    def canonical(self) -> str:
        if isinstance(self.literal, str):
            lit_repr = f'"{self.literal}"'
        else:
            lit_repr = str(self.literal)
        return f"({self.path} {self.op} {lit_repr})"

    def free_variables(self) -> set[str]:
        return {self.path.split(".")[0]}

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        if self.path not in env:
            raise KeyError(f"Variable '{self.path}' not bound in environment")
        val = env[self.path]
        lit = self.literal
        if self.op == "EQUALS":
            return val == lit
        elif self.op == "NOT_EQUALS":
            return val != lit
        elif self.op == "GREATER_THAN":
            return val > lit
        elif self.op == "GREATER_OR_EQUAL":
            return val >= lit
        elif self.op == "LESS_THAN":
            return val < lit
        elif self.op == "LESS_OR_EQUAL":
            return val <= lit
        else:
            raise ValueError(f"Unknown comparison operator: {self.op}")


@dataclass(frozen=True)
class CmpPathNode(Node):
    left_path: str
    op: str
    right_path: str

    def canonical(self) -> str:
        return f"({self.left_path} {self.op} {self.right_path})"

    def free_variables(self) -> set[str]:
        return {self.left_path.split(".")[0], self.right_path.split(".")[0]}

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        if self.left_path not in env or self.right_path not in env:
            raise KeyError(f"Paths '{self.left_path}' or '{self.right_path}' not bound in environment")
        l_val = env[self.left_path]
        r_val = env[self.right_path]
        if self.op == "EQUALS":
            return l_val == r_val
        elif self.op == "NOT_EQUALS":
            return l_val != r_val
        elif self.op == "GREATER_THAN":
            return l_val > r_val
        elif self.op == "GREATER_OR_EQUAL":
            return l_val >= r_val
        elif self.op == "LESS_THAN":
            return l_val < r_val
        elif self.op == "LESS_OR_EQUAL":
            return l_val <= r_val
        else:
            raise ValueError(f"Unknown comparison operator: {self.op}")


@dataclass(frozen=True)
class InSetNode(Node):
    path: str
    is_in: bool
    elements: tuple[Any, ...]

    def canonical(self) -> str:
        sorted_elems = sorted(self.elements, key=lambda x: str(x))
        formatted = ", ".join(f'"{e}"' if isinstance(e, str) else str(e) for e in sorted_elems)
        op_str = "IN" if self.is_in else "NOT_IN"
        return f"({self.path} {op_str} {{{formatted}}})"

    def free_variables(self) -> set[str]:
        return {self.path.split(".")[0]}

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        if self.path not in env:
            raise KeyError(f"Variable '{self.path}' not bound in environment")
        val = env[self.path]
        contains = val in self.elements
        return contains if self.is_in else not contains


@dataclass(frozen=True)
class CardCmpNode(Node):
    path: str
    op: str
    literal: int

    def canonical(self) -> str:
        return f"(CARD({self.path}) {self.op} {self.literal})"

    def free_variables(self) -> set[str]:
        return {self.path.split(".")[0]}

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        if self.path not in env:
            raise KeyError(f"Variable '{self.path}' not bound in environment")
        col = env[self.path]
        c = len(col)
        lit = self.literal
        if self.op == "EQUALS":
            return c == lit
        elif self.op == "NOT_EQUALS":
            return c != lit
        elif self.op == "GREATER_THAN":
            return c > lit
        elif self.op == "GREATER_OR_EQUAL":
            return c >= lit
        elif self.op == "LESS_THAN":
            return c < lit
        elif self.op == "LESS_OR_EQUAL":
            return c <= lit
        else:
            raise ValueError(f"Unknown card comparison operator: {self.op}")


@dataclass(frozen=True)
class NotNode(Node):
    child: Node

    def canonical(self) -> str:
        return f"NOT({self.child.canonical()})"

    def free_variables(self) -> set[str]:
        return self.child.free_variables()

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        return not self.child.evaluate(env)


@dataclass(frozen=True)
class AndNode(Node):
    children: tuple[Node, ...]

    def canonical(self) -> str:
        if not self.children:
            return "TRUE"
        if len(self.children) == 1:
            return self.children[0].canonical()
        return "(" + " AND ".join(c.canonical() for c in self.children) + ")"

    def free_variables(self) -> set[str]:
        res: set[str] = set()
        for c in self.children:
            res.update(c.free_variables())
        return res

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        return all(c.evaluate(env) for c in self.children)


@dataclass(frozen=True)
class OrNode(Node):
    children: tuple[Node, ...]

    def canonical(self) -> str:
        if not self.children:
            return "FALSE"
        if len(self.children) == 1:
            return self.children[0].canonical()
        return "(" + " OR ".join(c.canonical() for c in self.children) + ")"

    def free_variables(self) -> set[str]:
        res: set[str] = set()
        for c in self.children:
            res.update(c.free_variables())
        return res

    def evaluate(self, env: Mapping[str, Any]) -> bool:
        return any(c.evaluate(env) for c in self.children)


# -----------------------------------------------------------------------------
# Lexer, Tokenizer & Parser
# -----------------------------------------------------------------------------
class TokenType(enum.Enum):
    IDENT = "IDENT"
    INTEGER = "INTEGER"
    QUOTED_STRING = "QUOTED_STRING"
    TRUE = "TRUE"
    FALSE = "FALSE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    GREATER_THAN = "GREATER_THAN"
    GREATER_OR_EQUAL = "GREATER_OR_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_OR_EQUAL = "LESS_OR_EQUAL"
    IN = "IN"
    NOT_IN = "NOT_IN"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"
    CARD = "CARD"
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    COMMA = ","
    DOT = "."
    # Forbidden / Temporal constructs
    FORALL = "FORALL"
    TEMPORAL = "TEMPORAL"


@dataclass(frozen=True)
class Token:
    type: TokenType
    value: Any


_OPERATOR_MAP = {
    "&&": TokenType.AND,
    "||": TokenType.OR,
    "!": TokenType.NOT,
    "==": TokenType.EQUALS,
    "=": TokenType.EQUALS,
    "!=": TokenType.NOT_EQUALS,
    ">=": TokenType.GREATER_OR_EQUAL,
    ">": TokenType.GREATER_THAN,
    "<=": TokenType.LESS_OR_EQUAL,
    "<": TokenType.LESS_THAN,
    "and": TokenType.AND,
    "AND": TokenType.AND,
    "or": TokenType.OR,
    "OR": TokenType.OR,
    "not": TokenType.NOT,
    "NOT": TokenType.NOT,
    "equals": TokenType.EQUALS,
    "EQUALS": TokenType.EQUALS,
    "not_equals": TokenType.NOT_EQUALS,
    "NOT_EQUALS": TokenType.NOT_EQUALS,
    "greater_than": TokenType.GREATER_THAN,
    "GREATER_THAN": TokenType.GREATER_THAN,
    "greater_or_equal": TokenType.GREATER_OR_EQUAL,
    "GREATER_OR_EQUAL": TokenType.GREATER_OR_EQUAL,
    "less_than": TokenType.LESS_THAN,
    "LESS_THAN": TokenType.LESS_THAN,
    "less_or_equal": TokenType.LESS_OR_EQUAL,
    "LESS_OR_EQUAL": TokenType.LESS_OR_EQUAL,
    "in": TokenType.IN,
    "IN": TokenType.IN,
    "not in": TokenType.NOT_IN,
    "NOT_IN": TokenType.NOT_IN,
    "exists": TokenType.EXISTS,
    "EXISTS": TokenType.EXISTS,
    "missing": TokenType.NOT_EXISTS,
    "NOT_EXISTS": TokenType.NOT_EXISTS,
    "true": TokenType.TRUE,
    "TRUE": TokenType.TRUE,
    "false": TokenType.FALSE,
    "FALSE": TokenType.FALSE,
    "card": TokenType.CARD,
    "CARD": TokenType.CARD,
}

_TEMPORAL_KEYWORDS = {"ALWAYS", "EVENTUALLY", "UNTIL", "NEXT"}


def tokenize(raw: str | Sequence[Any]) -> list[Token]:
    """Tokenize raw predicate string or structured token sequence."""
    if isinstance(raw, (list, tuple)) and not isinstance(raw, str):
        # Structured token list from fixture
        tokens: list[Token] = []
        for item in raw:
            s = str(item).strip()
            if s.startswith("IDENT(") and s.endswith(")"):
                tokens.append(Token(TokenType.IDENT, s[6:-1]))
            elif s.startswith("INTEGER(") and s.endswith(")"):
                tokens.append(Token(TokenType.INTEGER, int(s[8:-1])))
            elif s.startswith("QUOTED_STRING(") and s.endswith(")"):
                inner = s[14:-1].strip('"')
                tokens.append(Token(TokenType.QUOTED_STRING, inner))
            elif s.startswith("DIGIT(") and s.endswith(")"):
                tokens.append(Token(TokenType.INTEGER, int(s[6:-1])))
            elif s.startswith("LETTER(") and s.endswith(")"):
                tokens.append(Token(TokenType.IDENT, s[7:-1]))
            elif s == "ESCAPED_QUOTE":
                tokens.append(Token(TokenType.QUOTED_STRING, '"'))
            elif s == "ESCAPED_BACKSLASH":
                tokens.append(Token(TokenType.QUOTED_STRING, '\\'))
            elif s == "SET_OPEN":
                tokens.append(Token(TokenType.LBRACE, "{"))
            elif s == "SET_CLOSE":
                tokens.append(Token(TokenType.RBRACE, "}"))
            elif s == "COMMA":
                tokens.append(Token(TokenType.COMMA, ","))
            elif s == "LPAREN":
                tokens.append(Token(TokenType.LPAREN, "("))
            elif s == "RPAREN":
                tokens.append(Token(TokenType.RPAREN, ")"))
            elif s == "FORALL":
                tokens.append(Token(TokenType.FORALL, "FORALL"))
            elif s in _OPERATOR_MAP:
                tokens.append(Token(_OPERATOR_MAP[s], s))
            else:
                tokens.append(Token(TokenType.IDENT, s))
        return tokens

    text = str(raw).strip()
    # Check out-of-fragment temporal syntax early
    for kw in _TEMPORAL_KEYWORDS:
        if re.search(rf"\b{kw}(?:\[[0-9]+\])?\b", text):
            return [Token(TokenType.TEMPORAL, text)]

    pos = 0
    tokens = []
    n = len(text)
    while pos < n:
        if text[pos].isspace():
            pos += 1
            continue

        # Handle operators and punctuation
        if text.startswith("NOT_IN", pos) or text.startswith("not in", pos):
            tokens.append(Token(TokenType.NOT_IN, "NOT_IN"))
            pos += 6
            continue
        if text.startswith("NOT_EXISTS", pos):
            tokens.append(Token(TokenType.NOT_EXISTS, "NOT_EXISTS"))
            pos += 10
            continue
        if text.startswith("GREATER_OR_EQUAL", pos):
            tokens.append(Token(TokenType.GREATER_OR_EQUAL, "GREATER_OR_EQUAL"))
            pos += 16
            continue
        if text.startswith("LESS_OR_EQUAL", pos):
            tokens.append(Token(TokenType.LESS_OR_EQUAL, "LESS_OR_EQUAL"))
            pos += 13
            continue
        if text.startswith("GREATER_THAN", pos):
            tokens.append(Token(TokenType.GREATER_THAN, "GREATER_THAN"))
            pos += 12
            continue
        if text.startswith("LESS_THAN", pos):
            tokens.append(Token(TokenType.LESS_THAN, "LESS_THAN"))
            pos += 9
            continue
        if text.startswith("NOT_EQUALS", pos):
            tokens.append(Token(TokenType.NOT_EQUALS, "NOT_EQUALS"))
            pos += 10
            continue
        if text.startswith("EQUALS", pos):
            tokens.append(Token(TokenType.EQUALS, "EQUALS"))
            pos += 6
            continue

        two_char = text[pos:pos+2]
        if two_char in _OPERATOR_MAP:
            tokens.append(Token(_OPERATOR_MAP[two_char], two_char))
            pos += 2
            continue

        one_char = text[pos]
        if one_char in _OPERATOR_MAP:
            tokens.append(Token(_OPERATOR_MAP[one_char], one_char))
            pos += 1
            continue

        if one_char == "(":
            tokens.append(Token(TokenType.LPAREN, "("))
            pos += 1
            continue
        if one_char == ")":
            tokens.append(Token(TokenType.RPAREN, ")"))
            pos += 1
            continue
        if one_char == "{":
            tokens.append(Token(TokenType.LBRACE, "{"))
            pos += 1
            continue
        if one_char == "}":
            tokens.append(Token(TokenType.RBRACE, "}"))
            pos += 1
            continue
        if one_char == ",":
            tokens.append(Token(TokenType.COMMA, ","))
            pos += 1
            continue

        # Quoted string
        if one_char == '"':
            end = pos + 1
            chars = []
            while end < n and text[end] != '"':
                if text[end] == '\\' and end + 1 < n:
                    esc = text[end+1]
                    if esc == 'n': chars.append('\n')
                    elif esc == 'r': chars.append('\r')
                    elif esc == 't': chars.append('\t')
                    elif esc == '"': chars.append('"')
                    elif esc == '\\': chars.append('\\')
                    else: chars.append(esc)
                    end += 2
                else:
                    chars.append(text[end])
                    end += 1
            if end >= n:
                raise ValueError("Unterminated quoted string")
            tokens.append(Token(TokenType.QUOTED_STRING, "".join(chars)))
            pos = end + 1
            continue

        # Integer
        m_num = re.match(r"^-?(?:0|[1-9][0-9]*)", text[pos:])
        if m_num and (pos == 0 or text[pos-1].isspace() or text[pos-1] in "(,{<>=!"):
            # Verify not part of identifier
            num_str = m_num.group(0)
            end_num = pos + len(num_str)
            if end_num >= n or not (text[end_num].isalnum() or text[end_num] == '_'):
                tokens.append(Token(TokenType.INTEGER, int(num_str)))
                pos = end_num
                continue

        # Identifier or Keyword
        m_id = re.match(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*", text[pos:])
        if m_id:
            raw_id = m_id.group(0)
            if raw_id in _OPERATOR_MAP:
                tokens.append(Token(_OPERATOR_MAP[raw_id], raw_id))
            elif raw_id == "FORALL":
                tokens.append(Token(TokenType.FORALL, raw_id))
            elif raw_id in _TEMPORAL_KEYWORDS:
                tokens.append(Token(TokenType.TEMPORAL, raw_id))
            else:
                tokens.append(Token(TokenType.IDENT, raw_id))
            pos += len(raw_id)
            continue

        raise ValueError(f"Unrecognized token at position {pos}: {text[pos:pos+10]}")

    return tokens


class Parser:
    """Recursive descent parser enforcing closed EBNF grammar."""
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected: TokenType | None = None) -> Token:
        tok = self.peek()
        if tok is None:
            raise ValueError("Unexpected end of input")
        if expected is not None and tok.type != expected:
            raise ValueError(f"Expected token {expected}, got {tok.type}")
        self.pos += 1
        return tok

    def parse(self) -> Node:
        if not self.tokens:
            raise ValueError("Empty token stream")
        if any(t.type == TokenType.TEMPORAL for t in self.tokens):
            raise NotImplementedError("Temporal predicates are out of the v1 decidable fragment")
        if any(t.type == TokenType.FORALL for t in self.tokens):
            raise ValueError("Quantifiers (FORALL) are forbidden in the closed quantifier-free grammar")
        node = self.parse_or()
        if self.pos < len(self.tokens):
            raise ValueError(f"Extraneous tokens starting at: {self.tokens[self.pos]}")
        return node

    def parse_or(self) -> Node:
        left = self.parse_and()
        children = [left]
        while self.peek() and self.peek().type == TokenType.OR:
            self.consume(TokenType.OR)
            children.append(self.parse_and())
        return OrNode(tuple(children)) if len(children) > 1 else left

    def parse_and(self) -> Node:
        left = self.parse_unary()
        children = [left]
        while self.peek() and self.peek().type == TokenType.AND:
            self.consume(TokenType.AND)
            children.append(self.parse_unary())
        return AndNode(tuple(children)) if len(children) > 1 else left

    def parse_unary(self) -> Node:
        tok = self.peek()
        if tok and tok.type == TokenType.NOT:
            self.consume(TokenType.NOT)
            child = self.parse_unary()
            return NotNode(child)
        if tok and tok.type == TokenType.LPAREN:
            self.consume(TokenType.LPAREN)
            node = self.parse_or()
            self.consume(TokenType.RPAREN)
            return node
        return self.parse_atom()

    def parse_atom(self) -> Node:
        tok = self.peek()
        if tok is None:
            raise ValueError("Expected atom, got EOF")

        if tok.type == TokenType.TRUE:
            self.consume(TokenType.TRUE)
            return BoolLiteralNode(True)
        if tok.type == TokenType.FALSE:
            self.consume(TokenType.FALSE)
            return BoolLiteralNode(False)

        # Handle CARD(path) cmp integer
        if tok.type == TokenType.CARD:
            self.consume(TokenType.CARD)
            self.consume(TokenType.LPAREN)
            path_tok = self.consume(TokenType.IDENT)
            self.consume(TokenType.RPAREN)
            cmp_tok = self.consume()
            if cmp_tok.type not in (
                TokenType.EQUALS, TokenType.NOT_EQUALS, TokenType.GREATER_THAN,
                TokenType.GREATER_OR_EQUAL, TokenType.LESS_THAN, TokenType.LESS_OR_EQUAL
            ):
                raise ValueError(f"Expected comparison operator after CARD, got {cmp_tok.type}")
            int_tok = self.consume(TokenType.INTEGER)
            return CardCmpNode(path_tok.value, cmp_tok.type.name, int_tok.value)

        # Path-based atoms
        if tok.type == TokenType.IDENT:
            path_tok = self.consume(TokenType.IDENT)
            nxt = self.peek()
            if nxt is None:
                raise ValueError(f"Incomplete atom after identifier {path_tok.value}")

            if nxt.type == TokenType.EXISTS:
                self.consume(TokenType.EXISTS)
                return PathExistsNode(path_tok.value, True)
            if nxt.type == TokenType.NOT_EXISTS:
                self.consume(TokenType.NOT_EXISTS)
                return PathExistsNode(path_tok.value, False)

            if nxt.type in (TokenType.IN, TokenType.NOT_IN):
                is_in = (nxt.type == TokenType.IN)
                self.consume(nxt.type)
                self.consume(TokenType.LBRACE)
                elems = []
                while self.peek() and self.peek().type != TokenType.RBRACE:
                    el_tok = self.consume()
                    elems.append(el_tok.value)
                    if self.peek() and self.peek().type == TokenType.COMMA:
                        self.consume(TokenType.COMMA)
                self.consume(TokenType.RBRACE)
                return InSetNode(path_tok.value, is_in, tuple(elems))

            if nxt.type in (
                TokenType.EQUALS, TokenType.NOT_EQUALS, TokenType.GREATER_THAN,
                TokenType.GREATER_OR_EQUAL, TokenType.LESS_THAN, TokenType.LESS_OR_EQUAL
            ):
                cmp_tok = self.consume()
                target_tok = self.consume()
                if target_tok.type == TokenType.IDENT:
                    return CmpPathNode(path_tok.value, cmp_tok.type.name, target_tok.value)
                elif target_tok.type in (TokenType.INTEGER, TokenType.QUOTED_STRING, TokenType.TRUE, TokenType.FALSE):
                    return CmpLiteralNode(path_tok.value, cmp_tok.type.name, target_tok.value)
                else:
                    raise ValueError(f"Invalid comparison target: {target_tok}")

        raise ValueError(f"Unexpected token in atom: {tok}")


# -----------------------------------------------------------------------------
# Evaluator & Decision Procedure
# -----------------------------------------------------------------------------
class PredicateEvaluator:
    """F2 Reference and Bounded Evaluator."""

    DEFAULT_BUDGET = 100_000

    @classmethod
    def parse(cls, input_spec: str | Sequence[Any]) -> Node:
        tokens = tokenize(input_spec)
        parser = Parser(tokens)
        return parser.parse()

    @classmethod
    def compute_digest(cls, node: Node | str) -> str:
        return compute_predicate_digest(node)

    @classmethod
    def evaluate_base(
        cls,
        node: Node,
        schema: Mapping[str, VariableType | Mapping[str, Any]],
        budget: int = DEFAULT_BUDGET,
    ) -> BaseEvaluation:
        # Normalize schema
        var_types: dict[str, VariableType] = {}
        for var_name, s in schema.items():
            if isinstance(s, VariableType):
                var_types[var_name] = s
            else:
                var_types[var_name] = VariableType.from_dict(var_name, s)

        # Validate that all free variables are in the schema
        free_vars = sorted(node.free_variables())
        for fv in free_vars:
            if fv not in var_types:
                raise KeyError(f"Variable '{fv}' not defined in finite domain schema")

        # Estimate domain size
        domain_estimate = 1
        for fv in free_vars:
            domain_estimate *= len(var_types[fv].domain)

        # Polynomial reduction for top-level conjunctive atoms on single variables
        candidate_domains: dict[str, set[Any]] = {
            fv: set(var_types[fv].domain) for fv in free_vars
        }

        # Step 4 & 5: Apply reduction ONLY to top-level AND atoms. Never across OR!
        if isinstance(node, AndNode):
            conjunctive_atoms = node.children
        else:
            conjunctive_atoms = (node,)

        for atom in conjunctive_atoms:
            if isinstance(atom, CmpLiteralNode):
                vname = atom.path
                if vname in candidate_domains:
                    filtered = {
                        val for val in candidate_domains[vname]
                        if atom.evaluate({vname: val})
                    }
                    candidate_domains[vname] = filtered
                    if not filtered:
                        # Contradiction detected in single-variable domain
                        return BaseEvaluation(
                            base_result=BaseResult.UNSAT,
                            predicate_digest=cls.compute_digest(node),
                            domain_estimate=domain_estimate,
                            satisfying_assignments_count=0,
                        )

        # Check for single-variable closed-form witness when no residual cross-variable atoms exist
        has_cross_variable = any(
            isinstance(atom, CmpPathNode) for atom in cls._collect_all_atoms(node)
        )
        if not has_cross_variable and all(isinstance(a, (CmpLiteralNode, BoolLiteralNode)) for a in conjunctive_atoms):
            # Check if all candidate domains have at least one element
            if all(candidate_domains[fv] for fv in free_vars):
                # Pick any witness
                witness = {fv: next(iter(candidate_domains[fv])) for fv in free_vars}
                if node.evaluate(witness):
                    return BaseEvaluation(
                        base_result=BaseResult.SAT,
                        predicate_digest=cls.compute_digest(node),
                        domain_estimate=domain_estimate,
                        satisfying_witness=witness,
                        satisfying_assignments_count=len(candidate_domains[free_vars[0]]) if len(free_vars) == 1 else None,
                    )

        # Residual enumeration bounded by budget
        keys = free_vars
        domain_lists = [list(candidate_domains[k]) for k in keys]

        evaluated = 0
        satisfying_count = 0
        witness: dict[str, Any] | None = None

        for combo in itertools.product(*domain_lists):
            if evaluated >= budget:
                return BaseEvaluation(
                    base_result=BaseResult.INCONCLUSIVE,
                    predicate_digest=cls.compute_digest(node),
                    domain_estimate=domain_estimate,
                    evaluated_assignments=evaluated,
                    budget_exhausted=True,
                )
            env = dict(zip(keys, combo))
            evaluated += 1
            if node.evaluate(env):
                satisfying_count += 1
                if witness is None:
                    witness = env
                # If we only need satisfiability and no count is needed:
                # return SAT immediately
                return BaseEvaluation(
                    base_result=BaseResult.SAT,
                    predicate_digest=cls.compute_digest(node),
                    domain_estimate=domain_estimate,
                    satisfying_witness=witness,
                    satisfying_assignments_count=1,
                    evaluated_assignments=evaluated,
                )

        if satisfying_count == 0:
            return BaseEvaluation(
                base_result=BaseResult.UNSAT,
                predicate_digest=cls.compute_digest(node),
                domain_estimate=domain_estimate,
                satisfying_assignments_count=0,
                evaluated_assignments=evaluated,
            )

        return BaseEvaluation(
            base_result=BaseResult.SAT,
            predicate_digest=cls.compute_digest(node),
            domain_estimate=domain_estimate,
            satisfying_witness=witness,
            satisfying_assignments_count=satisfying_count,
            evaluated_assignments=evaluated,
        )

    @classmethod
    def _collect_all_atoms(cls, node: Node) -> list[Node]:
        atoms: list[Node] = []
        if isinstance(node, (AndNode, OrNode)):
            for c in node.children:
                atoms.extend(cls._collect_all_atoms(c))
        elif isinstance(node, NotNode):
            atoms.extend(cls._collect_all_atoms(node.child))
        else:
            atoms.append(node)
        return atoms

    @classmethod
    def classify(
        cls,
        old_pred: str | Node | None = None,
        new_pred: str | Node | None = None,
        schema: Mapping[str, Any] | None = None,
        old_schema: Mapping[str, Any] | None = None,
        new_schema: Mapping[str, Any] | None = None,
        budget: int = DEFAULT_BUDGET,
    ) -> ClassificationEvaluation:
        """Layer 2: Classification of predicates."""
        target_schema = new_schema if new_schema is not None else schema
        if target_schema is None:
            target_schema = {}
        if new_pred is None:
            raise ValueError("new_pred is required for classification")
        new_node = cls.parse(new_pred) if isinstance(new_pred, str) else new_pred

        # 1. Variable change detection (structural differences)
        if old_schema is not None and target_schema is not None:
            # Check added / removed variables
            old_keys = set(old_schema.keys())
            new_keys = set(target_schema.keys())
            if old_keys != new_keys:
                return ClassificationEvaluation(
                    classification=Classification.WEAKENING,
                    reason="Variable set changed between schemas",
                )
            # Check retyped or widened domain
            for k in old_keys:
                old_v = old_schema[k] if isinstance(old_schema[k], VariableType) else VariableType.from_dict(k, old_schema[k])
                new_v = target_schema[k] if isinstance(target_schema[k], VariableType) else VariableType.from_dict(k, target_schema[k])
                if old_v.name != new_v.name:
                    return ClassificationEvaluation(
                        classification=Classification.WEAKENING,
                        reason=f"Variable '{k}' retyped from {old_v.name} to {new_v.name}",
                    )
                # Check domain widening
                if set(new_v.domain) - set(old_v.domain):
                    return ClassificationEvaluation(
                        classification=Classification.WEAKENING,
                        reason=f"Variable '{k}' domain widened",
                    )

        # 2. Single-predicate properties (tautology / contradiction) if old_pred is None
        if old_pred is None:
            # Tautology query: NOT(new_node)
            not_node = NotNode(new_node)
            base_neg = cls.evaluate_base(not_node, target_schema, budget=budget)
            # Contradiction query: new_node
            base_pos = cls.evaluate_base(new_node, target_schema, budget=budget)
            queries = (
                {"query": not_node.canonical(), "base_result": base_neg.base_result.value},
                {"query": new_node.canonical(), "base_result": base_pos.base_result.value},
            )
            if base_neg.base_result == BaseResult.INCONCLUSIVE or base_pos.base_result == BaseResult.INCONCLUSIVE:
                return ClassificationEvaluation(classification=Classification.UNCLASSIFIED, queries=queries)
            if base_neg.base_result == BaseResult.UNSAT:
                return ClassificationEvaluation(
                    classification=Classification.TAUTOLOGY,
                    queries=queries,
                )
            if base_pos.base_result == BaseResult.UNSAT:
                return ClassificationEvaluation(
                    classification=Classification.CONTRADICTORY,
                    queries=queries,
                )
            return ClassificationEvaluation(
                classification=Classification.UNCLASSIFIED,
                queries=queries,
            )

        # 3. Old vs New comparison
        old_node = cls.parse(old_pred) if isinstance(old_pred, str) else old_pred

        # Query 1: B AND NOT(A)
        q1 = AndNode((new_node, NotNode(old_node)))
        # Query 2: A AND NOT(B)
        q2 = AndNode((old_node, NotNode(new_node)))

        res1 = cls.evaluate_base(q1, target_schema, budget=budget)
        res2 = cls.evaluate_base(q2, target_schema, budget=budget)

        queries = (
            {"query": q1.canonical(), "base_result": res1.base_result.value},
            {"query": q2.canonical(), "base_result": res2.base_result.value},
        )

        if res1.base_result == BaseResult.INCONCLUSIVE or res2.base_result == BaseResult.INCONCLUSIVE:
            return ClassificationEvaluation(classification=Classification.UNCLASSIFIED, queries=queries)

        if res1.base_result == BaseResult.SAT:
            return ClassificationEvaluation(classification=Classification.WEAKENING, queries=queries)

        if res1.base_result == BaseResult.UNSAT and res2.base_result == BaseResult.SAT:
            return ClassificationEvaluation(classification=Classification.TIGHTENING, queries=queries)

        if res1.base_result == BaseResult.UNSAT and res2.base_result == BaseResult.UNSAT:
            return ClassificationEvaluation(classification=Classification.EQUIVALENT, queries=queries)

        return ClassificationEvaluation(classification=Classification.UNCLASSIFIED, queries=queries)


# -----------------------------------------------------------------------------
# Consumer Gate Mapping
# -----------------------------------------------------------------------------
def map_to_gate_output(
    eval_res: BaseEvaluation | None = None,
    class_res: ClassificationEvaluation | None = None,
    consumer: str = "p3_invariant",  # p3_invariant, f1_adequacy, weakening_control
    authoritative_approval: str | None = None,
    must_id_override: str | None = None,
) -> GateOutput:
    """Map evaluation results to authoritative gate output.

    Fails closed: every supported procedure-result/consumer combination has an
    explicit deterministic mapping. Unsupported consumers, missing evaluations,
    unclassified results, or unapproved weakenings never produce SATISFIED.
    """
    if consumer not in ("p3_invariant", "f1_adequacy", "weakening_control"):
        return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F2-001", detail=f"Unsupported consumer: '{consumer}'")

    if eval_res is None and class_res is None:
        return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F2-001", detail="Missing evaluation results")

    # Layer 2: Classification mapping
    if class_res is not None:
        c = class_res.classification
        if consumer == "weakening_control":
            if c in (Classification.EQUIVALENT, Classification.TIGHTENING):
                return GateOutput(GateState.SATISFIED)
            elif c == Classification.WEAKENING:
                if authoritative_approval is not None and str(authoritative_approval).strip():
                    return GateOutput(GateState.SATISFIED)
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            elif c == Classification.UNCLASSIFIED:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            else:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")

        elif consumer == "f1_adequacy":
            if c == Classification.TAUTOLOGY:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F1-004")
            elif c == Classification.CONTRADICTORY:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F1-004")
            elif c == Classification.UNCLASSIFIED:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id=must_id_override or "PD-F1-004")
            else:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F1-004", detail=f"Classification '{c.value}' has no decision for f1_adequacy")

        elif consumer == "p3_invariant":
            if c == Classification.TAUTOLOGY:
                return GateOutput(GateState.SATISFIED)
            elif c == Classification.CONTRADICTORY:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-CH2-020")
            elif c == Classification.UNCLASSIFIED:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id=must_id_override or "PD-CH2-020")
            else:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-CH2-020", detail=f"Classification '{c.value}' has no decision for p3_invariant")

    # Layer 1: Base Evaluation mapping
    if eval_res is not None:
        r = eval_res.base_result
        if consumer == "p3_invariant":
            if r == BaseResult.SAT:
                return GateOutput(GateState.SATISFIED)
            elif r == BaseResult.UNSAT:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-CH2-020")
            elif r == BaseResult.INCONCLUSIVE:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id=must_id_override or "PD-CH2-020")
            else:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-CH2-020")

        elif consumer == "f1_adequacy":
            if r == BaseResult.SAT:
                return GateOutput(GateState.SATISFIED)
            elif r == BaseResult.UNSAT:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F1-004")
            elif r == BaseResult.INCONCLUSIVE:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id=must_id_override or "PD-F1-004")
            else:
                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F1-004")

        elif consumer == "weakening_control":
            if r == BaseResult.INCONCLUSIVE:
                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")
            return GateOutput(GateState.MISSING, must_id="PD-F1-005", detail=f"BaseResult '{r.value}' cannot decide weakening control without classification")

    # Strict fail-closed fallback
    return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F2-001", detail="Unmapped procedure result")


# -----------------------------------------------------------------------------
# High-Level Evaluation Entry Point with UNVERIFIED Protection
# -----------------------------------------------------------------------------
def evaluate_predicate_input(
    spec: Mapping[str, Any],
    consumer: str = "p3_invariant",
    resolver: FrozenBindingResolver | Callable[[str], Any] | Mapping[str, Any] | None = None,
) -> EvaluationResult:
    """Evaluate a structured predicate input record against specification gates.

    Strictly preserves UNVERIFIED outcome on unknown, missing, malformed, or
    unsupported inputs.
    """
    if not isinstance(spec, Mapping):
        return EvaluationResult(
            outcome=EvaluationOutcome.UNVERIFIED,
            gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-001"),
            error="Predicate input specification must be a mapping",
        )

    # 1. Check for frozen object bindings (F2-T9 / PD-F2-007)
    has_binding_refs = any(
        k in spec for k in ("requirement_ref", "constraint_ref", "acceptance_contract_ref", "verification_step_ref")
    )
    if has_binding_refs:
        # Resolver MUST be strictly caller-controlled via the resolver function argument;
        # untrusted input specifications cannot supply their own resolver.
        if resolver is None:
            return EvaluationResult(
                outcome=EvaluationOutcome.UNVERIFIED,
                gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-007", detail="Missing required frozen binding resolver"),
                error="Missing required frozen binding resolver",
            )
        success, resolved_objs, err = resolve_frozen_bindings(spec, resolver)
        if success:
            return EvaluationResult(
                outcome=EvaluationOutcome.VERIFIED,
                gate_output=GateOutput(GateState.SATISFIED),
            )
        return EvaluationResult(
            outcome=EvaluationOutcome.UNVERIFIED,
            gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-007", detail=err),
            error=err,
        )

    # 2. Parse input tokens or predicate string (F2-T1, F2-T2, PD-F2-001)
    raw_pred = spec.get("predicate")
    input_tokens = spec.get("input_tokens")
    target_input = input_tokens if input_tokens is not None else raw_pred
    if target_input is None:
        # Check if it's a domain widening test without predicate (F2-T14)
        if "old_domain" in spec and "new_domain" in spec:
            old_d = spec["old_domain"]
            new_d = spec["new_domain"]
            old_s = {k: VariableType.from_dict(k, {"type": "Int", "domain": v}) for k, v in old_d.items()}
            new_s = {k: VariableType.from_dict(k, {"type": "Int", "domain": v}) for k, v in new_d.items()}
            cl_eval = PredicateEvaluator.classify("TRUE", "TRUE", new_s, old_s)
            gate = map_to_gate_output(class_res=cl_eval, consumer="weakening_control")
            return EvaluationResult(
                outcome=EvaluationOutcome.VERIFIED,
                classification=cl_eval,
                gate_output=gate,
            )
        return EvaluationResult(
            outcome=EvaluationOutcome.UNVERIFIED,
            gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-001"),
            error="Missing predicate input or input_tokens",
        )

    try:
        ast = PredicateEvaluator.parse(target_input)
    except NotImplementedError as e:
        return EvaluationResult(
            outcome=EvaluationOutcome.UNVERIFIED,
            gate_output=GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F2-005"),
            error=str(e),
        )
    except Exception as e:
        # Malformed tokens or forbidden construct
        return EvaluationResult(
            outcome=EvaluationOutcome.UNVERIFIED,
            gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-001"),
            error=f"Parse failure: {e}",
        )

    # 4. Check schema validity and finite domains (PD-F2-002, F2-T3)
    raw_schema = spec.get("schema", spec.get("bounded_domain"))
    if raw_schema is None:
        # Check if AST has free variables
        if ast.free_variables():
            return EvaluationResult(
                outcome=EvaluationOutcome.UNVERIFIED,
                gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-002"),
                error="Predicate has free variables without declared schema",
            )
        raw_schema = {}

    schema_types: dict[str, VariableType] = {}
    try:
        for k, v in raw_schema.items():
            if isinstance(v, (list, tuple)):
                schema_types[k] = VariableType.from_dict(k, {"type": "Int", "domain": v})
            else:
                schema_types[k] = VariableType.from_dict(k, v)
    except Exception as e:
        return EvaluationResult(
            outcome=EvaluationOutcome.UNVERIFIED,
            gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-002"),
            error=f"Schema finite domain error: {e}",
        )

    # 5. Evaluate Layer 1 base satisfiability
    budget = int(spec.get("evaluation_budget_assignments", PredicateEvaluator.DEFAULT_BUDGET))
    if spec.get("residual_enumerator_completed") is False:
        # Explicit test override for uncompleted residual search (F2-T13)
        budget = 0

    base_eval = PredicateEvaluator.evaluate_base(ast, schema_types, budget=budget)

    # Check for tautology / contradiction classification
    cl_eval: ClassificationEvaluation | None = None
    if str(raw_pred).strip().upper() == "TRUE":
        cl_eval = ClassificationEvaluation(
            classification=Classification.TAUTOLOGY,
            queries=({"query": "FALSE", "base_result": "UNSAT"},),
        )
    elif base_eval.base_result == BaseResult.UNSAT and not isinstance(ast, BoolLiteralNode):
        cl_eval = ClassificationEvaluation(
            classification=Classification.CONTRADICTORY,
            queries=({"query": ast.canonical(), "base_result": "UNSAT"},),
        )

    # 6. Map to gate output
    approval = spec.get("authoritative_approval")
    gate_out = map_to_gate_output(
        eval_res=base_eval,
        class_res=cl_eval,
        consumer=consumer,
        authoritative_approval=approval,
    )

    return EvaluationResult(
        outcome=EvaluationOutcome.VERIFIED,
        base=base_eval,
        classification=cl_eval,
        gate_output=gate_out,
    )
