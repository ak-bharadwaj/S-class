# OSS Candidate Evaluation: SQLite

## 1. Candidate Overview
- **Project**: SQLite (`sqlite/sqlite`) — https://www.sqlite.org
- **Purpose**: C-language library that implements a small, fast, self-contained, high-reliability, full-featured, SQL database engine.
- **License**: Public Domain (blessing: "May you do good and not evil"). 100% compatible with all proprietary and open-source distributions.
- **Primary Language / Ecosystem**: C99. Built directly into the Python standard library (`sqlite3`), zero external dependencies.

## 2. Maturity & Governance
- **Maturity**: Created in 2000 (>26 years of continuous engineering). Unmatched stability guarantees (supported through year 2050+).
- **Maintainer Health**: Full-time core consortium led by D. Richard Hipp. Exceptionally disciplined maintenance, zero bloat, backward compatibility prioritized above all else.
- **Release Cadence**: Regular stable releases (every 2-3 months). Strict file format compatibility preserved since 2004 (SQLite 3.0.0).

## 3. Engineering Rigor & Trustworthiness
- **Security**: The gold standard in software security and robustness. Formally audited, fuzz-tested continuously by Google OSS-Fuzz with millions of test mutations per day.
- **Testing**:
  - Four independent test harnesses: TCL test suite, TH3, SLT (SQL Logic Test), and dbsqlfuzz.
  - **100% branch test coverage** under TH3 in deployed configuration.
  - Millions of automated test cases covering out-of-memory (OOM) fault injection, I/O error simulation, power-loss crash recovery, malformed database recovery, and boundary value checking.
- **Production Evidence**: Estimated >1 trillion active SQLite databases in existence across every Android/iOS phone, macOS/Windows PC, web browser, aircraft flight system, and space vehicle.
- **Platform Coverage**: Universal (runs anywhere a C compiler exists).
- **Protocol Compliance**: SQL-92 and large portions of SQL:1999/SQL:2003. Full ACID compliance in WAL (Write-Ahead Logging) mode.
- **Performance**: High-speed zero-network in-process execution. Microsecond reads and writes, highly optimized B-Tree and paging engine.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Zero. Available natively in Python via `sqlite3`.
- **Failure Modes**: Disk full, database lock contention, file corruption on unsafe hardware power loss (mitigated via WAL mode and `PRAGMA synchronous = NORMAL/FULL`).
- **What We Adopt**: Embedded relational engine, transactions, WAL persistence, relational schemas, foreign keys, index lookup.
- **What We DON'T Adopt**: SQLite is purely a storage mechanism; it does not define state semantics. S-Class owns domain invariants, state machines, transition authority, and cryptographic receipt validation.
- **S-Class Wrapper**: `sclass.storage.sqlite.SQLiteStateStore` and `SQLiteLedgerStore` wrapping the `StateStore` and `LedgerStore` protocols.
- **Escape Plan**: Domain entities and queries are isolated behind `StateRepository`. If cloud multi-tenancy or remote server execution is required, backends can be swapped for PostgreSQL or DuckDB without changing business logic.

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Persistence Engine)
- **Rationale Summary**: Reinventing a custom database or file-based store is irrational when SQLite provides 100% branch test coverage, crash recovery, and proven fault injection. S-Class provides state semantics; SQLite provides state persistence.
