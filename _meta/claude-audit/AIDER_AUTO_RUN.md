# Aider Auto Run for Local Qwen

This file is the ready-to-run Aider wrapper for the prompts in
`_meta/claude-audit/qwen-prompts/`.

Default local model:

```powershell
ollama list
ollama run qwen3-coder:30b "say: ready"
```

Recommended Aider model name:

```text
ollama_chat/qwen3-coder:30b
```

If your local Ollama model has a different name, pass it with `-Model`.

---

## Safe unattended run

Run from the repository root:

```powershell
cd C:\Users\vladimir\Desktop\Investment\Tbot
.\scripts\run_qwen_prompts_aider.ps1
```

The script runs the safe prompts in this order:

1. `001_report_only_project_safety_audit.md`
2. `002_report_only_legacy_inventory.md`
3. `004_tests_gap_report.md`
4. `003_docs_update_project_boundaries.md`
5. `006_first_safe_docs_task.md`

This order follows `_meta/claude-audit/QWEN_AGENT_RUN_ORDER.md`.

The script uses:

```text
aider --message-file <prompt> --yes-always --auto-commits --no-dirty-commits
```

Auto-commits are intentional. Each prompt requires a clean git working tree
before the next prompt starts.

---

## Optional wire check

Prompt `009_wire_check_report.md` is report-only and safe, but it is not part
of the original overnight sequence. Add it explicitly:

```powershell
.\scripts\run_qwen_prompts_aider.ps1 -IncludeWireCheck
```

---

## Owner-review prompts

These prompts are intentionally excluded from the default unattended run:

- `005_first_safe_test_task.md`
- `007_first_safe_refactor_task.md`
- `008_next_recommended_task.md`

Run them only after reviewing the reports from the safe run:

```powershell
.\scripts\run_qwen_prompts_aider.ps1 -RunOwnerReviewTasks
```

---

## Dry run

Print the Aider commands without calling the model:

```powershell
.\scripts\run_qwen_prompts_aider.ps1 -DryRun -SkipPreflightTests
```

The script still checks that git is clean, because the real unattended run
depends on that invariant.

---

## Single prompt command

If you want to run one prompt manually through Aider:

```powershell
aider `
  --model ollama_chat/qwen3-coder:30b `
  --message-file _meta\claude-audit\qwen-prompts\001_report_only_project_safety_audit.md `
  --yes-always `
  --auto-commits `
  --no-dirty-commits `
  --no-restore-chat-history `
  --no-check-update
```

Use the PowerShell runner for the full batch, because it passes the expected
editable and read-only files for each prompt.
