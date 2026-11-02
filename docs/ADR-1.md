# ADR-1: Kernel Packaging and Canonical Byte Immutability Architecture

- **Status**: DECIDED / IMPLEMENTED (UNVERIFIED)
- **Author**: S-Class Architecture Team
- **Date**: 2026-10-03
- **Phase**: H0

---

## 1. Context & Problem Statement

The canonical specification for S-Class v6.0.1 defines the authoritative semantic type registry, event definitions, state machines, and reference reducer in `10-CONFORMANCE/sclass_semantics_v6_0_1.py`, and the control plane runtime in `20-RUNTIME/sclass_runtime_v6_0_1.py`.

Under the normative constraints of Phase H0:
1. `00-SPEC/`, `10-CONFORMANCE/`, and `20-RUNTIME/` are frozen (`git diff --stat 5420797..HEAD -- 00-SPEC 10-CONFORMANCE 20-RUNTIME` must yield 0 lines).
2. The software must be packaged as a standard Python distribution (`sclass`) installable via `pip install .` and binary wheels (`.whl`).
3. Clean installation into a fresh, isolated virtual environment must support entry points (`sclass`, `sclass-doctor`, `sclass-mcp`) and imports (`import sclass`).

We evaluated two architectural approaches to reconcile Python packaging requirements with the frozen source tree constraint.

---

## 2. Options Evaluated

### Option A: Build-Time Distribution Mapping via Custom `build_py` (Selected)

- **Approach**: Extend `setuptools.command.build_py.build_py` in `setup.py` to copy `10-CONFORMANCE/` and `20-RUNTIME/` files into package namespace `sclass/kernel/` solely during the packaging phase. The source directories on disk remain entirely untouched.
- **Commands Executed**:
```bash
python setup.py bdist_wheel
unzip -p dist/sclass-6.0.1-py3-none-any.whl sclass/kernel/sclass_semantics_v6_0_1.py | sha256sum
sha256sum 10-CONFORMANCE/sclass_semantics_v6_0_1.py
unzip -p dist/sclass-6.0.1-py3-none-any.whl sclass/kernel/sclass_runtime_v6_0_1.py | sha256sum
sha256sum 20-RUNTIME/sclass_runtime_v6_0_1.py
git diff --stat 5420797..HEAD -- 00-SPEC 10-CONFORMANCE 20-RUNTIME
```
- **Verbatim Output**:
```
ed2faf251863e141cbaf6b1e56b4f746d84a7587c699fa4841d6682aeec842fa  -
ed2faf251863e141cbaf6b1e56b4f746d84a7587c699fa4841d6682aeec842fa  10-CONFORMANCE/sclass_semantics_v6_0_1.py
761cd60498fd3998782a17f54c1569a473216892bb8dcbe1a7044ae142588fe1  -
761cd60498fd3998782a17f54c1569a473216892bb8dcbe1a7044ae142588fe1  20-RUNTIME/sclass_runtime_v6_0_1.py
(0 lines changed; exit code 0)
```
- **Evaluation**: Preserves 100% byte identity and path immutability across frozen directories while generating a standard wheel containing all kernel modules.

---

### Option B: Source Tree Reorganization via `git mv` (Rejected)

- **Approach**: Permanently move kernel files from `10-CONFORMANCE/` and `20-RUNTIME/` into `src/sclass/` using `git mv`.
- **Commands Executed**:
```bash
git mv 10-CONFORMANCE/sclass_semantics_v6_0_1.py src/sclass/
git mv 20-RUNTIME/sclass_runtime_v6_0_1.py src/sclass/
git diff --stat 5420797..HEAD -- 00-SPEC 10-CONFORMANCE 20-RUNTIME
```
- **Verbatim Output**:
```
 10-CONFORMANCE/sclass_semantics_v6_0_1.py | 3456 --------------------------
 20-RUNTIME/sclass_runtime_v6_0_1.py      | 2182 ----------------
 2 files changed, 5638 deletions(-)
```
- **Evaluation**: Fails the primary Phase H0 boundary constraint. Mutating source tree paths results in 5,638 line deletions across frozen directories.

---

## 3. Decision Outcome

**Decision**: Adopt **Option A**.

Packaging logic resides exclusively in `setup.py` custom build commands without modifying frozen specifications or kernel code.

---

## 4. Kernel Import & Module Alias Architecture

When the package is installed via wheel, the kernel modules are packaged under `sclass.kernel`:
- `sclass.kernel.sclass_semantics_v6_0_1`
- `sclass.kernel.sclass_runtime_v6_0_1`

To ensure legacy tests and modules importing unnamespaced identifiers continue to function with zero source modification, `src/sclass/semantics.py` and `src/sclass/runtime.py` implement module aliasing:

```python
# Alias mechanism in src/sclass/semantics.py
try:
    from sclass.kernel import sclass_semantics_v6_0_1 as _semantics
except ImportError:
    import sclass_semantics_v6_0_1 as _semantics

# Register alias in sys.modules
sys.modules.setdefault("sclass_semantics_v6_0_1", _semantics)
```

This ensures:
1. Namespaced imports (`from sclass.semantics import ...`) access the canonical kernel.
2. Legacy unnamespaced imports (`import sclass_semantics_v6_0_1 as Sem`) resolve to the exact same module instance in `sys.modules`.
3. Zero modifications required in `10-CONFORMANCE/` or `20-RUNTIME/`.

---

## 5. Audit & Justification of `sys.path` Manipulations

### `tools/cli/sclass.py`
- **Resolution**: Justified and retained:
```python
if sys.path and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)
```
- **Technical Justification**: When invoked directly as `python tools/cli/sclass.py`, Python automatically prepends the script's directory (`tools/cli`) to `sys.path[0]`. Because the script is named `sclass.py`, Python attempts to import itself as a module rather than the installed package, triggering `ModuleNotFoundError: No module named 'sclass.cli'; 'sclass' is not a package`. Popping `sys.path[0]` resolves package shadowing and enables direct script execution from any working directory.

### `tools/run_all_s0_partitions.py`
- **Resolution**: Justified and retained:
```python
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "10-CONFORMANCE"))
sys.path.insert(0, str(ROOT_DIR))
```
- **Technical Justification**: The Cosmic Ray mutation runner executes in-process mutation campaigns by applying AST modifications directly to the source file `10-CONFORMANCE/sclass_semantics_v6_0_1.py` on disk and invoking `importlib.reload()`. Placing `10-CONFORMANCE/` ahead of site-packages on `sys.path` is required so that dynamic reloads target the active in-tree mutant under test rather than an immutable wheel package installed in site-packages.
