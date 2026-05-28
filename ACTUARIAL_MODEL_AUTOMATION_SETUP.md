# Actuarial Stochastic Model Development — Automated Path 2 Setup

## Overview

This setup enables Claude Code to run scheduled tasks every 12 hours that:
1. **Read prior session state** from a persistent development log
2. **Continue model work** from where the previous run ended
3. **Commit progress** to GitHub with detailed messages
4. **Generate Gmail drafts** with progress summary and next steps

State persists across task runs via `MODEL_DEV_STATE.json` in your repo. Each 12-hour cycle is autonomous and picks up context automatically.

---

## Part 1: Repository Structure

Add these files to your actuarial model repo:

```
your-actuarial-repo/
├── .claude-dev/
│   ├── model-dev-task.md          # Scheduled task prompt (CREATED BELOW)
│   └── MODEL_DEV_STATE.json       # State persistence file (auto-created)
├── .github/
│   └── workflows/
│       └── claude-sync.yml        # Optional: sync state to remote
├── scripts/
│   ├── extract_state.py           # Extract repo state for context
│   └── update_state.json          # Helper to update JSON state
├── MODEL_DEV_LOG.md               # Human-readable development log
└── [existing model files...]
```

---

## Part 2: Create Persistent State File

Create `.claude-dev/MODEL_DEV_STATE.json` in your repo root:

```json
{
  "session_id": "model-dev-auto",
  "last_run": "2026-05-14T00:00:00Z",
  "current_phase": "Phase 1: Model Review & Documentation",
  "phases": {
    "Phase 1: Model Review & Documentation": {
      "status": "in_progress",
      "description": "Understand existing model structure, identify gaps vs industry standards (SOA, IA, ERM)",
      "tasks": [
        "Review model architecture and assumptions",
        "Check existing validation framework",
        "Document deviations from SOA/IA standards",
        "Identify calibration gaps"
      ],
      "completed": [],
      "in_progress": ["Review model architecture and assumptions"],
      "next": "Check existing validation framework"
    },
    "Phase 2: Industry Standards Alignment": {
      "status": "pending",
      "description": "Align model components with SOA/IA actuarial standards"
    },
    "Phase 3: Model Validation & Testing": {
      "status": "pending",
      "description": "Implement comprehensive validation suite"
    },
    "Phase 4: Calibration & Backtesting": {
      "status": "pending",
      "description": "Calibrate parameters and validate against historical data"
    },
    "Phase 5: Documentation & Delivery": {
      "status": "pending",
      "description": "Final documentation, model card, risk disclosures"
    }
  },
  "repository_info": {
    "url": "https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO",
    "branch": "main",
    "last_commit": "Initial model structure established"
  },
  "progress_metrics": {
    "phases_completed": 0,
    "estimated_completion_pct": 0,
    "critical_blockers": []
  },
  "technical_notes": {
    "model_type": "Stochastic",
    "key_components": [],
    "dependencies": []
  }
}
```

**Update the fields above:**
- `repository_info.url` → Your actual GitHub repo URL
- `technical_notes` → Your specific model architecture

---

## Part 3: Create the Scheduled Task Prompt

Create `.claude-dev/model-dev-task.md` with this YAML frontmatter + prompt:

