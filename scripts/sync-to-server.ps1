param(
    [switch]$HeadOnly,
    [switch]$DryRun,
    [switch]$SkipRemoteTests,
    [string]$Server = "semenkohome",
    [string]$RemoteProject = "/home/feelwent/projects/Tbot",
    [string]$ContainerName = "tbot",
    [string]$ImageName = "tbot-runtime:py312",
    [string]$ApiUrl = "http://127.0.0.1:8000/",
    [int]$StartupWaitSeconds = 45,
    [string]$SshPath = "$env:WINDIR\System32\OpenSSH\ssh.exe",
    [string]$ScpPath = "$env:WINDIR\System32\OpenSSH\scp.exe"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )

    Write-Host "> $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Get-GitValue {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $value = & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed"
    }
    return ($value | Select-Object -First 1)
}

$Branch = Get-GitValue @("branch", "--show-current")
$HeadSha = Get-GitValue @("rev-parse", "HEAD")
$HeadShort = Get-GitValue @("rev-parse", "--short", "HEAD")
$DirtyFiles = @(& git status --porcelain=v1)
if ($LASTEXITCODE -ne 0) {
    throw "git status failed"
}

Write-Host "Local repo: $RepoRoot"
Write-Host "Branch: $Branch"
Write-Host "Deploy source: HEAD $HeadShort"

if ($DirtyFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "Local working tree has changes that are NOT part of HEAD:"
    $DirtyFiles | ForEach-Object { Write-Host "  $_" }
    if (-not $HeadOnly) {
        throw "Refusing to deploy a dirty working tree unless -HeadOnly is specified."
    }
    Write-Host "Proceeding with committed HEAD only because -HeadOnly was specified."
}

if ($RemoteProject -ne "/home/feelwent/projects/Tbot") {
    throw "RemoteProject must be /home/feelwent/projects/Tbot for this deploy script."
}
if (-not (Test-Path -LiteralPath $SshPath)) {
    throw "ssh.exe not found at $SshPath"
}
if (-not (Test-Path -LiteralPath $ScpPath)) {
    throw "scp.exe not found at $ScpPath"
}

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) "tbot-deploy-$Stamp"
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
$BundlePath = Join-Path $TempDir "tbot-$HeadShort.bundle"
$RemoteBundle = "/tmp/tbot-deploy-$Stamp.bundle"

