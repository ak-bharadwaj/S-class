# MUST-ALLOCATION-V3 — Final 195 Active MUSTs Allocation (Roadmap §9j)

## Table 0 — Summary Counts & Self-Check (`195` Active MUSTs + `1` `RETIRED` `PD-CH4-013`)

| Metric | Verified Count | Notes |
|---|---|---|
| Active MUST rows allocated | `195` | `len(set(active_ids)) == 195 == MUST-REGISTRY == MUST-ALLOCATION-ROWS` |
| Retired MUST rows retained flagged | `1` | `PD-CH4-013` (`class=RETIRED`, kept flagged in CSV row 196) |
| `PROPOSE` rows remaining | `0` | Zero `PROPOSE` tokens in `plane`, `block`, `wi`, `rm_line`, or `basis` |
| Ruling diffs `v2 -> v3` | `7` | `7` §9j ruling rows (`PD-CH5-003,006,007`, `PD-CH10-008,009`, `PD-CH2-061`, `PD-CH3-010`) + `5` `WI-016` label cleanups (`WI-016 (PROPOSE-NEW-WI)` -> `WI-016`) |

## Table 1 — Counts per Plane (`195` Active MUSTs)

| plane | count |
|---|---|
| `S1` | `88` |
| `S2` | `9` |
| `S3` | `15` |
| `S4` | `8` |
| `S5` | `12` |
| `S6` | `20` |
| `S7` | `3` |
| `W1` | `2` |
| `W2` | `17` |
| `W3` | `17` |
| `W4` | `1` |
| `W5` | `1` |
| `W6` | `2` |

## Table 2 — Counts per Block (`195` Active MUSTs)

| block | count |
|---|---|
| `Block 2` | `88` |
| `Block 3` | `9` |
| `Block 4` | `8` |
| `Block 5` | `15` |
| `Block 6` | `40` |
| `Block 7` | `12` |
| `Block 8` | `20` |
| `Block 9` | `2` |
| `Block 12` | `1` |

## Table 3 — `v2 -> v3` Diff (`7` §9j Ruling Rows + `5` `WI-016` Label Normalizations)

| must_id | kind | old (`v2`) | new (`v3`) | rm_line |
|---|---|---|---|---|
| `PD-CH10-008` | `§9j RULING` | `S6 / Block 8 / PROPOSE` | `S7 / Block 12 / WI-420` | `RM:103` |
| `PD-CH10-009` | `§9j RULING` | `S6 / Block 8 / PROPOSE` | `S1 / Block 2 / WI-101` | `RM:72` |
| `PD-CH2-061` | `§9j RULING` | `S7 / Block 10 / PROPOSE` | `S7 / Block 9 / WI-356` | `RM:99` |
| `PD-CH3-010` | `§9j RULING` | `S7 / Block 10 / WI-356` | `S7 / Block 9 / WI-356` | `RM:99` |
| `PD-CH5-003` | `§9j RULING` | `S6 / Block 8 / PROPOSE` | `S1 / Block 2 / WI-100` | `RM:71` |
| `PD-CH5-006` | `§9j RULING` | `S6 / Block 8 / PROPOSE` | `S1 / Block 2 / WI-100` | `RM:71` |
| `PD-CH5-007` | `§9j RULING` | `S6 / Block 8 / PROPOSE` | `S1 / Block 2 / WI-100` | `RM:71` |
| `PD-CH10-007` | `WI-016 label cleanup` | `S1 / Block 2 / WI-016 (PROPOSE-NEW-WI)` | `S1 / Block 2 / WI-016` | `RM:9j (WI-016)` |
| `PD-CH10-010` | `WI-016 label cleanup` | `S1 / Block 2 / WI-016 (PROPOSE-NEW-WI)` | `S1 / Block 2 / WI-016` | `RM:9j (WI-016)` |
| `PD-CH10-011` | `WI-016 label cleanup` | `S1 / Block 2 / WI-016 (PROPOSE-NEW-WI)` | `S1 / Block 2 / WI-016` | `RM:9j (WI-016)` |
| `PD-CH10-012` | `WI-016 label cleanup` | `S1 / Block 2 / WI-016 (PROPOSE-NEW-WI)` | `S1 / Block 2 / WI-016` | `RM:9j (WI-016)` |
| `PD-CH10-013` | `WI-016 label cleanup` | `S1 / Block 2 / WI-016 (PROPOSE-NEW-WI)` | `S1 / Block 2 / WI-016` | `RM:9j (WI-016)` |

## Table 4 — Complete `195` Active MUSTs Allocation Table (V3) + `1` Retired Flagged

