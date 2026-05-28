# Path 2 Setup — Placeholder Replacement Guide

**Follow this to know exactly where to edit each file.**

---

## What You Need

Before starting edits, gather:
- Your GitHub repository URL: `https://github.com/yourname/your-actuarial-repo`
- Your Gmail email address: `yourname@gmail.com`

---

## File 1: `.claude-dev/MODEL_DEV_STATE.json`

### Location & What It Does
- **Where:** Copy `MODEL_DEV_STATE_TEMPLATE.json` → `.claude-dev/MODEL_DEV_STATE.json`
- **Purpose:** State persistence file — Claude reads this first every cycle to know what task to do next

### Edit 1 of 2: Repository URL

**Find this line (around line 26):**
```json
    "url": "https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO",
```

**Replace with your actual URL:**
```json
    "url": "https://github.com/wilson-ng/actuarial-stochastic-model",
```

(If your repo is at `https://github.com/wilson-ng/stochastic-actuarial`, use that.)

### Edit 2 of 2: Email Address

**Find this line (around line 80):**
```json
    "recipient": "your.email@gmail.com",
```

**Replace with your actual email:**
```json
    "recipient": "wilson@example.com",
```

### Save and Commit
```bash
git add .claude-dev/MODEL_DEV_STATE.json
git commit -m "Configure state file with repo URL and email"
git push origin main
```

---

## File 2: `.claude-dev/model-dev-task.md`

### Location & What It Does
- **Where:** Copy `MODEL_DEV_TASK_PROMPT.md` → `.claude-dev/model-dev-task.md`
- **Purpose:** Task definition — Claude's instructions for what to do each 12-hour cycle

### Edit 1 of 3: Repository URL (Line 3)

**Find this line (line 3, near the top):**
```markdown
**Repository:** https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
```

**Replace with:**
```markdown
**Repository:** https://github.com/wilson-ng/actuarial-stochastic-model
```

### Edit 2 of 3: Email Address (Line 4)

**Find this line (line 4):**
```markdown
**Email Recipient:** your.email@gmail.com (update below)
```

**Replace with:**
```markdown
**Email Recipient:** wilson@example.com (update below)
```

### Edit 3 of 3: Repository URL in Gmail Template (Around line 215-220)

**Find this line (inside the HTML email template section):**
```html
<a href="https://github.com/YOUR_USERNAME/YOUR_REPO/commit/{latest_commit_sha}">View Latest Commit</a><br/>
```

**Replace with:**
```html
<a href="https://github.com/wilson-ng/actuarial-stochastic-model/commit/{latest_commit_sha}">View Latest Commit</a><br/>
```

### Save and Commit
```bash
git add .claude-dev/model-dev-task.md
git commit -m "Configure task definition with repo URL and email"
git push origin main
```

---

## File 3: `MODEL_DEV_LOG.md`

### Location & What It Does
- **Where:** Create new file in repo root
- **Purpose:** Human-readable log of all development cycles

### Create File

In repo root, create `MODEL_DEV_LOG.md` with content:

```markdown
# Actuarial Model Development Log

Automated 12-hour development cycles initiated: 2026-05-14

## Setup Information
- **Repository:** https://github.com/wilson-ng/actuarial-stochastic-model
- **Email Recipient:** wilson@example.com
- **Cadence:** Every 12 hours
- **Goal:** Industry standards (SOA, IA, ERM) aligned stochastic model
- **Status:** Starting Phase 1 — Model Review & Documentation

---

## Development Cycles

(Entries appended automatically by Claude after each cycle)

```

### Save and Commit
```bash
git add MODEL_DEV_LOG.md
git commit -m "Initial: create development log"
git push origin main
```

---

## Quick Find & Replace Summary

| File | Find | Replace |
|------|------|---------|
| `MODEL_DEV_STATE.json` | `YOUR_USERNAME/YOUR_ACTUARIAL_REPO` | `wilson-ng/actuarial-stochastic-model` |
| `MODEL_DEV_STATE.json` | `your.email@gmail.com` | `wilson@example.com` |
| `model-dev-task.md` | `YOUR_USERNAME/YOUR_ACTUARIAL_REPO` (line 3) | `wilson-ng/actuarial-stochastic-model` |
| `model-dev-task.md` | `your.email@gmail.com` (line 4) | `wilson@example.com` |
| `model-dev-task.md` | `YOUR_USERNAME/YOUR_REPO` (line ~216) | `wilson-ng/actuarial-stochastic-model` |
| `MODEL_DEV_LOG.md` | N/A (create new) | N/A |

---

## How to Know You Got It Right

After making all edits:

### Check 1: URLs are consistent
```bash
grep -r "YOUR_USERNAME" .claude-dev/
```
Should return **zero results**. If it returns anything, you missed an edit.

### Check 2: Emails are correct
```bash
grep -r "your.email@gmail.com" .claude-dev/
```
Should return **zero results**. If it returns anything, you missed an edit.

### Check 3: Files are valid JSON and Markdown
```bash
# Check JSON is valid
python3 -m json.tool .claude-dev/MODEL_DEV_STATE.json > /dev/null && echo "Valid JSON"

# Check markdown exists
ls -la MODEL_DEV_LOG.md
```

