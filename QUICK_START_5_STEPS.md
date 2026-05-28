# 5-Step Quick Start: Automated Actuarial Model Development

**Time required:** 15 minutes  
**Result:** Fully autonomous 12-hour development cycles with Gmail progress reports

---

## Step 1: Clone Your Actuarial Model Repo (2 min)

```bash
cd your-workspace
git clone https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
cd YOUR_ACTUARIAL_REPO
```

Verify you have:
- Model code (Python, R, or whatever language)
- README or documentation
- Git credentials configured

---

## Step 2: Add State Files to Repo (3 min)

### Create directory structure:
```bash
mkdir -p .claude-dev
```

### Copy the state file:
```bash
# Download MODEL_DEV_STATE_TEMPLATE.json (provided above)
# Rename to MODEL_DEV_STATE.json
# Edit the two placeholders:

# Line with "repository_info.url": 
# Change to: "https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO"

# Line with "email_config.recipient":
# Change to: "your.actual@email.com"

git add .claude-dev/MODEL_DEV_STATE.json
```

### Create initial development log:
```bash
cat > MODEL_DEV_LOG.md << 'EOF'
# Actuarial Model Development Log

Automated development cycles starting: 2026-05-14

## Initial Setup
- Repository: https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
- Cadence: Every 12 hours
- Email: your.email@gmail.com
- Target: Industry standards (SOA, IA, ERM) aligned stochastic model

---

EOF

git add MODEL_DEV_LOG.md
git commit -m "Initial setup: state files and development log"
git push origin main
```

---

## Step 3: Create the Scheduled Task Prompt (2 min)

### Create the task file:
```bash
# Download MODEL_DEV_TASK_PROMPT.md (provided above)
cp MODEL_DEV_TASK_PROMPT.md .claude-dev/model-dev-task.md

# Edit line 4 to replace email:
sed -i 's/your.email@gmail.com/YOUR_ACTUAL_EMAIL@gmail.com/g' .claude-dev/model-dev-task.md

# Edit line 3 to add your repo:
sed -i 's|YOUR_USERNAME/YOUR_ACTUARIAL_REPO|YOUR_USERNAME/YOUR_ACTUAL_REPO|g' .claude-dev/model-dev-task.md

git add .claude-dev/model-dev-task.md
git commit -m "Add scheduled task definition for 12h automation cycles"
git push origin main
```

---

## Step 4: Configure & Test in Claude Code Desktop (5 min)

### Open your repo in Claude Code Desktop:
```bash
# From your repo directory:
claude .
```

### Create the scheduled task:

**Option A — Via UI (Easiest):**
1. In Claude Code, press `/schedule`
2. Select "Create New Task"
3. Fill in:
   - **Name:** `Actuarial Model Auto-Dev (12h)`
   - **Trigger:** `Recurring`
   - **Cron Schedule:** `0 */12 * * *`
   - **Timezone:** Your timezone (e.g., `Asia/Singapore`)
   - **Prompt File:** `.claude-dev/model-dev-task.md`
4. Toggle ON:
   - ✅ Autonomous Execution (allow commits without prompts)
   - ✅ Use Git Integration (commit and push)
5. Click **Save**

**Option B — Via Command:**
```bash
claude -p "/schedule task --name 'Actuarial Model Auto-Dev' --cron '0 */12 * * *' --file '.claude-dev/model-dev-task.md' --autonomous"
```

### Test Run (Critical!):
1. Click "Test Now" or manually invoke the task once
2. **Wait 2–3 minutes** for task to complete
3. Check:
   - ✅ A new commit appeared in `git log`
   - ✅ `.claude-dev/MODEL_DEV_STATE.json` was updated
   - ✅ `MODEL_DEV_LOG.md` has a new entry
   - ✅ A draft email arrived in your Gmail inbox

If any step fails → **Fix before proceeding.** Check troubleshooting in the full guide.

---

## Step 5: Enable Gmail & Relax (3 min)

### Ensure Gmail is connected:
1. Claude Code Desktop → **Settings** → **Connectors**
2. Find **Gmail** → Click **Connect** (if not already connected)
3. Authenticate with your Google account
4. Return to task configuration

