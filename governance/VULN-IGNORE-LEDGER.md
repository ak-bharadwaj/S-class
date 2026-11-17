# S-Class Vulnerability Ignore Ledger

This ledger documents and authorizes all CVE and GHSA identifiers ignored during supply-chain vulnerability audits (`pip-audit`, CI workflows, and security gate checks).

Any ignored vulnerability missing from this ledger, containing an invalid owner, having a package mismatch, or having an expired date will cause security gate checks and CI to fail closed.

| id | package | reason | owner | expiry |
| :--- | :--- | :--- | :--- | :--- |
| `CVE-2026-114145` | gitpython | Submodule creation path vulnerability; S-Class does not invoke GitPython submodule clone APIs with untrusted paths | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111063` | aiohttp | Unbounded decompression in HTTP client; S-Class uses offline/unconfined mock transports | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111064` | aiohttp | HTTP header parsing CRLF injection; internal loopback/mock use only | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111065` | aiohttp | Multipart parser CPU exhaustion; no multipart endpoints exposed | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111066` | aiohttp | Memory exhaustion via unbounded chunked transfer; internal client only | ak-bharadwaj | 2027-12-31 |
| `GHSA-2g87-pp6c-29x5` | aiohttp | HTTP client request smuggling; internal IPC only, no reverse proxy | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111748` | aiohttp | Client TLS session reuse issue; TLS disabled on local loopback IPC | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111749` | aiohttp | HTTP response splitting on redirected connections; redirect disabled | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-111750` | aiohttp | HTTP proxy authorization header leak; no proxy configured | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-123817` | aiohttp | WebSocket frame length arithmetic overflow; WebSocket endpoints disabled | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128124` | aiohttp | Domain mask wildcard quadratic matching; host masks not configured | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128125` | aiohttp | CookieJar unbounded memory consumption; CookieJar not used | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128126` | aiohttp | POST body form field quadratic parse time; no form endpoints exposed | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128127` | aiohttp | Multipart chunked read memory limit bypass; multipart parser unused | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128128` | aiohttp | WebSocket max_msg_size buffer overflow; WebSocket protocol unused | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128129` | aiohttp | HTTP client connection pool leak under timeout; timeout handled externally | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128130` | aiohttp | HTTP client response header buffer exhaustion; headers restricted | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128131` | aiohttp | Concatenated compressed payload quadratic decompression; compression off | ak-bharadwaj | 2027-12-31 |
| `CVE-2026-128132` | aiohttp | Chunked encoding trailer parsing error; trailers ignored in local IPC | ak-bharadwaj | 2027-12-31 |
