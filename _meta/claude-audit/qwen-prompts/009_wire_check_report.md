# Prompt 009 — PlanRunner Wire Check (Report Only)

SAFE_FOR_UNATTENDED_RUN: YES
CHANGES_TO_CODE: NONE
INTERRUPTION_RISK: MINIMAL

---

## Role

You are a local coding agent running in read-only mode.
Your only job is to run four commands and fill in the report template below.
Do not make any decisions. Do not modify any files. Do not run tests.

---

## Project context

Project: Tbot v1 / Investor v1.
Location: current working directory.
The file `app/services/plan_runner.py` contains a class `PlanRunner`
that can execute investment plan orders via broker API.
The safety question: is `PlanRunner` currently scheduled to run automatically?

---

## Your exact steps — follow in order, no deviations

**Step 1.** Run this command and save the output as OUTPUT_A:

```bash
git status --short
```

**Step 2.** Run this command and save the output as OUTPUT_B:

```bash
grep -rn "PlanRunner" app/ --include="*.py"
```

**Step 3.** Run this command and save the output as OUTPUT_C:

```bash
grep -rn "plan_runner" app/ --include="*.py"
```

**Step 4.** Run this command and save the output as OUTPUT_D:

```bash
grep -rn "add_job\|scheduler.add\|BackgroundScheduler\|BlockingScheduler\|APScheduler" app/ --include="*.py"
```

**Step 5.** Create the file `_meta/claude-audit/009_wire_check_report.md`
with the content below. Replace each `[INSERT ...]` with the actual output
of the corresponding command. Do not interpret, do not summarize — paste the
raw command output exactly.

---

## Report template — paste raw command output into each section

```markdown
# PlanRunner Wire Check Report

Date: [INSERT today's date]
Model: qwen3-coder:30b
Task: 009

## Step 1 — git status --short

OUTPUT_A:
[INSERT raw output of git status --short here]

---

## Step 2 — grep PlanRunner in app/

OUTPUT_B:
[INSERT raw output of grep -rn "PlanRunner" app/ --include="*.py" here]

---

## Step 3 — grep plan_runner in app/

OUTPUT_C:
[INSERT raw output of grep -rn "plan_runner" app/ --include="*.py" here]

---

## Step 4 — grep scheduler calls in app/

OUTPUT_D:
[INSERT raw output of grep -rn "add_job|scheduler.add|BackgroundScheduler|BlockingScheduler|APScheduler" app/ --include="*.py" here]

---

## Conclusion

Fill in ONE of these conclusions based on OUTPUT_B and OUTPUT_C:

IF OUTPUT_B contains references ONLY in app/services/plan_runner.py itself
AND no other .py file references PlanRunner or plan_runner:
→ Write: "PlanRunner is defined but NOT scheduled. No active auto-execution."

IF OUTPUT_B or OUTPUT_C contains references in files OTHER than app/services/plan_runner.py:
→ Write: "PlanRunner IS referenced outside its own module. Files: [list the files from the grep output]"

IF OUTPUT_B is empty:
→ Write: "PlanRunner not found. Check if the file exists."

## Changed files

NONE

## Commands run

- git status --short
- grep -rn "PlanRunner" app/ --include="*.py"
- grep -rn "plan_runner" app/ --include="*.py"
- grep -rn "add_job|..." app/ --include="*.py"
```

---

## Done

After creating the file, your task is complete.
Do not run any other commands.
Do not edit any source files.
Do not run tests.