### Verify Task is Running:
```bash
# In Claude Code:
/tasks
```

You should see your task listed with:
- Next run time: In 12 hours
- Last run: Just now (test run)
- Status: `enabled`

### Done! Your automation is live.

Each cycle:
- **Reads** `.claude-dev/MODEL_DEV_STATE.json` for context
- **Executes** ONE focused model development task
- **Commits** changes to GitHub
- **Updates** state file with next task
- **Emails** you a progress draft

---

## What to Expect

**First Cycle (Now):**
- Claude audits your model code
- Identifies assumptions and standards deviations
- Creates initial documentation
- Sends Gmail draft

**Second Cycle (12 hours later):**
- Continues where cycle 1 left off
- Moves to next task (still Phase 1)
- Updates state file
- Sends updated Gmail draft

**Subsequent Cycles:**
- Each phase takes 3–7 cycles (36–84 hours)
- You receive email every 12 hours
- Zero manual intervention needed
- Progress visible in commits and email trail

---

## Key Files (After Setup)

```
Your Repo/
├── .claude-dev/
│   ├── MODEL_DEV_STATE.json         ← STATE PERSISTENCE (read/updated each cycle)
│   └── model-dev-task.md            ← SCHEDULED TASK DEFINITION
├── MODEL_DEV_LOG.md                 ← PROGRESS LOG (appended each cycle)
├── [Your model code files...]
└── .git/
    └── [commits created by automation]
```

---

## Monitoring: Check Status Anytime

### In Claude Code:
```
/tasks
```

### In Email:
Gmail inbox → Search: `subject:"[AUTO] Actuarial Model Dev"`

### In GitHub:
```
git log --oneline | head -10
```

You'll see one new commit every 12 hours from Claude.

---

## Adjust Mid-Cycle (If Needed)

**To change the next task:**
1. Edit `.claude-dev/MODEL_DEV_STATE.json` locally
2. Update the `phases[current_phase].in_progress` and `.next` fields
3. Commit and push
4. Next scheduled cycle picks up new state

**To pause automation:**
```
/tasks
# Find "Actuarial Model Auto-Dev"
# Click "Disable" or "Cancel"
```

**To resume:**
```
/tasks
# Click "Enable" or recreate the task
```

---

## Success Checklist

- [ ] Repo cloned and credentials working
- [ ] `.claude-dev/MODEL_DEV_STATE.json` created with your URLs
- [ ] `MODEL_DEV_LOG.md` created in repo root
- [ ] `.claude-dev/model-dev-task.md` created with your email
- [ ] Scheduled task configured in Claude Code
- [ ] Test run completed successfully
- [ ] Commit appeared in git log
- [ ] Gmail draft arrived in inbox
- [ ] Task shows "enabled" in `/tasks` list
- [ ] Next run scheduled in 12 hours

**If all checked:** ✅ Automation is live and will run every 12 hours until completion.

---

## Troubleshooting Quick Fixes

| Problem | Fix |
|---------|-----|
| Task doesn't run at scheduled time | Computer was asleep. Claude catches up when you wake it. Enable "Keep Computer Awake" in Settings. |
| No Gmail draft | Check Gmail connector enabled in Settings. Verify email address in task prompt. |
| Commit didn't appear | Check git credentials: `git config user.name` and `git config user.email`. Push manually: `git push origin main`. |
| State file not updating | Ensure task ran (check `/tasks`). Enable "Autonomous" mode. Check file permissions. |
| Task is too slow | Simplify current task. Break into smaller steps. Edit state file to move to next task. |

---

## Next: Monitoring & Insights

After first 24 hours, you'll have:
- 2 completed cycles (48 hours of model development)
- 2 Gmail drafts (one per cycle)
- 2+ commits in GitHub
- Visible progress on Phase 1

Review the Gmail drafts to see what was accomplished. Adjust state file or task prompt if needed for next phases.

---

**You're set up. Let Claude build your model autonomously. Check back in 12 hours for the first progress report.**
