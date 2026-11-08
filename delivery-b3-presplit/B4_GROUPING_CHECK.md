# B4: Proposed Grouping Check against EXECUTION-FLOW

## Proposed EXECUTION-FLOW Groups

| Group | Scope | Count | Status (Cap <= 6) | Member MUST IDs |
|---|---|---|---|---|
| **Group A (P0-P2)** | P0-P2 | 14 | **EXCEEDS 6** | `PD-CH2-001`, `PD-CH2-003`, `PD-CH2-005`, `PD-CH2-006`, `PD-CH2-007`, `PD-CH2-008`, `PD-CH2-009`, `PD-CH2-010`, `PD-CH2-011`, `PD-CH2-012`, `PD-CH2-055`, `PD-CH2-002`, `PD-CH2-056`, `PD-CH2-057` |
| **Group B (P3-P5)** | P3-P5 | 23 | **EXCEEDS 6** | `PD-CH2-013`, `PD-CH2-014`, `PD-CH2-015`, `PD-CH2-016`, `PD-CH2-017`, `PD-CH2-018`, `PD-CH2-020`, `PD-CH2-021`, `PD-CH2-022`, `PD-CH2-023`, `PD-CH2-024`, `PD-CH2-025`, `PD-CH2-026`, `PD-CH2-028`, `PD-CH2-029`, `PD-CH2-031`, `PD-CH2-032`, `PD-CH2-033`, `PD-CH2-034`, `PD-CH2-035`, `PD-CH2-036`, `PD-CH2-046`, `PD-CH2-047` |
| **Group C (P6-P7)** | P6-P7 | 11 | **EXCEEDS 6** | `PD-CH2-037`, `PD-CH2-038`, `PD-CH2-039`, `PD-CH2-040`, `PD-CH2-048`, `PD-CH2-041`, `PD-CH2-042`, `PD-CH2-043`, `PD-CH2-044`, `PD-CH2-045`, `PD-CH2-050` |
| **Group D (P8-P11)** | P8-P11 | 9 | **EXCEEDS 6** | `PD-CH2-051`, `PD-CH2-052`, `PD-CH2-053`, `PD-CH2-054`, `PD-CH2-058`, `PD-CH2-060`, `PD-CH2-061`, `PD-CH2-062`, `PD-CH2-063` |
| **Group E (F8 + replay)** | F8 + replay | 6 | **OK (<= 6)** | `PD-F8-001`, `PD-F8-002`, `PD-F8-003`, `PD-F8-004`, `PD-CH2-064`, `PD-CH2-065` |
| **Lane F4 (Adaptive Depth & Policy)** | Adaptive Depth & Policy | 6 | **OK (<= 6)** | `PD-F4-001`, `PD-F4-002`, `PD-F4-003`, `PD-F4-004`, `PD-F4-005`, `PD-F4-006` |

## Per-Phase Tag Distribution

| Phase Tag | Count | Status (Cap <= 6) | Notes |
|---|---|---|---|
| `F4` | 6 | OK (<= 6) | Fits within standard 6-MUST lane |
| `F8` | 4 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P0` | 12 | EXCEEDS 6 | Requires lane subdivision |
| `P1` | 2 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P10` | 1 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P11` | 6 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P3` | 14 | EXCEEDS 6 | Requires lane subdivision |
| `P4` | 3 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P5` | 6 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P6` | 5 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P7` | 6 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P8` | 1 | OK (<= 6) | Fits within standard 6-MUST lane |
| `P9` | 1 | OK (<= 6) | Fits within standard 6-MUST lane |
| `REPLAY` | 2 | OK (<= 6) | Fits within standard 6-MUST lane |
