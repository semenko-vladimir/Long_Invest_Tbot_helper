param(
    [string]$Model = "ollama_chat/qwen3-coder:30b",
    [string]$AiderCommand = "aider",
    [string]$PythonCommand = ".\venv312\Scripts\python.exe",
    [switch]$IncludeWireCheck,
    [switch]$RunOwnerReviewTasks,
    [switch]$SkipPreflightTests,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Require-CleanGit {
    param([string]$Stage)

    $status = git status --short
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed during $Stage"
    }

    if ($status) {
        Write-Host ""
        Write-Host "STOP: working tree is not clean during $Stage." -ForegroundColor Red
        Write-Host "Commit or stash these changes before running the unattended Aider batch:"
        $status | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
}

function Assert-PathExists {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required path not found: $Path"
    }
}

function Get-RepoFiles {
    param([string[]]$Paths)

    $files = @()
    $root = (Get-Location).Path

    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }

        $item = Get-Item -LiteralPath $path
        if ($item.PSIsContainer) {
            $files += Get-ChildItem -LiteralPath $path -Recurse -File |
                ForEach-Object { $_.FullName.Substring($root.Length + 1) }
        }
        else {
            $files += $path
        }
    }

    return $files | Sort-Object -Unique
}

function Invoke-AiderTask {
    param(
        [string]$Name,
        [string]$Prompt,
        [string[]]$EditableFiles,
        [string[]]$ReadOnlyFiles
    )

    Assert-PathExists $Prompt
    foreach ($path in $ReadOnlyFiles) {
        Assert-PathExists $path
    }

    Require-CleanGit "before $Name"

    $args = @(
        "--model", $Model,
        "--message-file", $Prompt,
        "--yes-always",
        "--auto-commits",
        "--no-dirty-commits",
        "--no-restore-chat-history",
        "--no-check-update",
        "--no-show-model-warnings",
        "--no-check-model-accepts-settings",
        "--no-gui",
        "--no-browser",
        "--map-tokens", "1024",
        "--test-cmd", ".\venv312\Scripts\python.exe -m unittest discover -q",
        "--chat-language", "Russian"
    )

    foreach ($path in $ReadOnlyFiles) {
        $args += @("--read", $path)
    }

    foreach ($path in $EditableFiles) {
        if (Test-Path -LiteralPath $path) {
            $args += $path
        }
    }

    Write-Host ""
    Write-Host "=== Running $Name ===" -ForegroundColor Cyan
    Write-Host "$AiderCommand $($args -join ' ')"

    if ($DryRun) {
        return
    }

    & $AiderCommand @args
    if ($LASTEXITCODE -ne 0) {
        throw "Aider failed during $Name with exit code $LASTEXITCODE"
    }

    Require-CleanGit "after $Name"
}

$safeTasks = @(
    @{
        Name = "001 safety audit report"
        Prompt = "_meta\claude-audit\qwen-prompts\001_report_only_project_safety_audit.md"
        EditableFiles = @(
            "_meta\claude-audit\001_safety_audit_report.md",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "app\services\orders.py",
            "app\services\mode.py",
            "app\services\trading_policy.py",
            "app\services\plan_runner.py",
            "app\services\plan_confirmation.py",
            "app\client\config\schedulers_config.py",
            "app\client\config\__init__.py",
            "app\run.py",
            "README.md",
            "PROJECT_INSTRUCTIONS.md",
            "V1_SCOPE.md"
        )
    },
    @{
        Name = "002 legacy inventory report"
        Prompt = "_meta\claude-audit\qwen-prompts\002_report_only_legacy_inventory.md"
        EditableFiles = @(
            "_meta\claude-audit\002_legacy_inventory_report.md",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "requirements-optional.txt",
            "requirements-base.txt",
            "app\run.py",
            "app\client\config\schedulers_config.py",
            "app\backend\main_api.py"
        ) + (Get-RepoFiles @(
            "app\client\signals",
            "app\client\graphics",
            "app\client\strategy",
            "app\client\store",
            "app\client\orders"
        ))
    },
    @{
        Name = "004 tests gap report"
        Prompt = "_meta\claude-audit\qwen-prompts\004_tests_gap_report.md"
        EditableFiles = @(
            "_meta\claude-audit\004_tests_gap_report.md",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "app\client\config\__init__.py"
        ) + (Get-RepoFiles @(
            "tests",
            "app\services"
        ))
    },
    @{
        Name = "003 docs update project boundaries"
        Prompt = "_meta\claude-audit\qwen-prompts\003_docs_update_project_boundaries.md"
        EditableFiles = @(
            "V1_SCOPE.md",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "README.md",
            "PROJECT_INSTRUCTIONS.md"
        )
    },
    @{
        Name = "006 create architecture doc"
        Prompt = "_meta\claude-audit\qwen-prompts\006_first_safe_docs_task.md"
        EditableFiles = @(
            "docs\ARCHITECTURE.md",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "app\run.py",
            "app\backend\main_api.py",
            "app\services\orders.py",
            "app\services\mode.py",
            "app\services\user_context.py",
            "app\services\portfolio.py",
            "app\services\watchlist.py",
            "app\services\dividends.py",
            "app\services\investment_plans.py",
            "app\services\statistics.py",
            "app\services\trading_policy.py",
            "app\services\plan_runner.py",
            "app\services\plan_confirmation.py",
            "app\services\settings_view.py",
            "app\services\order_history.py",
            "app\services\user_database.py",
            "README.md",
            "PROJECT_INSTRUCTIONS.md"
        )
    }
)

