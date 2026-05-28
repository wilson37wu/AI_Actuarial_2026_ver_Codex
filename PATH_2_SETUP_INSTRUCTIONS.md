# Path 2: Claude Code Desktop Scheduled Task Setup Instructions

**Objective:** Set up autonomous 12-hour actuarial model development cycles with state persistence and Gmail progress reports.

**Time Required:** 20 minutes  
**Difficulty:** Low (copy-paste + configure UI)

---

## Prerequisites

- [ ] Claude Code Desktop installed and running
- [ ] Your actuarial stochastic model repository cloned locally
- [ ] Git credentials configured (`git config user.name` and `user.email`)
- [ ] Gmail account connected to Claude Code (will set up in Step 3)
- [ ] All 4 template files downloaded/available in a folder

---

## Step 1: Prepare Your Repository (5 min)

### 1.1 Open Your Repository

```bash
# Navigate to your actuarial model repo
cd /path/to/your/actuarial-repo

# Verify you're in the right place
ls -la
# You should see: .git/, model files, README.md, etc.
```

### 1.2 Create Directory Structure

```bash
# Create the hidden .claude-dev directory for state and task files
mkdir -p .claude-dev

# Verify it was created
ls -la | grep claude
```

### 1.3 Copy State File Template

From your folder with the 4 downloaded files:

```bash
# Copy the state template into your repo
cp /path/to/your/templates/MODEL_DEV_STATE_TEMPLATE.json \
   .claude-dev/MODEL_DEV_STATE.json
```

### 1.4 Edit the State File (Critical)

Open `.claude-dev/MODEL_DEV_STATE.json` in your editor and make **2 essential edits:**

**Find line ~26 (repository_info.url):**
```json
"url": "https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO",
```

Replace with your actual GitHub URL:
```json
"url": "https://github.com/yourname/your-actuarial-repo",
```

**Find line ~80 (email_config.recipient):**
```json
"recipient": "your.email@gmail.com",
```

Replace with your actual email:
```json
"recipient": "yourname@gmail.com",
```

**Save the file.**

### 1.5 Create Initial Development Log

Create `MODEL_DEV_LOG.md` in repo root:

```bash
cat > MODEL_DEV_LOG.md << 'EOF'
# Actuarial Model Development Log

Automated 12-hour development cycles initiated: 2026-05-14

## Setup Information
- **Repository:** Check .claude-dev/MODEL_DEV_STATE.json for URL
- **Cadence:** Every 12 hours
- **Goal:** Industry standards (SOA, IA, ERM) aligned stochastic model
- **Status:** Starting Phase 1 — Model Review & Documentation

---

## Development Cycles

(Entries appended automatically by Claude after each cycle)

EOF

# Commit these initial files
git add .claude-dev/MODEL_DEV_STATE.json MODEL_DEV_LOG.md
git commit -m "Initial setup: add state persistence and development log"
git push origin main
```

---

## Step 2: Prepare the Scheduled Task Definition (5 min)

### 2.1 Copy Task Prompt File

```bash
# Copy the task prompt into .claude-dev/
cp /path/to/your/templates/MODEL_DEV_TASK_PROMPT.md \
   .claude-dev/model-dev-task.md
```

### 2.2 Edit Task Prompt (2 Places)

Open `.claude-dev/model-dev-task.md` and make **2 edits:**

**Find line ~6 (Repository URL):**
```markdown
**Repository:** https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
```

Replace with your actual URL:
```markdown
**Repository:** https://github.com/yourname/your-actuarial-repo
```

**Find line ~7 (Email Recipient):**
```markdown
**Email Recipient:** your.email@gmail.com (update below)
```

Replace with your email:
```markdown
**Email Recipient:** yourname@gmail.com (update below)
```

**Find line ~216 (inside Gmail HTML template):**
```html
<a href="https://github.com/YOUR_USERNAME/YOUR_REPO/commit/{latest_commit_sha}">View Latest Commit</a><br/>
```

Replace with your repo URL:
```html
<a href="https://github.com/yourname/your-actuarial-repo/commit/{latest_commit_sha}">View Latest Commit</a><br/>
```

**Save the file.**

### 2.3 Commit Task Definition

```bash
git add .claude-dev/model-dev-task.md
git commit -m "Add Claude Code scheduled task definition for 12h automation"
git push origin main
```

---

## Step 3: Configure Gmail in Claude Code (3 min)

### 3.1 Open Claude Code Settings

In Claude Code Desktop:
1. Click **Settings** (gear icon, usually bottom-left)
2. Navigate to **Connectors** or **Integrations**

