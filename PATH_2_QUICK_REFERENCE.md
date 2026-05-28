# Path 2 Setup — Quick Reference Card

**Print this page or keep it open while setting up.**

---

## 3-Minute Overview

Claude Code Desktop will run your model development every 12 hours automatically.

Each cycle:
1. Reads state file (knows what you did last cycle)
2. Does focused model work (one task at a time)
3. Updates state file (marks complete, identifies next)
4. Commits to GitHub
5. Creates Gmail draft with progress

---

## Setup Checklist (7 Steps, 20 min)

```
☐ Step 1: Prepare Repository (5 min)
    ☐ mkdir -p .claude-dev
    ☐ Copy MODEL_DEV_STATE_TEMPLATE.json → .claude-dev/MODEL_DEV_STATE.json
    ☐ Edit: Fix 2 placeholders (GitHub URL + email)
    ☐ Create MODEL_DEV_LOG.md in repo root
    ☐ git add + commit + push

☐ Step 2: Prepare Task Definition (5 min)
    ☐ Copy MODEL_DEV_TASK_PROMPT.md → .claude-dev/model-dev-task.md
    ☐ Edit: Fix 3 placeholders (GitHub URL x2 + email)
    ☐ git add + commit + push

☐ Step 3: Enable Gmail (3 min)
    ☐ Claude Code Settings → Connectors
    ☐ Find Gmail → Connect (if not connected)
    ☐ Authenticate with Google

☐ Step 4: Create Scheduled Task (5 min)
    ☐ Claude Code → /schedule
    ☐ Name: "Actuarial Model Auto-Dev (12h)"
    ☐ Cron: 0 */12 * * *
    ☐ File: .claude-dev/model-dev-task.md
    ☐ Enable: ✓ Autonomous Execution
    ☐ Enable: ✓ Git Integration
    ☐ Save

☐ Step 5: Test Run (3 min)
    ☐ /tasks → Find your task → Run Now
    ☐ Wait 2–4 minutes for completion
    ☐ VERIFY (all 3 must pass):
       ☐ git log shows new commit
       ☐ .claude-dev/MODEL_DEV_STATE.json has new timestamp
       ☐ Gmail Drafts has new email

☐ Step 6: Verify Enabled (1 min)
    ☐ /tasks → Check status is "Enabled"
    ☐ Check "Next Run" shows ~12 hours from now

☐ Step 7: Done
    ☐ Automation is live
    ☐ Check back in 12 hours for first progress email
```

---

## 5 Files You Need to Edit

### 1. `.claude-dev/MODEL_DEV_STATE.json`

Find & Replace:
```
❌ "url": "https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO",
✅ "url": "https://github.com/myname/my-actuarial-repo",

❌ "recipient": "your.email@gmail.com",
✅ "recipient": "myname@gmail.com",
```

### 2. `.claude-dev/model-dev-task.md`

Find & Replace (3 places):
```
❌ https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
✅ https://github.com/myname/my-actuarial-repo

❌ your.email@gmail.com
✅ myname@gmail.com
```

### 3. `MODEL_DEV_LOG.md` (New File)

Create in repo root with:
```markdown
# Actuarial Model Development Log

Automated cycles starting 2026-05-14

---
```

### 4 & 5: Leave Unchanged
- `ACTUARIAL_MODEL_AUTOMATION_SETUP.md` (reference only)
- `QUICK_START_5_STEPS.md` (reference only)

---

## Commands You'll Use

### Copy Files to Repo
```bash
cp /path/to/templates/MODEL_DEV_STATE_TEMPLATE.json \
   .claude-dev/MODEL_DEV_STATE.json

cp /path/to/templates/MODEL_DEV_TASK_PROMPT.md \
   .claude-dev/model-dev-task.md
```

### Commit Initial Setup
```bash
git add .claude-dev/ MODEL_DEV_LOG.md
git commit -m "Initial: add automation state and task definition"
git push origin main
```

### Check Task Status
```bash
/tasks
```

### Check Commits
```bash
git log --oneline -5
```

### Check State Updated
```bash
cat .claude-dev/MODEL_DEV_STATE.json | grep last_run
```

---

## Expected Results

### After Test Run (Step 5)

**In Terminal:**
```
$ git log --oneline -1
[Phase 1] Audit current model code... (a1b2c3d)
```