```yaml
---
name: "Actuarial Model Auto-Development"
description: "Automated 12-hour model development cycle with state persistence"
---

# Actuarial Stochastic Model Development Task

## Context: Current Session State

Read from `.claude-dev/MODEL_DEV_STATE.json` at the start of each run.

**Current Phase:** {extract from state}
**Last Progress:** {extract from state.in_progress}
**Next Task:** {extract from state.phases[current].next}

## Your Task This Cycle

1. **Load State** (30 sec)
   - Read `.claude-dev/MODEL_DEV_STATE.json`
   - Review `MODEL_DEV_LOG.md` for context from prior runs
   - Identify the exact next step from `current_phase` → `next`

2. **Execute Development Work** (45–90 min)
   - Work on ONE specific task from the current phase
   - Make incremental, reviewable changes
   - Run validation/tests if model structure supports it
   - Document findings in code comments + commit messages

3. **Update State** (10 min)
   - Move completed task → `completed[]`
   - Advance `in_progress` to next task
   - Update progress metrics in `MODEL_DEV_STATE.json`
   - Commit changes with detailed message (see template below)

4. **Generate Gmail Draft** (5 min)
   - Create draft email with:
     - What was accomplished
     - Industry standard alignment progress
     - Next 12-hour action items
     - Any blockers or manual review needed
   - Use the Gmail template below

## Development Phases (Reference)

**Phase 1: Model Review & Documentation**
- Task: Review current model code, architecture, assumptions
- Task: Identify deviations from SOA/IA standards
- Task: Document existing validation gaps
- Task: Create assumptions document

**Phase 2: Industry Standards Alignment**
- Align stochastic process definitions (SOA standards)
- Implement required risk metrics (Value at Risk, etc.)
- Add governance framework compliance checks

**Phase 3: Model Validation & Testing**
- Unit tests for model components
- Integration testing across modules
- Stress testing and scenario analysis
- Backtesting framework

**Phase 4: Calibration & Backtesting**
- Parameter calibration to historical data
- Backtesting report generation
- Sensitivity analysis
- Model stability checks

**Phase 5: Documentation & Delivery**
- Model risk disclosures
- User guide and assumptions document
- Final validation report
- Deployment checklist

## Commit Message Template

```
[Phase N] Task Name: Brief summary

- Detailed accomplishment 1
- Detailed accomplishment 2
- Next immediate task: [specific]

Industry Standards Alignment:
- SOA standard X: [progress]
- IA requirement Y: [status]

Files changed: model.py, validation.py
Test status: PASSING / NEEDS REVIEW
```

## Gmail Draft Template

To create the draft, call the Gmail tool with:

**Subject:** `[AUTO] Actuarial Model Dev — Phase N — {Task Name}`

**Body (HTML):**

```html
<h3>Actuarial Model Development — 12-Hour Cycle Report</h3>

<p><strong>Session ID:</strong> {current_phase}<br/>
<strong>Run Time:</strong> {timestamp}<br/>
<strong>Duration:</strong> {elapsed time}</p>

<h4>✅ This Cycle — Completed</h4>
<ul>
  <li>{Task 1 summary}</li>
  <li>{Task 2 summary if applicable}</li>
</ul>

<h4>📊 Industry Standards Progress</h4>
<ul>
  <li><strong>SOA Standards:</strong> {specific alignment status}</li>
  <li><strong>IA Requirements:</strong> {specific alignment status}</li>
  <li><strong>Model Validation:</strong> {current level}</li>
</ul>

<h4>🎯 Next 12-Hour Actions (Immediate Next Run)</h4>
<ol>
  <li>{Task 1}</li>
  <li>{Task 2}</li>
</ol>

<h4>⚠️ Blockers / Manual Review Needed</h4>
{List any issues, or "None"}

<h4>📈 Overall Progress</h4>
<p>Phases Completed: {X}/5 | Estimated Completion: {Y}%</p>

<h4>GitHub Commit</h4>
<p><a href="https://github.com/YOUR_USERNAME/YOUR_REPO/commits/main">View latest commit</a></p>

<hr/>
<p><em>Auto-generated by Claude Code scheduled task. Review before sending if desired.</em></p>
```

---

## Part 4: Set Up the Scheduled Task in Claude Code Desktop

### Option A: Via Claude Code Desktop GUI

1. **Open Claude Code Desktop** and open your model repo
2. **Type:** `/schedule` (or click the Tasks menu)
3. **Create New Task:**
   - **Name:** "Actuarial Model Auto-Dev (12h)"
   - **Trigger:** Recurring cron
   - **Schedule:** `0 */12 * * *` (every 12 hours)
   - **Timezone:** Your local timezone
   - **Command/Prompt:** Point to `.claude-dev/model-dev-task.md`

4. **Enable Autonomous Mode:**
   - Toggle "Allow autonomous execution" (Claude can commit/push without prompts)
   - Toggle "Use worktree isolation" (optional; isolates changes for review)

5. **Save & Test**
   - Click "Test Run" to verify it works once
   - Check that Gmail draft is created successfully
   - Review first commit to main

### Option B: Via Claude Code CLI (Permanent, Survives Session Restart)

In your repo, create `.claude/scheduled-tasks/actuarial-model-dev/SKILL.md`:

```yaml
---
name: "Actuarial Stochastic Model Development"
description: "12-hourly autonomous model development with state persistence and Gmail reporting"
---

