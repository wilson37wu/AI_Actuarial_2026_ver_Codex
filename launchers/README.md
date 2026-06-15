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
- The **compute** step uses the model engine (`numpy`, `scipy`). If they're missing,
  the launcher says so; install once with `pip install numpy scipy`.
- The committed zero-install results template `ui_app.html` is **never modified** --
  your run is rendered into a separate `user_results/ui_app_user.html` copy.
- Localhost only; no outbound network; no model parameters are user-settable.