**In `.claude-dev/MODEL_DEV_STATE.json`:**
```
"last_run": "2026-05-14T12:34:56Z",  ← Updated to now
"cycles_run": 1,
```

**In Gmail Drafts:**
```
Subject: [AUTO] Actuarial Model Dev — Phase 1 — Audit current model...
```

### After 12 Hours (Next Cycle)

Same pattern repeats automatically:
- New commit
- State file updated
- New Gmail draft

---

## If Something Goes Wrong

| Issue | Check This | Fix |
|-------|-----------|-----|
| No commit | git credentials | `git config user.name/email` |
| No Gmail draft | Gmail connected? | Settings → Connectors → Gmail |
| State not updating | Autonomous mode on? | Task settings → Enable Autonomous |
| Task doesn't run at 12h | Computer asleep | Settings → Keep Awake During Tasks |

**For detailed troubleshooting:** See `PATH_2_SETUP_INSTRUCTIONS.md` → Troubleshooting section.

---

## Timeline

**Every 12 Hours:**
- One model development task completes
- Commit created
- State file advances
- Gmail draft sent

**Phase 1 (~36 hours):** Review & document model  
**Phase 2 (~48 hours):** Align with SOA/IA standards  
**Phase 3 (~60 hours):** Validation & testing  
**Phase 4 (~60 hours):** Calibration & backtesting  
**Phase 5 (~36 hours):** Final docs & delivery  

**Total: 5–10 days** → Complete actuarial model ready

---

## Email You'll Receive (Every 12 Hours)

```
Subject: [AUTO] Actuarial Model Dev — Phase 1 — Audit current model code and architecture

✅ Completed This Cycle
  • Audit current model code and architecture: Initial review of model structure

📈 Progress
  • Phases Completed: 1/5
  • Estimated Overall Completion: 20%

🎯 Industry Standards Alignment
  • SOA Standards: In Progress — Documenting stochastic process assumptions
  • IA Requirements: In Progress — Setting up governance framework
  • Validation Framework: Not Started

🎬 Next 12-Hour Actions
  1. Document all model assumptions and parameters
     - Will extract all key parameters and create documentation

2. Identify deviations from SOA stochastic modeling standards
   - Will compare current model against SOA best practices

⚠️ Blockers / Manual Review Needed
  None — proceeding autonomously

🔗 Commit & Code
  View Latest Commit
  Branch: main
  Files Changed: model.py, assumptions.md
```

---

## Modify During Automation (If Needed)

**To change next task mid-automation:**

1. Edit `.claude-dev/MODEL_DEV_STATE.json`
2. Change `in_progress` and `next` fields
3. `git add`, `commit`, `push`
4. Next cycle picks up new state automatically

**To pause:**
- `/tasks` → Your task → Disable

**To resume:**
- `/tasks` → Your task → Enable

---

## Files in Your Repo (After Setup)

```
your-actuarial-repo/
├── .claude-dev/
│   ├── MODEL_DEV_STATE.json         ← State persistence (auto-updated)
│   └── model-dev-task.md            ← Task definition (read each cycle)
├── MODEL_DEV_LOG.md                 ← Human-readable log (auto-appended)
├── [Your model code files...]
└── .git/
    └── [One new commit every 12 hours from Claude]
```

---

## Support Resources

1. **General Setup:** `ACTUARIAL_MODEL_AUTOMATION_SETUP.md`
2. **Quick Start:** `QUICK_START_5_STEPS.md`
3. **Detailed Instructions:** `PATH_2_SETUP_INSTRUCTIONS.md` (this file's companion)
4. **Task Prompt:** `.claude-dev/model-dev-task.md` (what Claude executes)
5. **State Template:** `.claude-dev/MODEL_DEV_STATE.json` (persistence across cycles)

---

## One-Line Summary

**Copy files → Edit 2 URLs in state file → Edit 3 URLs in task file → Create scheduled task in Claude Code → Run test → Done. Automation runs every 12 hours until model complete.**

---

## Success Looks Like This

### Day 1
- 2 cycles run (24 hours)
- 2 commits in GitHub
- 2 Gmail drafts
- Phase 1 ~30% complete

### Day 3
- 6 cycles run (72 hours)
- 6 commits in GitHub
- Phase 1 complete, Phase 2 in progress

### Day 7
- All 5 phases complete
- Model fully documented, validated, calibrated
- Ready for production

---

**You're ready. Set it up, then check back tomorrow.**