$wireCheckTask = @{
    Name = "009 plan runner wire check"
    Prompt = "_meta\claude-audit\qwen-prompts\009_wire_check_report.md"
    EditableFiles = @(
        "_meta\claude-audit\009_wire_check_report.md"
    )
    ReadOnlyFiles = @(
        "app\services\plan_runner.py"
    )
}

$ownerReviewTasks = @(
    @{
        Name = "005 owner review test task"
        Prompt = "_meta\claude-audit\qwen-prompts\005_first_safe_test_task.md"
        EditableFiles = @(
            "tests\test_plan_confirmation_service.py",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "app\services\plan_confirmation.py",
            "tests\test_plan_runner.py",
            "tests\test_order_service.py"
        )
    },
    @{
        Name = "007 owner review refactor task"
        Prompt = "_meta\claude-audit\qwen-prompts\007_first_safe_refactor_task.md"
        EditableFiles = @(
            "app\client\config\schedulers_config.py",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "app\client\store\store.py",
            "tests\test_schedulers_config.py"
        )
    },
    @{
        Name = "008 owner review watchlist tests"
        Prompt = "_meta\claude-audit\qwen-prompts\008_next_recommended_task.md"
        EditableFiles = @(
            "tests\test_watchlist_service.py",
            "_meta\claude-audit\qwen-run-log.md"
        )
        ReadOnlyFiles = @(
            "app\services\watchlist.py",
            "tests\test_investment_plans.py",
            "_meta\claude-audit\004_tests_gap_report.md"
        )
    }
)

Assert-PathExists $PythonCommand
Assert-PathExists "_meta\claude-audit\QWEN_AGENT_RUN_ORDER.md"

Write-Host "Aider model: $Model"
Write-Host "Aider command: $AiderCommand"
Write-Host "Working directory: $(Get-Location)"

Require-CleanGit "initial preflight"

if (-not $SkipPreflightTests) {
    Write-Host ""
    Write-Host "=== Preflight tests ===" -ForegroundColor Cyan
    if (-not $DryRun) {
        & $PythonCommand -m unittest discover -q
        if ($LASTEXITCODE -ne 0) {
            throw "Preflight tests failed. Fix them before running Aider unattended."
        }
    }
}

$tasks = @()
$tasks += $safeTasks

if ($IncludeWireCheck) {
    $tasks += $wireCheckTask
}

if ($RunOwnerReviewTasks) {
    Write-Host ""
    Write-Host "WARNING: -RunOwnerReviewTasks includes prompts marked owner-review-required." -ForegroundColor Yellow
    Write-Host "Use this only after reading the safe-run reports."
    $tasks += $ownerReviewTasks
}

foreach ($task in $tasks) {
    Invoke-AiderTask `
        -Name $task.Name `
        -Prompt $task.Prompt `
        -EditableFiles $task.EditableFiles `
        -ReadOnlyFiles $task.ReadOnlyFiles
}

Write-Host ""
Write-Host "Aider prompt batch complete." -ForegroundColor Green
git log --oneline -10