[Paste the full prompt from Part 3 above]
```

Then, in a Claude Code CLI session:

```bash
cd your-actuarial-repo
claude -p "/schedule task from .claude/scheduled-tasks/actuarial-model-dev/SKILL.md --recurring --cron '0 */12 * * *' --timezone 'Asia/Singapore'"
```

Claude will confirm and store the task permanently.

---

## Part 5: Configure Gmail Integration

### Step 1: Enable Gmail in Claude Code

In Claude Code Desktop Settings → Connectors, enable **Gmail**.

(Or, if using CLI, ensure your Claude account is authenticated with Gmail access.)

### Step 2: Update Task Prompt with Your Email

In `.claude-dev/model-dev-task.md`, replace placeholder with your email:

```
# At the end of the Gmail template section, add:
to_address: "your.email@gmail.com"
```

---

## Part 6: GitHub Integration (Optional but Recommended)

To push commits back to your repo automatically:

### Step 1: Ensure Git Credentials

```bash
git config user.name "Claude Auto-Dev"
git config user.email "claude@your-org.local"
git remote set-url origin https://YOUR_GITHUB_TOKEN@github.com/YOUR_USERNAME/YOUR_REPO.git
```

(Or use SSH keys if configured.)

### Step 2: Enable in Task

In Claude Code, when configuring the scheduled task, enable:
- **Git Integration:** ✓ Commit and push changes
- **Branch Strategy:** Push to `main` or feature branch (your choice)

---

## Part 7: First-Run Checklist

Before the first 12-hour cycle:

- [ ] `.claude-dev/MODEL_DEV_STATE.json` exists and is valid JSON
- [ ] `.claude-dev/model-dev-task.md` exists with correct repo URL
- [ ] `MODEL_DEV_LOG.md` created (initially empty or with project context)
- [ ] Scheduled task created and **test run successful**
- [ ] Gmail draft appeared in your inbox
- [ ] Commit was created in repo
- [ ] STATE FILE WAS UPDATED by Claude after task completion

---

## Part 8: Monitoring & Adjustments

### Check Task Status

In Claude Code Desktop:
```
/tasks
```

Shows all scheduled tasks, last run, next run, status.

### Manual Intervention

If you want to adjust the current phase or next steps mid-cycle:

1. Edit `.claude-dev/MODEL_DEV_STATE.json` directly
2. Commit and push
3. Next scheduled task will pick up the new state

### Extend/Modify Phases

Edit `.claude-dev/model-dev-task.md` → `## Development Phases` section. Changes take effect on the next run.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Task doesn't run at scheduled time | Computer was asleep. Claude catches up on next wake. Enable "Keep Awake" in Claude Settings if needed. |
| Gmail draft not created | Check Gmail connector is enabled. Verify email address in task prompt. |
| State file not updating | Ensure task has autonomous mode enabled. Check file permissions. |
| Model changes not committed | Verify git credentials are set. Check repo URL in state file is correct. |
| Task runs but model work is incomplete | Adjust task duration. Simplify Phase tasks into smaller, 30–45 min chunks. |

---

## Files Summary

| File | Purpose | Owner |
|------|---------|-------|
| `.claude-dev/MODEL_DEV_STATE.json` | State persistence; read/update by task | Claude + You (initial) |
| `.claude-dev/model-dev-task.md` | Scheduled task definition | You (create once, maintain) |
| `MODEL_DEV_LOG.md` | Human-readable log of all runs | Claude (append) |
| `.github/workflows/claude-sync.yml` | Optional: sync state to GitHub | You (optional) |
| `scripts/extract_state.py` | Helper to parse state before run | You (optional utility) |

---

## Next Steps

1. **Copy state file** to your repo and update with your GitHub URL + model details
2. **Copy task prompt** to `.claude-dev/model-dev-task.md`
3. **Create scheduled task** in Claude Code Desktop or CLI
4. **Test run once** — manually invoke to ensure it works
5. **Monitor first cycle** — review Gmail draft and commit
6. **Let it run** — Check back every 24–48 hours for progress

Each 12-hour cycle is independent but continuous. You'll receive a Gmail draft every 12 hours with a clear next-action summary.

---

## Repository Template Link

**Plug in your GitHub URL here:**

```
https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
```

Once you provide the URL, update these files:
- `.claude-dev/MODEL_DEV_STATE.json` → `repository_info.url`
- `.claude-dev/model-dev-task.md` → Any references to repo structure

