# UI Accessibility & Evidence-Integrity Design Card (Phase 35)

- Design note: `PHASE35_TASK1_DESIGN_NOTE` v1.0.0 - gate PASS (29 checks)
- Baseline: 8 offline self-tests green (340/11/27/9/9/10/18/21 = 445 checks), 0 network, 0 JS errors, 0 external refs, contract 1.18.0, 18 tabs
- Gaps (one per cycle): A1 formal WCAG 2.1 AA keyboard + contrast conformance pass (ADDITIVE a11y_audit, CSS focus + build-time contrast table); A2 per-section cryptographic digest in the H1 integrity panel (ADDITIVE manifest section_digests; in-browser SHA-256 verify, no network); A3 one-page printable model-card cover (presentation only, bit-for-bit, blank decision)
- Constraints: additive-only contract changes; zero-install preserved; display layer never recomputes (a hash is not a model figure); NO model parameter changes; Phase 30 binding stop-rule stands; MR-016/MR-017 owner decision pending and not pre-empted
- Detail: `docs/validation/PHASE35_TASK1_DESIGN_NOTE.{json,md}`
