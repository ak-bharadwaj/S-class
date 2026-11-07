# Block 2 Delivery Errata: R2-9 Frozen-Semantics Pair Correction

## 1. Errata Finding
In the initial Block 2 summary report, the R2-9 Frozen-Semantics Pair Note erroneously cited the Master Product Design document (`S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`, SHA-256 `340db978...`) as the package corpus semantics file. The Master Design document is the authoritative product specification Markdown file, not a Python semantics implementation module.

## 2. Authoritative Frozen Pair
The correct R2-9 pair consists of two distinct versions of the conformance semantics module:

1. **Repo In-Tree Conformance Semantics:**
   - Path: `10-CONFORMANCE/sclass_semantics_v6_0_1.py`
   - SHA-256: `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922`
   - Size: 303,939 bytes
   - Guard: Enforced by `tests/guards/test_frozen_integrity_guard.py`.

2. **Package-Original Conformance Semantics:**
   - Path: `frozen-v6.0.1/10-CONFORMANCE/sclass_semantics_v6_0_1.py` (in `S-CLASS-R32-PACKAGE`)
   - SHA-256: `66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76`
   - Size: 286,669 bytes

3. **Master Product Design Document (Separate Specification Artifact):**
   - Path: `S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`
   - SHA-256: `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`
   - Size: 699,827 bytes

Both semantics files remain 100% frozen, unedited, and protected across all branches.
