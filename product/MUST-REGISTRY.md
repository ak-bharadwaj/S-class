### MUST registry — reserved ranges

This master maintains one non-reusing MUST namespace. Existing allocations remain fixed; later chapters may allocate only from their reserved range. The registry is authoritative for product-layer ID allocation, not for kernel semantics.

| Owner | Reserved range (prefix `PD-` omitted) | Currently allocated | Status rule |
|---|---:|---:|---|
| Ch1 | `CH1-001..099` | `001..002`, `004..007` | retired (never reused): 003 |
| Ch2 | `CH2-001..199` | `001..003`, `005..018`, `020..026`, `028..029`, `031..048`, `050..058`, `060..065` | retired (never reused): 004, 019, 027, 030, 049, 059 |
| Ch3 | `CH3-001..199` | `001..003`, `006..007`, `009..012`, `014..018`, `020` | retired (never reused): 004..005, 008, 013, 019, 021 |
| Ch4 | `CH4-001..199` | `002`, `005..010`, `012`, `014`, `016` | retired (never reused): 001, 003..004, 011, 013, 015, 017 |
| Ch5 | `CH5-001..199` | `003..012` | retired (never reused): 001..002 |
| Ch6 | `CH6-001..199` | `003`, `006..014` | retired (never reused): 001..002, 004..005 |
| Ch7 | `CH7-001..199` | `008..009`, `011..016` | retired (never reused): 001..007, 010 |
| Ch8 | `CH8-001..199` | `008..013` | retired (never reused): 001..007 |
| Ch9 | `CH9-001..199` | `003..010` | retired (never reused): 001..002 |
| Ch10 | `CH10-001..199` | `007..013` | retired (never reused): 001..006, 014..019 |
| F1 | `PD-F1-001..099` | `001..005` | allocated IDs never reused |
| F2 | `PD-F2-001..099` | `001..007` | allocated IDs never reused |
| F3 | `PD-F3-001..099` | `001..006` | allocated IDs never reused |
| F4 | `PD-F4-001..099` | `001..006` | allocated IDs never reused |
| F5 | `PD-F5-001..099` | `001..005` | allocated IDs never reused |
| F6 | `PD-F6-001..099` | `001..006` | allocated IDs never reused |
| F7 | `PD-F7-001..099` | `001..006` | allocated IDs never reused |
| F8 | `PD-F8-001..099` | `001..004` | allocated IDs never reused |
| F9 | `PD-F9-001..099` | `001..004` | allocated IDs never reused |
| F10 | `PD-F10-001..099` | `001..007` | allocated IDs never reused |

MUST-ID integrity is specified by `PD-CH2-028`; producer self-pass is owned by accepted `PD-F3-001`. Each chapter allocates only its active IDs (see the table above); retired IDs are listed in the status column and are never reused. `PD-CH10-013` is the sole open-issue completeness MUST (§10.6).
### Test registry

Every MUST test identifier resolves to a named Appendix F fixture or a clearly declared future definition point. Authored fixture text is traceability, not execution evidence until qualified adapter runs are recorded. Chapter and foundation ranges are listed below.

| Test ID range | Resolution |
|---|---|
| `CH1-T1..T8` | fixtures in Appendix F; retired vectors are omitted |
| `CH2-T1..T3, T5..T18, T20..T29, T31..T48, T50..T62, T65..T76` | fixtures in Appendix F; retired vectors are omitted |
| `CH3-T1..T3, T6, T7, T9..T12, T14..T22, T25, T26` | fixtures in Appendix F; retired vectors are omitted |
| `CH4-T2, T5..T12, T15, T16, T19, T20, T23, T24, T27..T30` | fixtures in Appendix F; retired vectors are omitted |
| `CH5-T3..T18` | fixtures in Appendix F; retired vectors are omitted |
| `CH6-T3, T6..T22` | fixtures in Appendix F; retired vectors are omitted |
| `CH7-T8..T11, T14..T25` | fixtures in Appendix F; retired vectors are omitted |
| `CH8-T8..T19` | fixtures in Appendix F; retired vectors are omitted |
| `CH9-T3..T6, T8..T24` | fixtures in Appendix F; retired vectors are omitted |
| `CH10-T7..T19` | fixtures in Appendix F; retired vectors are omitted |
| `F1-T1..T11` | fixtures in Appendix F |
| `F2-T1..T14` | fixtures in Appendix F |
| `F3-T1..T7` | fixtures in Appendix F |
| `F4-T1..T7` | fixtures in Appendix F |
| `F5-T1..T4, F5-T5a..T5c, F5-T6..T7` | fixtures in Appendix F |
| `F6-T1..T6` | fixtures in Appendix F |
| `F7-T1..T6` | fixtures in Appendix F |
| `F8-T1..T4` | fixtures in Appendix F |
| `F9-T1..T4` | fixtures in Appendix F |
| `F10-T1..T8` | fixtures in Appendix F |
