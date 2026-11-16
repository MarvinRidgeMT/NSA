# POLARIS X v2 — status (one row per phase; each session edits only its own row)

Integration branch `feature/v2-whole-moon`. Split: `docs/v2/SPLIT.md`. Started 16 Nov 2026 ~02:40 EST.

| Phase / session | Status | Tests | Results | Open items | Hours |
|---|---|---|---|---|---|
| S1 · §1 6D model + cube v2 + backlog | not started | — | — | — | — |
| S2 · §2.1 whole-Moon data inventory + downloads | **done** (data in hand, unvalidated inputs) | pytest science/tests + tools/globe: 216 passed, 2 skipped; `fetch --check` 172/172; `fetch --verify` 172/172 OK, 0 missing, 0 bad | **105.93 GB** new, 172 files, all SHA-256 in manifest: SLDEM2015 512 ppd 45.30; LOLA polar LDEM 5–60 m both poles 37.27; PGDA 67 slope+azimuth 64 ppd 2.12 + 128 ppd 8.49; LROC WAC 100 m 5.96 (MD5 ok); LOLA global LDEM 16/64/128 ppd 5.37; LOLA roughness LDRM/LDSM/LDRC 1.31; PGDA 70 slope/Hurst 0.11. Free disk 377.7 GB. LOLA/SLDEM float heights are in **km** | not downloaded: Ch-2 TMC-2 (PRADAN) and CNSA (need an account the user has not approved); Kaguya TC DTMs, NAC DTMs, SfS (26.6 GB, 13 regions) stream on demand; JAXA SELENE wording unverified (DARTS rejects scripted requests) | ~2 |
| S3 · §2.2–2.3, 2.5 global pyramid, seams, coverage, roughness | not started | — | — | — | — |
| S4 · §2.4 any-site solver | not started | — | — | — | — |
| S5 · §5 Blender v2 pipeline + proof tests | not started | — | — | — | — |
| S6 · §6.1, 6.3 imagery catalogue + pre-registered protocol | not started | — | — | — | — |
| §4 6D decision tools across the Moon | not started (after Phase 1) | — | — | — | — |
| §3 worlds: Mercury, Mars | not started (after Phase 1) | — | — | — | — |
| §6.2, 6.4–6.5 render twins + scoring | not started (after S5 + S6) | — | — | — | — |
| §7 NASA-user features + gates | not started | — | — | — | — |
