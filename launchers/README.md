# One-click offline launcher (Phase IGUI Task 8)

Press one button to **supply inputs AND run the stochastic model**, then see
**your own** results in the offline UI -- all on `127.0.0.1`, fully offline.

| Your computer | Double-click |
|---|---|
| Windows | `Launch_Actuarial_GUI.bat` |
| macOS | `Launch_Actuarial_GUI.command` |
| Linux | `launch_actuarial_gui.sh` (or `python3 scripts/launch_offline_gui.py`) |

What happens:

1. The local Input & Run GUI opens in your browser.
2. Fill in run controls, model points, assumptions, ESG; clear the validation gate.
3. Press **Run the model end-to-end**.
4. Your own results appear at **`/my-results`** in the same browsable UI.

Notes:

- **No install needed** beyond Python 3.8+ for entering inputs and browsing.
- The **compute** step uses the model engine (`numpy`, `pandas`, `scipy`). If they're
  missing, the launcher says so and points you at the pinned, offline-capable install:
  `python -m pip install -r requirements-engine-lock.txt` (CPython 3.9-3.12).
  Full walkthrough (venv / air-gapped / verify): see
  [`docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md`](../docs/PHASE_IGUI_OFFLINE_INSTALL_APPENDIX.md).
  The pinned versions freeze the engine so the governed headline is reproducible; this
  is the **Option C** (run-from-source) path and pre-empts no packaging decision -- see
  [`docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md`](../docs/PHASE_IGUI_PACKAGING_OPTIONS_CARD.md).
- The committed zero-install results template `ui_app.html` is **never modified** --
  your run is rendered into a separate `user_results/ui_app_user.html` copy.
- Localhost only; no outbound network; no model parameters are user-settable.