try {
    Invoke-Native git "bundle" "create" $BundlePath "HEAD"

    Write-Host ""
    Write-Host "Deploy target: ${Server}:$RemoteProject"
    Write-Host "Remote bundle: $RemoteBundle"
    Write-Host "Container: $ContainerName"
    Write-Host "Image: $ImageName"
    Write-Host "Backup path: ${RemoteProject}.backup-$Stamp"
    Write-Host "SSH: $SshPath"
    Write-Host "SCP: $ScpPath"

    if ($DryRun) {
        Write-Host ""
        Write-Host "Dry run complete. No remote changes were made."
        return
    }

    Invoke-Native $ScpPath $BundlePath "${Server}:$RemoteBundle"

    $RemoteScript = @'
set -Eeuo pipefail

project_dir="$1"
bundle_path="$2"
container_name="$3"
image_name="$4"
stamp="$5"
api_url="$6"
startup_wait="$7"
skip_tests="$8"

if [[ "$project_dir" != "/home/feelwent/projects/Tbot" ]]; then
  echo "Refusing unexpected project_dir: $project_dir" >&2
  exit 2
fi
if [[ ! -d "$project_dir/.git" ]]; then
  echo "Remote project git repo is missing: $project_dir" >&2
  exit 2
fi
if [[ ! -f "$bundle_path" ]]; then
  echo "Bundle is missing: $bundle_path" >&2
  exit 2
fi

backup_dir="${project_dir}.backup-${stamp}"
failed_dir="${project_dir}.failed-${stamp}"
rollback_image="${image_name}-rollback-${stamp}"

run_container() {
  local image="$1"
  docker run -d \
    --name "$container_name" \
    --restart unless-stopped \
    --network host \
    -v "$project_dir:/workspace" \
    -w /workspace \
    "$image" \
    bash -lc 'if [ -d /app ]; then mv /app /image_app; fi; python app/run.py'
}

redacted_logs() {
  docker logs --tail 80 "$container_name" 2>&1 \
    | sed -E 's#/bot[0-9]+:[A-Za-z0-9_-]+#/bot<REDACTED>#g' || true
}

rollback() {
  local line="$1"
  set +e
  echo "Deploy failed at remote script line $line. Rolling back." >&2
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  if [[ -d "$backup_dir" ]]; then
    if [[ -d "$project_dir" ]]; then
      mv "$project_dir" "$failed_dir"
    fi
    cp -a "$backup_dir" "$project_dir"
  fi
  if docker image inspect "$rollback_image" >/dev/null 2>&1; then
    run_container "$rollback_image" >/dev/null || true
  elif [[ -d "$project_dir" ]]; then
    docker build -t "$image_name" "$project_dir" >/dev/null 2>&1 && run_container "$image_name" >/dev/null || true
  fi
  echo "Rollback attempted. Backup: $backup_dir" >&2
  redacted_logs >&2
  exit 1
}

echo "Remote host: $(hostname)"
echo "Remote project: $project_dir"
echo "Backing up current project to $backup_dir"
cp -a "$project_dir" "$backup_dir"

if docker image inspect "$image_name" >/dev/null 2>&1; then
  echo "Tagging current image as $rollback_image"
  docker tag "$image_name" "$rollback_image"
fi

trap 'rollback $LINENO' ERR

echo "Stopping current container if present"
docker rm -f "$container_name" >/dev/null 2>&1 || true

cd "$project_dir"
echo "Fetching laptop HEAD from bundle"
git fetch "$bundle_path" HEAD
new_sha="$(git rev-parse FETCH_HEAD)"
echo "Resetting server working tree to $new_sha"
git reset --hard FETCH_HEAD
git clean -fd

for runtime_path in .env database.db database.db-wal database.db-shm users.json .runtime data/users user_strategies; do
  if [[ ! -e "$project_dir/$runtime_path" && -e "$backup_dir/$runtime_path" ]]; then
    echo "Restoring runtime path: $runtime_path"
    mkdir -p "$(dirname "$project_dir/$runtime_path")"
    cp -a "$backup_dir/$runtime_path" "$project_dir/$runtime_path"
  fi
done

if [[ ! -f "$project_dir/.env" ]]; then
  echo "Missing .env after deploy; cannot start live bot." >&2
  exit 3
fi

echo "Building $image_name"
docker build -t "$image_name" "$project_dir"

if [[ "$skip_tests" != "true" ]]; then
  echo "Running remote tests in disposable container"
  docker run --rm \
    --network host \
    -v "$project_dir:/workspace" \
    -w /workspace \
    "$image_name" \
    bash -lc 'python -m pip install -q -r requirements-dev.txt && python -m unittest discover -q'
else
  echo "Skipping remote tests by request"
fi

echo "Starting $container_name"
run_container "$image_name" >/dev/null

echo "Waiting for API: $api_url"
ok="false"
for _ in $(seq 1 "$startup_wait"); do
  if curl -fsS --max-time 2 "$api_url" | grep -q "Investor Terminal"; then
    ok="true"
    break
  fi
  sleep 1
done
if [[ "$ok" != "true" ]]; then
  echo "API validation failed: $api_url" >&2
  redacted_logs >&2
  exit 4
fi

echo "Container status:"
docker ps --filter "name=$container_name" --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
echo "Server git status:"
git status --short --branch
echo "Recent redacted logs:"
redacted_logs

trap - ERR
rm -f "$bundle_path"
echo "Deploy completed: $new_sha"
'@

    $SkipTestsArg = if ($SkipRemoteTests) { "true" } else { "false" }
    $SshArgs = @(
        $Server,
        "bash",
        "-s",
        "--",
        $RemoteProject,
        $RemoteBundle,
        $ContainerName,
        $ImageName,
        $Stamp,
        $ApiUrl,
        [string]$StartupWaitSeconds,
        $SkipTestsArg
    )

    Write-Host ""
    Write-Host "> $SshPath $($SshArgs -join ' ')"
    $RemoteScript | & $SshPath @SshArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Remote deploy failed with exit code $LASTEXITCODE"
    }
}
finally {
    if (Test-Path -LiteralPath $TempDir) {
        Remove-Item -LiteralPath $TempDir -Recurse -Force
    }
}