### 3.2 Enable Gmail

1. Look for **Gmail** in the connectors list
2. If it shows **"Not Connected"**:
   - Click **Connect**
   - You'll be redirected to Google login
   - Authenticate with the Gmail account you want to use
   - Grant Claude Code permission to create drafts
   - Return to Claude Code
3. You should now see **Gmail: Connected ✓**

**Note:** If Gmail is already connected, skip this section.

---

## Step 4: Create the Scheduled Task in Claude Code Desktop (5 min)

### 4.1 Open Your Repository

In Claude Code Desktop:

```bash
# From your repo directory, open Claude Code:
claude .
```

Or in Claude Code menu: **File** → **Open Folder** → Select your repo

### 4.2 Access the Tasks Menu

**Option A — Using Slash Command:**
```
Type in the chat: /schedule
```

**Option B — Using Menu:**
Click the **Tasks** icon (usually a checkbox or calendar icon in the left sidebar)

### 4.3 Create New Scheduled Task

You'll see a dialog or prompt. Fill in these fields:

| Field | Value |
|-------|-------|
| **Task Name** | `Actuarial Model Auto-Dev (12h)` |
| **Description** | `Autonomous 12-hour model development cycle with state persistence` |
| **Trigger Type** | `Recurring` or `Cron` |
| **Schedule (Cron)** | `0 */12 * * *` |
| **Timezone** | Your timezone (e.g., `Asia/Singapore`, `America/New_York`) |
| **Prompt/File** | `.claude-dev/model-dev-task.md` |

### 4.4 Enable Advanced Options

Look for toggles/checkboxes and enable these:

- ✅ **Autonomous Execution** (or "Allow autonomous mode")
  - This lets Claude commit and push without asking for confirmation each time

- ✅ **Git Integration** (or "Auto-commit changes")
  - This enables automatic git commits after work completes

- ✅ **Use Git Worktree** (Optional, but recommended)
  - This isolates changes in a temporary branch for safety
  - If enabled, set Branch Prefix: `claude-task/`

### 4.5 Save the Task

Click **Create** or **Save**.

You should see the task appear in your task list with:
- Status: `Enabled`
- Next Run: (timestamp in 12 hours)
- Last Run: (empty, or shows test run if you ran it)

---

## Step 5: Test Run the Task (3 min)

### 5.1 Manually Invoke the Task

In Claude Code, find your task in the task list and click **Run Now** or **Test**.

Claude will immediately start the scheduled task.

### 5.2 Wait for Completion

The task will take **2–4 minutes** to complete. You'll see:
- Claude loading and reading state file
- Model code being reviewed
- Changes being made
- A commit being created

### 5.3 Verify Success

After the task completes, check **all 3 of these:**

#### Check 1: Git Commit Created
```bash
git log --oneline -5
```

You should see a new commit at the top from Claude, something like:
```
[Phase 1] Audit current model code and architecture: Initial review...
```

#### Check 2: State File Updated
```bash
cat .claude-dev/MODEL_DEV_STATE.json | grep last_run
```

Should show a recent timestamp (not null).

#### Check 3: Gmail Draft Appeared
Go to your Gmail account:
1. Open Gmail in browser
2. Click **Drafts** on the left
3. You should see a new draft with subject like:
   ```
   [AUTO] Actuarial Model Dev — Phase 1 — Audit current model code and architecture
   ```

**If all 3 checks pass:** ✅ Your automation is working. Proceed to Step 6.