| must_id | section | class | plane | block | b_step | wi | rm_line | basis |
|---|---|---|---|---|---|---|---|---|
| `PD-CH1-001` | `1.1 (MUST-ALLOCATION-ROWS.md:7, master:L1082)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-CH1-002` | `1.2 (MUST-ALLOCATION-ROWS.md:8, master:L1105)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-CH1-004` | `1.5 (MUST-ALLOCATION-ROWS.md:9, master:L1185)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-CH1-005` | `1.6 (MUST-ALLOCATION-ROWS.md:10, master:L1209)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-CH1-006` | `1.8 (MUST-ALLOCATION-ROWS.md:11, master:L1242)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-CH1-007` | `1.9 (MUST-ALLOCATION-ROWS.md:12, master:L1264)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-CH10-007` | `10.6 (MUST-ALLOCATION-ROWS.md:13, master:L4594)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-016` | `RM:9j (WI-016)` | RM §9j: S1 / Block 2 evaluator (`WI-016` plan-integrity MUSTs); artifact owner = Block 0 |
| `PD-CH10-008` | `10.1 (MUST-ALLOCATION-ROWS.md:14, master:L4426)` | `M` | `S7` | `Block 12` | `B21` | `WI-420` | `RM:103` | RM §9j: CL ruling moves PD-CH10-008 -> S7 / Block 12 / WI-420 (S-CLASS-ROADMAP-FINAL.md:103); B21; b_step=B21 |
| `PD-CH10-009` | `10.2 (MUST-ALLOCATION-ROWS.md:15, master:L4450)` | `M` | `S1` | `Block 2` | `B22` | `WI-101` | `RM:72` | RM §9j: CL ruling moves PD-CH10-009 -> S1 / Block 2 / WI-101 (S-CLASS-ROADMAP-FINAL.md:72); B22; b_step=B22 |
| `PD-CH10-010` | `10.3 (MUST-ALLOCATION-ROWS.md:16, master:L4485)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-016` | `RM:9j (WI-016)` | RM §9j: S1 / Block 2 evaluator (`WI-016` plan-integrity MUSTs); artifact owner = Block 0 |
| `PD-CH10-011` | `10.4 (MUST-ALLOCATION-ROWS.md:17, master:L4519)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-016` | `RM:9j (WI-016)` | RM §9j: S1 / Block 2 evaluator (`WI-016` plan-integrity MUSTs); artifact owner = Block 0 |
| `PD-CH10-012` | `10.5 (MUST-ALLOCATION-ROWS.md:18, master:L4543)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-016` | `RM:9j (WI-016)` | RM §9j: S1 / Block 2 evaluator (`WI-016` plan-integrity MUSTs); artifact owner = Block 0 |
| `PD-CH10-013` | `10.6 (MUST-ALLOCATION-ROWS.md:19, master:L4567)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-016` | `RM:9j (WI-016)` | RM §9j: S1 / Block 2 evaluator (`WI-016` plan-integrity MUSTs); artifact owner = Block 0 |
| `PD-CH2-001` | `2.1 (MUST-ALLOCATION-ROWS.md:20, master:L1314)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-002` | `2.4 (MUST-ALLOCATION-ROWS.md:21, master:L1407)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-003` | `2.2 (MUST-ALLOCATION-ROWS.md:22, master:L1323)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-005` | `2.2 (MUST-ALLOCATION-ROWS.md:23, master:L1324)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-006` | `2.2 (MUST-ALLOCATION-ROWS.md:24, master:L1325)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-007` | `2.2 (MUST-ALLOCATION-ROWS.md:25, master:L1326)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-008` | `2.2 (MUST-ALLOCATION-ROWS.md:26, master:L1327)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-009` | `2.2 (MUST-ALLOCATION-ROWS.md:27, master:L1328)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-010` | `2.2 (MUST-ALLOCATION-ROWS.md:28, master:L1329)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-011` | `2.2 (MUST-ALLOCATION-ROWS.md:29, master:L1330)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-012` | `2.2 (MUST-ALLOCATION-ROWS.md:30, master:L1331)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-013` | `2.9 (MUST-ALLOCATION-ROWS.md:31, master:L1820)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-014` | `2.9 (MUST-ALLOCATION-ROWS.md:32, master:L1821)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-015` | `2.9 (MUST-ALLOCATION-ROWS.md:33, master:L1822)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-016` | `2.9 (MUST-ALLOCATION-ROWS.md:34, master:L1823)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-017` | `2.9 (MUST-ALLOCATION-ROWS.md:35, master:L1824)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-018` | `2.9 (MUST-ALLOCATION-ROWS.md:36, master:L1825)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-020` | `2.9 (MUST-ALLOCATION-ROWS.md:37, master:L1826)` | `M/E` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-021` | `2.9 (MUST-ALLOCATION-ROWS.md:38, master:L1827)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-022` | `2.9 (MUST-ALLOCATION-ROWS.md:39, master:L1828)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-023` | `2.9 (MUST-ALLOCATION-ROWS.md:40, master:L1829)` | `M/E` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-024` | `2.9 (MUST-ALLOCATION-ROWS.md:41, master:L1830)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-025` | `2.9 (MUST-ALLOCATION-ROWS.md:42, master:L1831)` | `M/J` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-026` | `2.9 (MUST-ALLOCATION-ROWS.md:43, master:L1832)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-028` | `2.9 (MUST-ALLOCATION-ROWS.md:44, master:L1833)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-029` | `2.10 (MUST-ALLOCATION-ROWS.md:45, master:L1921)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-031` | `2.10 (MUST-ALLOCATION-ROWS.md:46, master:L1922)` | `M` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-032` | `2.10 (MUST-ALLOCATION-ROWS.md:47, master:L1923)` | `M/E/J` | `W2` | `Block 6` | `NONE-IN-B00-B23` | `WI-210` | `RM:90` | S-CLASS-ROADMAP-FINAL.md:RM:90 (`WI-210`) |
| `PD-CH2-033` | `2.11 (MUST-ALLOCATION-ROWS.md:48, master:L1994)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-034` | `2.11 (MUST-ALLOCATION-ROWS.md:49, master:L1995)` | `E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-035` | `2.11 (MUST-ALLOCATION-ROWS.md:50, master:L1996)` | `M/E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-036` | `2.11 (MUST-ALLOCATION-ROWS.md:51, master:L1997)` | `E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-037` | `2.12 (MUST-ALLOCATION-ROWS.md:52, master:L2072)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-038` | `2.12 (MUST-ALLOCATION-ROWS.md:53, master:L2073)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-039` | `2.12 (MUST-ALLOCATION-ROWS.md:54, master:L2074)` | `E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-040` | `2.12 (MUST-ALLOCATION-ROWS.md:55, master:L2075)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-041` | `2.13 (MUST-ALLOCATION-ROWS.md:56, master:L2144)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-042` | `2.13 (MUST-ALLOCATION-ROWS.md:57, master:L2145)` | `E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-043` | `2.13 (MUST-ALLOCATION-ROWS.md:58, master:L2146)` | `M/E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-044` | `2.13 (MUST-ALLOCATION-ROWS.md:59, master:L2147)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-045` | `2.13 (MUST-ALLOCATION-ROWS.md:60, master:L2148)` | `M/E/J` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-046` | `2.11 (MUST-ALLOCATION-ROWS.md:61, master:L1998)` | `M/E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-047` | `2.11 (MUST-ALLOCATION-ROWS.md:62, master:L1999)` | `E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-048` | `2.12 (MUST-ALLOCATION-ROWS.md:63, master:L2076)` | `M` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-050` | `2.13 (MUST-ALLOCATION-ROWS.md:64, master:L2149)` | `M/E` | `W3` | `Block 6` | `NONE-IN-B00-B23` | `WI-220` | `RM:91` | S-CLASS-ROADMAP-FINAL.md:RM:91 (`WI-220`) |
| `PD-CH2-051` | `2.14 (MUST-ALLOCATION-ROWS.md:65, master:L2215)` | `M/E` | `W4` | `Block 6` | `NONE-IN-B00-B23` | `WI-230` | `RM:92` | S-CLASS-ROADMAP-FINAL.md:RM:92 (`WI-230`) |
| `PD-CH2-052` | `2.15 (MUST-ALLOCATION-ROWS.md:66, master:L2281)` | `M/E/J` | `W5` | `Block 6` | `NONE-IN-B00-B23` | `WI-240` | `RM:93` | S-CLASS-ROADMAP-FINAL.md:RM:93 (`WI-240`) |
| `PD-CH2-053` | `2.16 (MUST-ALLOCATION-ROWS.md:67, master:L2347)` | `M/J` | `W6` | `Block 6` | `NONE-IN-B00-B23` | `WI-250` | `RM:94` | S-CLASS-ROADMAP-FINAL.md:RM:94 (`WI-250`) |
| `PD-CH2-054` | `2.17 (MUST-ALLOCATION-ROWS.md:68, master:L2413)` | `M/E/J` | `W6` | `Block 6` | `NONE-IN-B00-B23` | `WI-250` | `RM:94` | S-CLASS-ROADMAP-FINAL.md:RM:94 (`WI-250`) |
| `PD-CH2-055` | `2.2 (MUST-ALLOCATION-ROWS.md:69, master:L1353)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-056` | `2.7 (MUST-ALLOCATION-ROWS.md:70, master:L1668)` | `M` | `W1` | `Block 6` | `NONE-IN-B00-B23` | `WI-200` | `RM:89` | S-CLASS-ROADMAP-FINAL.md:RM:89 (`WI-200`) |
| `PD-CH2-057` | `2.7 (MUST-ALLOCATION-ROWS.md:71, master:L1687)` | `M` | `W1` | `Block 6` | `NONE-IN-B00-B23` | `WI-200` | `RM:89` | S-CLASS-ROADMAP-FINAL.md:RM:89 (`WI-200`) |
| `PD-CH2-058` | `2.18 (MUST-ALLOCATION-ROWS.md:72, master:L2473)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R3: CL Round 2 R3 CH2 cross-phase -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH2-060` | `2.20 (MUST-ALLOCATION-ROWS.md:73, master:L2568)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R3: CL Round 2 R3 CH2 flow/guidance -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH2-061` | `2.21 (MUST-ALLOCATION-ROWS.md:74, master:L2630)` | `M` | `S7` | `Block 9` | `NONE-IN-B00-B23` | `WI-356` | `RM:99` | RM §9j: CL ruling moves PD-CH2-061 -> S7 / Block 9 / WI-356 (S-CLASS-ROADMAP-FINAL.md:99) |
| `PD-CH2-062` | `2.22 (MUST-ALLOCATION-ROWS.md:75, master:L2694)` | `M` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-113` | `RM:78` | R3: CL Round 2 R3 CH2 project-class qualification -> S2/Block 3; RM:30,78 (`WI-113`) |
| `PD-CH2-063` | `2.23 (MUST-ALLOCATION-ROWS.md:76, master:L2761)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R3: CL Round 2 R3 CH2 question-budget -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH2-064` | `2.24 (MUST-ALLOCATION-ROWS.md:77, master:L2808)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | R3: CL Round 2 R3 CH2 replay-point -> S1/Block 2; RM:29,73 (`WI-102`) |
| `PD-CH2-065` | `2.25 (MUST-ALLOCATION-ROWS.md:78, master:L2866)` | `M` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | R3: CL Round 2 R3 CH2 worked examples -> S6/Block 8; RM:35,98 (`WI-311`) |
| `PD-CH3-001` | `3.8 (MUST-ALLOCATION-ROWS.md:79, master:L3179)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R4: CL Round 2 R4 CH3 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH3-002` | `3.8 (MUST-ALLOCATION-ROWS.md:80, master:L3180)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R4: CL Round 2 R4 CH3 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH3-003` | `3.8 (MUST-ALLOCATION-ROWS.md:81, master:L3181)` | `E/J` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R4: Ch.3 guidance/StepPack -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH3-006` | `3.8 (MUST-ALLOCATION-ROWS.md:82, master:L3182)` | `E` | `S5` | `Block 7` | `NONE-IN-B00-B23` | `WI-302` | `RM:97` | R4: CL Round 2 R4 CH3 external process tools -> S5/Block 7; RM:34,97 (`WI-302`) |
| `PD-CH3-007` | `3.8 (MUST-ALLOCATION-ROWS.md:83, master:L3183)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R4: Ch.3 guidance/StepPack -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH3-009` | `3.8 (MUST-ALLOCATION-ROWS.md:84, master:L3184)` | `E` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R4: Ch.3 guidance/StepPack -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH3-010` | `3.8 (MUST-ALLOCATION-ROWS.md:85, master:L3185)` | `E` | `S7` | `Block 9` | `NONE-IN-B00-B23` | `WI-356` | `RM:99` | RM §9j: CL ruling moves PD-CH3-010 -> S7 / Block 9 / WI-356 (S-CLASS-ROADMAP-FINAL.md:99) |
| `PD-CH3-011` | `3.8 (MUST-ALLOCATION-ROWS.md:86, master:L3186)` | `E` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-113` | `RM:78` | R4: CL Round 2 R4 CH3 -> S2/Block 3; RM:30,78 (`WI-113`) |
| `PD-CH3-012` | `3.8 (MUST-ALLOCATION-ROWS.md:87, master:L3187)` | `M/E` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R4: Ch.3 guidance/StepPack -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH3-014` | `3.8 (MUST-ALLOCATION-ROWS.md:88, master:L3188)` | `E` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | R4: CL Round 2 R4 CH3 -> S6/Block 8; RM:35,98 (`WI-311`) |
| `PD-CH3-015` | `3.1 (MUST-ALLOCATION-ROWS.md:89, master:L2916)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R4: CL Round 2 R4 CH3 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH3-016` | `3.2 (MUST-ALLOCATION-ROWS.md:90, master:L2966)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R4: CL Round 2 R4 CH3 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH3-017` | `3.3 (MUST-ALLOCATION-ROWS.md:91, master:L3024)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R4: CL Round 2 R4 CH3 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH3-018` | `3.4 (MUST-ALLOCATION-ROWS.md:92, master:L3074)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R4: Ch.3 guidance/StepPack -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH3-020` | `3.6 (MUST-ALLOCATION-ROWS.md:93, master:L3117)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | R4: CL Round 2 R4 CH3 -> S1/Block 2; RM:29,73 (`WI-102`) |
| `PD-CH4-002` | `4.8 (MUST-ALLOCATION-ROWS.md:94, master:L3464)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R5: CL Round 2 R5 CH4 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH4-005` | `4.8 (MUST-ALLOCATION-ROWS.md:95, master:L3465)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | R5: CL Round 2 R5 CH4 -> S1/Block 2; RM:29,73 (`WI-102`) |
| `PD-CH4-006` | `4.8 (MUST-ALLOCATION-ROWS.md:96, master:L3466)` | `E` | `S1` | `Block 2` | `B18` | `WI-100` | `RM:71` | R5: CL Round 2 R5 CH4 -> S1/Block 2; RM:29,71 (`WI-100`); r29-companion/ROADMAP.md:33 |
| `PD-CH4-007` | `4.8 (MUST-ALLOCATION-ROWS.md:97, master:L3467)` | `M/E` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R5: Ch.4 guidance -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH4-008` | `4.8 (MUST-ALLOCATION-ROWS.md:98, master:L3468)` | `M` | `S6` | `Block 8` | `B17` | `WI-310` | `RM:98` | R5: CL Round 2 R5 CH4 -> S6/Block 8; RM:35,98 (`WI-310`); r29-companion/ROADMAP.md:33 |
| `PD-CH4-009` | `4.4 (MUST-ALLOCATION-ROWS.md:99, master:L3288)` | `M` | `S1` | `Block 2` | `B07` | `WI-100` | `RM:71` | R5: CL Round 2 R5 CH4 -> S1/Block 2; RM:29,71 (`WI-100`); r29-companion/ROADMAP.md:19 |
| `PD-CH4-010` | `4.4 (MUST-ALLOCATION-ROWS.md:100, master:L3289)` | `M/E` | `S4` | `Block 4` | `NONE-IN-B00-B23` | `WI-132` | `RM:86` | R5: CL Round 2 R5 CH4 -> S4/Block 4 (`RM:31,86` `WI-132`); NOTE: also needs its real fixture pair in Block 2 (`WI-100`, `RM:71`) |
| `PD-CH4-012` | `4.2 (MUST-ALLOCATION-ROWS.md:101, master:L3257)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | R5: CL Round 2 R5 CH4 -> S1/Block 2; RM:29,71 (`WI-100`) |
| `PD-CH4-014` | `4.4 (MUST-ALLOCATION-ROWS.md:103, master:L3327)` | `M` | `S4` | `Block 4` | `B09` | `WI-132` | `RM:86` | R5: CL Round 2 R5 CH4 -> S4/Block 4; RM:31,86 (`WI-132`); r29-companion/ROADMAP.md:23 |
| `PD-CH4-016` | `4.6 (MUST-ALLOCATION-ROWS.md:104, master:L3408)` | `E` | `S1` | `Block 2` | `B07` | `WI-100` | `RM:71` | R5: CL Round 2 R5 CH4 -> S1/Block 2; RM:29,71 (`WI-100`); r29-companion/ROADMAP.md:19 |
| `PD-CH5-003` | `5.6 (MUST-ALLOCATION-ROWS.md:105, master:L3639)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | RM §9j: CL ruling moves PD-CH5-003 -> S1 / Block 2 / WI-100 (S-CLASS-ROADMAP-FINAL.md:71) |
| `PD-CH5-004` | `5.6 (MUST-ALLOCATION-ROWS.md:106, master:L3640)` | `E` | `S6` | `Block 8` | `B16` | `WI-312` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-312`); r29-companion/ROADMAP.md:33 |
| `PD-CH5-005` | `5.6 (MUST-ALLOCATION-ROWS.md:107, master:L3641)` | `M/E` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`) |
| `PD-CH5-006` | `5.6 (MUST-ALLOCATION-ROWS.md:108, master:L3642)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | RM §9j: CL ruling moves PD-CH5-006 -> S1 / Block 2 / WI-100 (S-CLASS-ROADMAP-FINAL.md:71) |
| `PD-CH5-007` | `5.1 (MUST-ALLOCATION-ROWS.md:109, master:L3492)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | RM §9j: CL ruling moves PD-CH5-007 -> S1 / Block 2 / WI-100 (S-CLASS-ROADMAP-FINAL.md:71) |
| `PD-CH5-008` | `5.2 (MUST-ALLOCATION-ROWS.md:110, master:L3516)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | R6: S-CLASS-ROADMAP-FINAL.md:73 (FACT: `WI-102` explicitly names `ch.5 PD-CH5-008/009`) |
| `PD-CH5-009` | `5.3 (MUST-ALLOCATION-ROWS.md:111, master:L3540)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | R6: S-CLASS-ROADMAP-FINAL.md:73 (FACT: `WI-102` explicitly names `ch.5 PD-CH5-008/009`) |
| `PD-CH5-010` | `5.4 (MUST-ALLOCATION-ROWS.md:112, master:L3564)` | `M` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-312` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-312`) |
| `PD-CH5-011` | `5.5 (MUST-ALLOCATION-ROWS.md:113, master:L3588)` | `M` | `S6` | `Block 8` | `B16` | `WI-312` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-312`); r29-companion/ROADMAP.md:33 |
| `PD-CH5-012` | `5.6 (MUST-ALLOCATION-ROWS.md:114, master:L3612)` | `M` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`) |
| `PD-CH6-003` | `6.8 (MUST-ALLOCATION-ROWS.md:115, master:L3862)` | `E` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-006` | `6.8 (MUST-ALLOCATION-ROWS.md:116, master:L3863)` | `E` | `S5` | `Block 7` | `B12` | `WI-301` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-301`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-007` | `6.1 (MUST-ALLOCATION-ROWS.md:117, master:L3669)` | `M` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-008` | `6.2 (MUST-ALLOCATION-ROWS.md:118, master:L3693)` | `M` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-009` | `6.3 (MUST-ALLOCATION-ROWS.md:119, master:L3717)` | `M` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-010` | `6.4 (MUST-ALLOCATION-ROWS.md:120, master:L3741)` | `M` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-011` | `6.5 (MUST-ALLOCATION-ROWS.md:121, master:L3765)` | `M` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-012` | `6.6 (MUST-ALLOCATION-ROWS.md:122, master:L3789)` | `M` | `S5` | `Block 7` | `B12` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-013` | `6.7 (MUST-ALLOCATION-ROWS.md:123, master:L3813)` | `M` | `S5` | `Block 7` | `B12` | `WI-301` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-301`); r29-companion/ROADMAP.md:28 |
| `PD-CH6-014` | `6.8 (MUST-ALLOCATION-ROWS.md:124, master:L3835)` | `M` | `S5` | `Block 7` | `B20` | `WI-300` | `RM:97` | S-CLASS-ROADMAP-FINAL.md:34,97 (`WI-300`); r29-companion/ROADMAP.md:33 |
| `PD-CH7-008` | `7.1 (MUST-ALLOCATION-ROWS.md:125, master:L3909)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-122` | `RM:82` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,82 (`WI-122`) |
| `PD-CH7-009` | `7.2 (MUST-ALLOCATION-ROWS.md:126, master:L3933)` | `M` | `S3` | `Block 5` | `B10` | `WI-121` | `RM:81` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,81 (`WI-121`); r29-companion/ROADMAP.md:26 |
| `PD-CH7-011` | `7.4 (MUST-ALLOCATION-ROWS.md:127, master:L3969)` | `M` | `S3` | `Block 5` | `B11` | `WI-123` | `RM:83` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,83 (`WI-123`); r29-companion/ROADMAP.md:27 |
| `PD-CH7-012` | `7.5 (MUST-ALLOCATION-ROWS.md:128, master:L3993)` | `M` | `S3` | `Block 5` | `B10` | `WI-121` | `RM:81` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,81 (`WI-121`); r29-companion/ROADMAP.md:26 |
| `PD-CH7-013` | `7.6 (MUST-ALLOCATION-ROWS.md:129, master:L4017)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-123` | `RM:83` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,83 (`WI-123`) |
| `PD-CH7-014` | `7.7 (MUST-ALLOCATION-ROWS.md:130, master:L4041)` | `M` | `S3` | `Block 5` | `NONE-IN-B00-B23` | `WI-123` | `RM:83` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,83 (`WI-123`) |
| `PD-CH7-015` | `7.8 (MUST-ALLOCATION-ROWS.md:131, master:L4077)` | `M` | `S5` | `Block 7` | `NONE-IN-B00-B23` | `WI-302` | `RM:97` | R1: CL Round 2 R1 §7.8 -> S5/Block 7; RM:34,97 (`WI-302`) |
| `PD-CH7-016` | `7.1 (MUST-ALLOCATION-ROWS.md:132, master:L3892)` | `M` | `S3` | `Block 5` | `B10` | `WI-121` | `RM:81` | R1: CL Round 2 R1 §7.1-7.7 -> S3/Block 5; RM:32,81 (`WI-121`); r29-companion/ROADMAP.md:26 |
| `PD-CH8-008` | `8.1 (MUST-ALLOCATION-ROWS.md:133, master:L4102)` | `M` | `S4` | `Block 4` | `B05` | `WI-130` | `RM:85` | S-CLASS-ROADMAP-FINAL.md:31,85 (`WI-130`); r29-companion/ROADMAP.md:17 |
| `PD-CH8-009` | `8.2 (MUST-ALLOCATION-ROWS.md:134, master:L4126)` | `M` | `S4` | `Block 4` | `B09` | `WI-132` | `RM:86` | S-CLASS-ROADMAP-FINAL.md:31,86 (`WI-132`); r29-companion/ROADMAP.md:23 |
| `PD-CH8-010` | `8.3 (MUST-ALLOCATION-ROWS.md:135, master:L4150)` | `M` | `S4` | `Block 4` | `B09` | `WI-132` | `RM:86` | S-CLASS-ROADMAP-FINAL.md:31,86 (`WI-132`); r29-companion/ROADMAP.md:23 |
| `PD-CH8-011` | `8.4 (MUST-ALLOCATION-ROWS.md:136, master:L4174)` | `M` | `S4` | `Block 4` | `B09` | `WI-133` | `RM:86` | S-CLASS-ROADMAP-FINAL.md:31,86 (`WI-133`); r29-companion/ROADMAP.md:23 |
| `PD-CH8-012` | `8.5 (MUST-ALLOCATION-ROWS.md:137, master:L4198)` | `M` | `S4` | `Block 4` | `B09` | `WI-133` | `RM:86` | S-CLASS-ROADMAP-FINAL.md:31,86 (`WI-133`); r29-companion/ROADMAP.md:23 |
| `PD-CH8-013` | `8.6 (MUST-ALLOCATION-ROWS.md:138, master:L4222)` | `M` | `S4` | `Block 4` | `B08` | `WI-134` | `RM:86` | S-CLASS-ROADMAP-FINAL.md:31,86 (`WI-134`); r29-companion/ROADMAP.md:23 |
| `PD-CH9-003` | `9.3 (MUST-ALLOCATION-ROWS.md:139, master:L4398)` | `M/E` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-310` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-310`) |
| `PD-CH9-004` | `9.3 (MUST-ALLOCATION-ROWS.md:140, master:L4399)` | `E` | `S6` | `Block 8` | `B18` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`); r29-companion/ROADMAP.md:33 |
| `PD-CH9-005` | `9.3 (MUST-ALLOCATION-ROWS.md:141, master:L4400)` | `M` | `S6` | `Block 8` | `B19` | `WI-313` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-313`); r29-companion/ROADMAP.md:33 |
| `PD-CH9-006` | `9.3 (MUST-ALLOCATION-ROWS.md:142, master:L4401)` | `M/E/J` | `S6` | `Block 8` | `B18` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`); r29-companion/ROADMAP.md:33 |
| `PD-CH9-007` | `9.3 (MUST-ALLOCATION-ROWS.md:143, master:L4402)` | `E` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-310` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-310`) |
| `PD-CH9-008` | `9.1 (MUST-ALLOCATION-ROWS.md:144, master:L4321)` | `M` | `S6` | `Block 8` | `B17` | `WI-310` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-310`); r29-companion/ROADMAP.md:33 |
| `PD-CH9-009` | `9.2 (MUST-ALLOCATION-ROWS.md:145, master:L4347)` | `M` | `S6` | `Block 8` | `B18` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`); r29-companion/ROADMAP.md:33 |
| `PD-CH9-010` | `9.3 (MUST-ALLOCATION-ROWS.md:146, master:L4371)` | `M` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`) |
| `PD-F1-001` | `F1 (MUST-ALLOCATION-ROWS.md:147, master:L207)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F1-002` | `F1 (MUST-ALLOCATION-ROWS.md:148, master:L208)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F1-003` | `F1 (MUST-ALLOCATION-ROWS.md:149, master:L209)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F1-004` | `F1 (MUST-ALLOCATION-ROWS.md:150, master:L210)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F1-005` | `F1 (MUST-ALLOCATION-ROWS.md:151, master:L211)` | `M/E/J` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F10-001` | `F10 (MUST-ALLOCATION-ROWS.md:152, master:L1020)` | `M` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-112` | `RM:77` | S-CLASS-ROADMAP-FINAL.md:30,77 (`WI-112`) |
| `PD-F10-002` | `F10 (MUST-ALLOCATION-ROWS.md:153, master:L1021)` | `M/E` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-113` | `RM:78` | S-CLASS-ROADMAP-FINAL.md:30,78 (`WI-113`) |
| `PD-F10-003` | `F10 (MUST-ALLOCATION-ROWS.md:154, master:L1022)` | `M` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-110` | `RM:75` | S-CLASS-ROADMAP-FINAL.md:30,75 (`WI-110`) |
| `PD-F10-004` | `F10 (MUST-ALLOCATION-ROWS.md:155, master:L1023)` | `E` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-112` | `RM:77` | S-CLASS-ROADMAP-FINAL.md:30,77 (`WI-112`) |
| `PD-F10-005` | `F10 (MUST-ALLOCATION-ROWS.md:156, master:L1024)` | `M/E` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-112` | `RM:77` | S-CLASS-ROADMAP-FINAL.md:30,77 (`WI-112`) |
| `PD-F10-006` | `F10 (MUST-ALLOCATION-ROWS.md:157, master:L1025)` | `E/J` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-112` | `RM:77` | S-CLASS-ROADMAP-FINAL.md:30,77 (`WI-112`) |
| `PD-F10-007` | `F10 (MUST-ALLOCATION-ROWS.md:158, master:L1026)` | `E` | `S2` | `Block 3` | `NONE-IN-B00-B23` | `WI-112` | `RM:77` | S-CLASS-ROADMAP-FINAL.md:30,77 (`WI-112`) |
| `PD-F2-001` | `F2 (MUST-ALLOCATION-ROWS.md:159, master:L373)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F2-002` | `F2 (MUST-ALLOCATION-ROWS.md:160, master:L374)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F2-003` | `F2 (MUST-ALLOCATION-ROWS.md:161, master:L375)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F2-004` | `F2 (MUST-ALLOCATION-ROWS.md:162, master:L376)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F2-005` | `F2 (MUST-ALLOCATION-ROWS.md:163, master:L377)` | `E/J` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F2-006` | `F2 (MUST-ALLOCATION-ROWS.md:164, master:L378)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F2-007` | `F2 (MUST-ALLOCATION-ROWS.md:165, master:L379)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F3-001` | `F3 (MUST-ALLOCATION-ROWS.md:166, master:L443)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F3-002` | `F3 (MUST-ALLOCATION-ROWS.md:167, master:L444)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F3-003` | `F3 (MUST-ALLOCATION-ROWS.md:168, master:L445)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F3-004` | `F3 (MUST-ALLOCATION-ROWS.md:169, master:L446)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F3-005` | `F3 (MUST-ALLOCATION-ROWS.md:170, master:L447)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F3-006` | `F3 (MUST-ALLOCATION-ROWS.md:171, master:L448)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F4-001` | `F4 (MUST-ALLOCATION-ROWS.md:172, master:L583)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F4-002` | `F4 (MUST-ALLOCATION-ROWS.md:173, master:L584)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F4-003` | `F4 (MUST-ALLOCATION-ROWS.md:174, master:L585)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F4-004` | `F4 (MUST-ALLOCATION-ROWS.md:175, master:L586)` | `M/E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F4-005` | `F4 (MUST-ALLOCATION-ROWS.md:176, master:L587)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F4-006` | `F4 (MUST-ALLOCATION-ROWS.md:177, master:L588)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F5-001` | `F5 (MUST-ALLOCATION-ROWS.md:178, master:L668)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | S-CLASS-ROADMAP-FINAL.md:29,73 (`WI-102`) |
| `PD-F5-002` | `F5 (MUST-ALLOCATION-ROWS.md:179, master:L669)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,71 (`WI-100`) |
| `PD-F5-003` | `F5 (MUST-ALLOCATION-ROWS.md:180, master:L670)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,71 (`WI-100`) |
| `PD-F5-004` | `F5 (MUST-ALLOCATION-ROWS.md:181, master:L671)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-102` | `RM:73` | S-CLASS-ROADMAP-FINAL.md:29,73 (`WI-102`) |
| `PD-F5-005` | `F5 (MUST-ALLOCATION-ROWS.md:182, master:L672)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,71 (`WI-100`) |
| `PD-F6-001` | `F6 (MUST-ALLOCATION-ROWS.md:183, master:L729)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F6-002` | `F6 (MUST-ALLOCATION-ROWS.md:184, master:L730)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F6-003` | `F6 (MUST-ALLOCATION-ROWS.md:185, master:L731)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F6-004` | `F6 (MUST-ALLOCATION-ROWS.md:186, master:L732)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F6-005` | `F6 (MUST-ALLOCATION-ROWS.md:187, master:L733)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F6-006` | `F6 (MUST-ALLOCATION-ROWS.md:188, master:L734)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F7-001` | `F7 (MUST-ALLOCATION-ROWS.md:189, master:L794)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F7-002` | `F7 (MUST-ALLOCATION-ROWS.md:190, master:L795)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F7-003` | `F7 (MUST-ALLOCATION-ROWS.md:191, master:L796)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F7-004` | `F7 (MUST-ALLOCATION-ROWS.md:192, master:L797)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F7-005` | `F7 (MUST-ALLOCATION-ROWS.md:193, master:L798)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F7-006` | `F7 (MUST-ALLOCATION-ROWS.md:194, master:L799)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F8-001` | `F8 (MUST-ALLOCATION-ROWS.md:195, master:L855)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F8-002` | `F8 (MUST-ALLOCATION-ROWS.md:196, master:L856)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F8-003` | `F8 (MUST-ALLOCATION-ROWS.md:197, master:L857)` | `M` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F8-004` | `F8 (MUST-ALLOCATION-ROWS.md:198, master:L858)` | `E` | `S1` | `Block 2` | `NONE-IN-B00-B23` | `WI-100` | `RM:71` | S-CLASS-ROADMAP-FINAL.md:29,53,71 (`WI-100`) |
| `PD-F9-001` | `F9 (MUST-ALLOCATION-ROWS.md:199, master:L922)` | `M` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`) |
| `PD-F9-002` | `F9 (MUST-ALLOCATION-ROWS.md:200, master:L923)` | `M` | `S6` | `Block 8` | `B18` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`); r29-companion/ROADMAP.md:33 |
| `PD-F9-003` | `F9 (MUST-ALLOCATION-ROWS.md:201, master:L924)` | `E` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`) |
| `PD-F9-004` | `F9 (MUST-ALLOCATION-ROWS.md:202, master:L925)` | `M` | `S6` | `Block 8` | `NONE-IN-B00-B23` | `WI-311` | `RM:98` | S-CLASS-ROADMAP-FINAL.md:35,98 (`WI-311`) |
| `PD-CH4-013` | `4.3 (MUST-ALLOCATION-ROWS.md:102, master:L0)` | `RETIRED` | `RETIRED` | `RETIRED` | `NONE-IN-B00-B23` | `RETIRED` | `RETIRED` | MUST-ALLOCATION-ROWS.md:102 |
