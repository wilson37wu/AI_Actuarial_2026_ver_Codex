# Live-Region Status Announcements — Methodology Card

**Surface:** zero-install offline UI (`ui_app.html`) · **Standard:** WCAG 2.1 AA SC 4.1.3 (Status Messages) · **Phase 36 Task 2 (gap E1)** · **classification:** educational

## Purpose

Make dynamic state changes in the offline UI perceivable to screen-reader users without moving focus or interrupting them, completing the dynamic half of WCAG 2.1 AA (the static half — `:focus-visible`, keyboard operability, contrast — was delivered in Phase 35 A1).

## Mechanism

A single visually-hidden polite live region carries concise text updates:

```
<div id="srlive" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></div>
```

`announce(msg)` sets its `textContent`. Because the region is `aria-live="polite"`, assistive technology reads the update at the next graceful pause — it never interrupts and never steals focus. Four surfaces route through it:

| Surface | Announcement |
|---|---|
| Tab activation | "Showing tab: \<name\>" (Integrity tab also appends the verify outcome) |
| Global search | "N result(s) for \<query\>" |
| Distribution slider | "Distribution read-out: \<percentile / F(loss)\>" |
| Integrity verifier | "Content integrity verified" / "check: content altered" |

## Invariants (why this is safe)

- **Describes on-screen state only.** Every announcement is built from text already rendered; the announce path recomputes **no** model figure. The governed headline `39975.654628199336` and all governed read-outs render bit-for-bit.
- **Polite, never assertive.** No interruption; focus is never stolen; the region is `sr-only` and never visible.
- **Single announcer.** `#srlive` is the one dedicated live region for these four surfaces; the inline distribution read-out is no longer its own live region (no double-speak). The separate visible contract-mismatch banner is unchanged.
- **No contract change.** ARIA/JS only — the embedded `ui_data` payload is byte-identical, so the Phase 35 A2 per-section SHA-256 digests still verify in-browser by construction.
- **Zero-install.** No network, no storage API, single self-contained `file://`-openable HTML; 0 external references.

## Limitations

- The region announces immediate text updates; a time-based debounce is intentionally omitted so behaviour is synchronously verifiable — the polite region itself coalesces rapid updates at the AT level (the latest value is read).
- Verified under jsdom (programmatic) and by source inspection; live screen-reader passes (NVDA/JAWS/VoiceOver) are recommended as a future manual check.
