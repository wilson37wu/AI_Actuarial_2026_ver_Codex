# Cycle Status — 2026-07-03 — CF-1b Wide-Format CF Output (Owner Request)

**Item:** Owner request: restructure CF-set output so only the time
dimension is in rows; asset classes / product classes run horizontally as
headers.
**Outcome:** DONE

- `to_wide()` pivot added to `cashflow_projection_set.py`; all six CSVs now
  written wide (`<class>__<measure>` headers; balances use plain class
  labels); JSON yearly preview follows the same orientation and states it.
- Tidy frames unchanged in-process (`result["frames"]`) — CF-3 GUI tab and
  any downstream analytics keep the long form.
- Tests: 2 new pivot tests (wide==tidy spot equality, single-measure plain
  headers) + artifact test extended (row counts = 1200/100, no class column,
  expected headers present); 18/18 GREEN.

Next queued: CF-2 run integration, then CF-3 GUI tab.