---

## Common Mistakes to Avoid

❌ **Mistake 1:** Forgetting to replace ALL occurrences
- Check: Grep for "YOUR_USERNAME" and "your.email@gmail.com" as shown above

❌ **Mistake 2:** Wrong capitalization
- Your repo might be `wilson-ng/actuarial-model` not `Wilson-Ng/Actuarial-Model`
- Check GitHub URL in browser, copy exactly

❌ **Mistake 3:** Using a non-Gmail email
- The Gmail integration only works with Gmail accounts
- Use your actual Gmail address (ending in @gmail.com)

❌ **Mistake 4:** Not pushing to GitHub
- After edits, must commit and push:
  ```bash
  git add .claude-dev/ MODEL_DEV_LOG.md
  git commit -m "Configure automation files"
  git push origin main
  ```

❌ **Mistake 5:** Editing the template files instead of copies
- Don't edit the original template files in your templates folder
- Copy them to `.claude-dev/` first, then edit the copies

---

## Step-by-Step Example (Using Real GitHub URL)

### Scenario
- Your GitHub: `https://github.com/wilson-ng/actuarial-stochastic-model`
- Your email: `wilson.ng@gmail.com`
- You're in your repo directory: `/Users/wilson/projects/actuarial-stochastic-model`

### Step 1: Copy State Template
```bash
cp ~/Downloads/MODEL_DEV_STATE_TEMPLATE.json .claude-dev/MODEL_DEV_STATE.json
```

### Step 2: Edit State File
Open `.claude-dev/MODEL_DEV_STATE.json` in your editor:

**Line 26 — Before:**
```json
    "url": "https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO",
```

**Line 26 — After:**
```json
    "url": "https://github.com/wilson-ng/actuarial-stochastic-model",
```

**Line 80 — Before:**
```json
    "recipient": "your.email@gmail.com",
```

**Line 80 — After:**
```json
    "recipient": "wilson.ng@gmail.com",
```

Save file.

### Step 3: Copy Task Template
```bash
cp ~/Downloads/MODEL_DEV_TASK_PROMPT.md .claude-dev/model-dev-task.md
```

### Step 4: Edit Task File
Open `.claude-dev/model-dev-task.md` in your editor:

**Line 3 — Before:**
```markdown
**Repository:** https://github.com/YOUR_USERNAME/YOUR_ACTUARIAL_REPO
```

**Line 3 — After:**
```markdown
**Repository:** https://github.com/wilson-ng/actuarial-stochastic-model
```

**Line 4 — Before:**
```markdown
**Email Recipient:** your.email@gmail.com (update below)
```

**Line 4 — After:**
```markdown
**Email Recipient:** wilson.ng@gmail.com (update below)
```

**Line ~216 — Before:**
```html
<a href="https://github.com/YOUR_USERNAME/YOUR_REPO/commit/{latest_commit_sha}">View Latest Commit</a><br/>
```

**Line ~216 — After:**
```html
<a href="https://github.com/wilson-ng/actuarial-stochastic-model/commit/{latest_commit_sha}">View Latest Commit</a><br/>
```

Save file.

### Step 5: Create Log File
In repo root:
```bash
cat > MODEL_DEV_LOG.md << 'EOF'
# Actuarial Model Development Log

Automated 12-hour development cycles initiated: 2026-05-14

## Setup Information
- **Repository:** https://github.com/wilson-ng/actuarial-stochastic-model
- **Email Recipient:** wilson.ng@gmail.com
- **Cadence:** Every 12 hours
- **Goal:** Industry standards (SOA, IA, ERM) aligned stochastic model
- **Status:** Starting Phase 1 — Model Review & Documentation

---

## Development Cycles

(Entries appended automatically by Claude after each cycle)

EOF
```

### Step 6: Verify & Commit
```bash
# Verify no placeholders left
grep -r "YOUR_USERNAME" .claude-dev/
grep -r "your.email@gmail.com" .claude-dev/

# Both should return nothing

# Commit
git add .claude-dev/ MODEL_DEV_LOG.md
git commit -m "Configure automation: add state, task definition, and log"
git push origin main

# Verify pushed
git log --oneline -1  # Should show your commit
```

---

## Verification Checklist

After all edits and commits:

```
☐ .claude-dev/MODEL_DEV_STATE.json exists
☐ State file has YOUR repo URL (not placeholder)
☐ State file has YOUR email (not placeholder)
☐ .claude-dev/model-dev-task.md exists
☐ Task file line 3 has YOUR repo URL
☐ Task file line 4 has YOUR email
☐ Task file line ~216 has YOUR repo URL
☐ MODEL_DEV_LOG.md exists in repo root
☐ All files committed and pushed to GitHub
☐ No grep results for "YOUR_USERNAME"
☐ No grep results for "your.email@gmail.com"
```

---

## You're Ready for Claude Code Setup

Once all placeholders are replaced and committed, proceed to:

**Next Step:** `PATH_2_SETUP_INSTRUCTIONS.md` → Step 3 (Configure Gmail)

You've completed the file preparation. Now you'll:
1. Enable Gmail in Claude Code
2. Create the scheduled task
3. Test it
4. Let it run autonomously every 12 hours