**If any check fails:** Go to [Troubleshooting](#troubleshooting) section below.

---

## Step 6: Enable Permanent Scheduling (2 min)

### 6.1 Confirm Task is Enabled

In Claude Code, check your task list:
```
/tasks
```

Your "Actuarial Model Auto-Dev (12h)" task should show:
- Status: **Enabled**
- Next Run: ~12 hours from now

### 6.2 What Happens Next

Once enabled:
- Claude Code will automatically invoke this task every 12 hours
- **No manual action needed from you**
- Each cycle:
  1. Reads state file (knows where you left off)
  2. Does focused model development work
  3. Updates state file (marks task complete, identifies next)
  4. Commits changes to GitHub
  5. Creates Gmail draft with progress
  6. Waits 12 hours, repeats

### 6.3 Keep Your Machine Awake (Optional but Recommended)

For reliable scheduled execution:

**Claude Code Desktop Settings:**
1. Settings → **General**
2. Enable: **Keep computer awake during scheduled tasks**

This prevents the task from being missed if your computer sleeps.

---

## Step 7: Monitor Automation (Ongoing)

### Daily Check-In

Once per day, spend 2 minutes checking progress:

**In Claude Code:**
```
/tasks
```
Shows next run time and status.

**In Gmail:**
Search for `[AUTO] Actuarial Model Dev` to see all cycle reports.

**In GitHub:**
```bash
git log --oneline -10
```
Shows commits from each cycle.

### Review Gmail Drafts

Each draft contains:
- **What was completed** in that cycle
- **Industry standards progress** (SOA/IA alignment)
- **Next 12-hour actions** (what the next cycle will do)
- **Blockers** (if anything needs manual attention)

You can:
- **Send it** as-is (it's already a complete progress report)
- **Edit it** and send (customize for stakeholders)
- **Ignore it** (it's archived in Drafts; automation continues regardless)

---

## How State Persistence Works

**The Key:** `.claude-dev/MODEL_DEV_STATE.json` is the contract between cycles.

Each cycle:
1. Claude reads the JSON file
2. Finds `current_phase` and `in_progress[0]`
3. Works on that ONE task
4. Marks it `completed` in the JSON
5. Moves `.next` to `in_progress`
6. Commits the JSON update

Next cycle starts fresh, reads the updated JSON, continues from exactly where the previous cycle stopped.

**Example Flow:**

**Cycle 1 (12:00 AM):**
```json
"in_progress": ["Audit current model code and architecture"],
"next": "Document all model assumptions and parameters"
```
→ Completes audit → Updates state

**Cycle 2 (12:00 PM):**
```json
"in_progress": ["Document all model assumptions and parameters"],
"next": "Identify deviations from SOA stochastic modeling standards"
```
→ Documents assumptions → Updates state

**Cycle 3 (12:00 AM +1 day):**
```json
"in_progress": ["Identify deviations from SOA stochastic modeling standards"],
"next": "Review existing validation and testing framework"
```
→ And so on...

---

## Timeline Expectations

**Phase 1: Model Review & Documentation**
- 6 tasks listed
- ~3 cycles (36 hours)
- Result: Full documentation, assumptions identified, standards gaps noted

**Phase 2: Industry Standards Alignment**
- 6 tasks listed
- ~3–4 cycles (36–48 hours)
- Result: Model aligned with SOA/IA standards

**Phase 3: Model Validation & Testing**
- 6 tasks listed
- ~4–5 cycles (48–60 hours)
- Result: Comprehensive test suite, validation framework

**Phase 4: Calibration & Backtesting**
- 6 tasks listed
- ~4–5 cycles (48–60 hours)
- Result: Calibrated parameters, backtesting reports

**Phase 5: Documentation & Delivery**
- 6 tasks listed
- ~3 cycles (36 hours)
- Result: Final documentation, deployment ready

**Total: ~5–10 days of automation to complete entire model development.**

---

## Adjusting Mid-Automation (If Needed)

### Scenario: You want to change the next task

1. Open `.claude-dev/MODEL_DEV_STATE.json` in your editor
2. Find the `current_phase` section
3. Edit `in_progress` and `next` arrays to reflect desired task
4. Save and commit:
   ```bash
   git add .claude-dev/MODEL_DEV_STATE.json
   git commit -m "Manual state adjustment: changed next task to [X]"
   git push origin main
   ```
5. Next scheduled cycle picks up the new state automatically

### Scenario: You want to pause automation

```bash
# In Claude Code:
/tasks
```

Find your task → Click **Disable** or **Cancel**

The task stops running. You can re-enable it anytime.

### Scenario: You want to skip a phase

1. Edit `.claude-dev/MODEL_DEV_STATE.json`
2. Change Phase X `status` from `pending` to `skipped`
3. Update `current_phase` to point to Phase Y
4. Set `in_progress` and `next` in Phase Y
5. Commit and push
6. Next cycle continues with Phase Y

---

## Troubleshooting

### Problem: Task Runs But No Commit Appears

**Symptoms:**
- `/tasks` shows "Last Run: [now]"
- No new commit in `git log`

**Solutions:**
1. Check git credentials are set:
   ```bash
   git config user.name
   git config user.email
   ```
   If empty, set them:
   ```bash
   git config --global user.name "Claude Auto-Dev"
   git config --global user.email "claude@auto.local"
   ```

2. Check git remote:
   ```bash
   git remote -v
   ```
   Should show `origin https://github.com/...` with valid URL

3. Test push manually:
   ```bash
   echo "test" > test.txt
   git add test.txt
   git commit -m "test commit"
   git push origin main
   ```
   If this fails, fix credentials before re-enabling automation.

### Problem: Gmail Draft Not Appearing

**Symptoms:**
- Task runs successfully
- Commit appears
- No draft in Gmail

**Solutions:**
1. Check Gmail is connected in Claude Code Settings → Connectors
2. Check email address in task prompt `.claude-dev/model-dev-task.md` (line ~7)
3. Check email address in state file `.claude-dev/MODEL_DEV_STATE.json` (line ~80)
4. Try manually creating a Gmail draft in Claude Code to test connection:
   ```
   Type: /gmail or look for Gmail in tools
   ```
   If you can create one manually, the connector works.

### Problem: Task Runs But Work Seems Incomplete

**Symptoms:**
- Commits are created
- State file updates
- But work feels rushed or incomplete

**Solutions:**
1. The task may be too ambitious for 12 hours. Edit `.claude-dev/model-dev-task.md`
2. Break the current `in_progress` task into smaller subtasks
3. Edit state file to reflect smaller chunks
4. Next cycle will have more focused work

### Problem: State File Not Updating

**Symptoms:**
- Task runs
- Commit appears
- `.claude-dev/MODEL_DEV_STATE.json` shows old timestamp

**Solutions:**
1. Ensure task has **Autonomous Execution** enabled
2. Manually push state update:
   ```bash
   git status
   ```
   If `.claude-dev/MODEL_DEV_STATE.json` shows as modified but not committed:
   ```bash
   git add .claude-dev/MODEL_DEV_STATE.json
   git commit -m "Update state after manual run"
   git push origin main
   ```

### Problem: Task Doesn't Run at Scheduled Time

**Symptoms:**
- Next Run shows future time
- But at that time, nothing happens
- Computer was asleep

**Solution:**
1. Claude Code catches up when machine wakes
2. To prevent misses, enable in Claude Code Settings:
   - **General** → **Keep computer awake during scheduled tasks**
3. Or manually run task:
   ```
   /tasks → Find your task → Click "Run Now"
   ```

---

## File Checklist

Before considering setup complete, verify these files exist in your repo:

```
your-actuarial-repo/
├── .claude-dev/
│   ├── MODEL_DEV_STATE.json              ✓ (edited with your URLs)
│   └── model-dev-task.md                 ✓ (edited with your URLs)
├── MODEL_DEV_LOG.md                      ✓ (created, initially empty)
├── [Your model code files]               ✓ (existing)
└── .git/                                 ✓ (existing)
```

And in Claude Code:
- Task "Actuarial Model Auto-Dev (12h)" visible in `/tasks`
- Status: **Enabled**
- Trigger: **Recurring cron `0 */12 * * *`**

---

## Success Criteria

You've successfully completed Path 2 setup when:

✅ All 4 template files copied and edited with your URLs  
✅ `.claude-dev/` directory exists with state and task files  
✅ `MODEL_DEV_LOG.md` created in repo root  
✅ Scheduled task created in Claude Code Desktop  
✅ Test run completed successfully:
  - New commit in `git log`
  - `.claude-dev/MODEL_DEV_STATE.json` shows updated timestamp
  - Gmail draft appeared in Drafts folder
✅ Task shows **Enabled** in `/tasks`  
✅ Next scheduled run showing ~12 hours in future  

---

## You're Done

Your actuarial model automation is now live.

Claude will automatically develop your model every 12 hours, picking up exactly where the previous cycle left off, until all phases complete.

Monitor via:
- **Gmail drafts** — Progress reports every 12 hours
- **GitHub commits** — Work visible in commit history
- **Claude Code `/tasks`** — Next run time and status

No further manual setup needed. Let it run.

---

## Reference: Cron Schedule Explained

`0 */12 * * *`

- `0` = Minute 0
- `*/12` = Every 12 hours (0, 12, 24, 36 hours = midnight and noon)
- `*` = Every day
- `*` = Every month
- `*` = Every day of week

**Result:** Task runs at 12:00 AM (midnight) and 12:00 PM (noon) every day.

To change schedule:
- Every 6 hours: `0 */6 * * *`
- Every day at 9 AM: `0 9 * * *`
- Every Monday at 8 AM: `0 8 * * 1`

Edit in Claude Code task configuration.

---

## Quick Command Reference

```bash
# Check task status
/tasks

# Manually run task now
/tasks → [Your task] → Run Now

# Check recent commits
git log --oneline -10

# Check state file updated
cat .claude-dev/MODEL_DEV_STATE.json | grep last_run

# Disable automation
/tasks → [Your task] → Disable

# Re-enable automation
/tasks → [Your task] → Enable
```

---

**Setup complete. Automation running. Model development in progress.**
