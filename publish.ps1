[CmdletBinding()]
param(
    [string]$Message = "",
    [string[]]$Paths = @(),
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Stop-WithError {
    param([string]$Text)
    Write-Host ""
    Write-Host "ERROR: $Text" -ForegroundColor Red
    exit 1
}

function Confirm-Action {
    param([string]$Prompt)
    $answer = (Read-Host "$Prompt [y/N]").Trim().ToLowerInvariant()
    return (($answer -eq "y") -or ($answer -eq "yes"))
}

function Get-GitText {
    param([string[]]$GitArgs)
    $result = @(& git -C $RepoRoot @GitArgs)
    if ($LASTEXITCODE -ne 0) {
        throw "Git command failed: git $($GitArgs -join ' ')"
    }
    return (($result -join [Environment]::NewLine).Trim())
}

function Test-InScope {
    param(
        [string]$RelativePath,
        [string[]]$Scopes
    )

    if ($Scopes.Count -eq 0) {
        return $true
    }

    $normalizedPath = $RelativePath.Replace('\', '/')
    foreach ($scope in $Scopes) {
        $normalizedScope = $scope.Replace('\', '/').TrimEnd('/')
        if ($normalizedPath.Equals($normalizedScope, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
        if ($normalizedPath.StartsWith($normalizedScope + '/', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

try {
    Push-Location $RepoRoot

    Write-Step "Checking repository"

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Stop-WithError "Git is not installed or is not available in PATH."
    }

    $insideRepo = Get-GitText @('rev-parse', '--is-inside-work-tree')
    if ($insideRepo -ne 'true') {
        Stop-WithError "This script is not inside a Git repository."
    }

    $branch = Get-GitText @('branch', '--show-current')
    if ($branch -ne 'main') {
        Stop-WithError "Expected branch 'main', but current branch is '$branch'."
    }

    $remote = Get-GitText @('remote', 'get-url', 'origin')
    if ($remote -notmatch 'github\.com[/:]Anthony-7k/Python-Basics(?:\.git)?$') {
        Stop-WithError "Unexpected origin remote: $remote"
    }

    Write-Host "Repository : $RepoRoot"
    Write-Host "Branch     : $branch"
    Write-Host "Remote     : $remote"

    $repoFullPath = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
    $repoPrefix = $repoFullPath + '\'
    $resolvedScopes = @()

    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }

        $fullPath = [IO.Path]::GetFullPath((Join-Path $RepoRoot $path))
        if (-not $fullPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-WithError "Path is outside the repository: $path"
        }
        if (-not (Test-Path -LiteralPath $fullPath)) {
            Stop-WithError "Path does not exist: $path"
        }

        $relativePath = $fullPath.Substring($repoPrefix.Length).Replace('\', '/')
        $resolvedScopes += $relativePath
    }

    $resolvedScopes = @($resolvedScopes | Sort-Object -Unique)

    $statusLines = @(& git -C $RepoRoot -c "core.quotepath=false" status --short --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Could not read Git status."
    }

    $ahead = [int](Get-GitText @('rev-list', '--count', 'origin/main..main'))
    $behind = [int](Get-GitText @('rev-list', '--count', 'main..origin/main'))

    if ($behind -gt 0) {
        Stop-WithError "Local main is behind origin/main by $behind commit(s). Pull and review remote changes first."
    }

    if ($statusLines.Count -eq 0) {
        if ($ahead -gt 0) {
            Write-Host "There are $ahead local commit(s) waiting to be pushed." -ForegroundColor Yellow
            if ($DryRun) {
                Write-Host "DRY RUN: no push was performed." -ForegroundColor Yellow
                exit 0
            }
            if (-not (Confirm-Action "Push pending commit(s) to origin/main now?")) {
                Write-Host "Canceled. Nothing was pushed."
                exit 0
            }
            & git -C $RepoRoot push origin main
            if ($LASTEXITCODE -ne 0) {
                Stop-WithError "Push failed. The local commit is still safe on this computer."
            }
            Write-Host "SUCCESS: pending commit(s) were pushed to origin/main." -ForegroundColor Green
            exit 0
        }

        Write-Host "No changes found. The working tree is clean." -ForegroundColor Green
        exit 0
    }

    Write-Step "Changes detected"
    $statusLines | ForEach-Object { Write-Host $_ }

    $candidateFiles = @()
    $candidateFiles += @(& git -C $RepoRoot -c "core.quotepath=false" diff --name-only)
    $candidateFiles += @(& git -C $RepoRoot -c "core.quotepath=false" diff --cached --name-only)
    $candidateFiles += @(& git -C $RepoRoot -c "core.quotepath=false" ls-files --others --exclude-standard)
    $candidateFiles = @($candidateFiles | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)

    if ($resolvedScopes.Count -gt 0) {
        $candidateFiles = @($candidateFiles | Where-Object { Test-InScope $_ $resolvedScopes })
        Write-Host "Selected scope: $($resolvedScopes -join ', ')"
    }

    if ($candidateFiles.Count -eq 0) {
        Stop-WithError "No changed files matched the selected scope."
    }

    Write-Step "Safety checks"

    $sensitiveFiles = New-Object System.Collections.Generic.List[string]
    $largeFiles = New-Object System.Collections.Generic.List[string]
    $secretContentFiles = New-Object System.Collections.Generic.List[string]
    $textExtensions = @('.py', '.http', '.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.ps1')
    $secretPatterns = @(
        '(?i)-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----',
        '(?i)(api[_-]?key|access[_-]?token|secret|password)\s*=\s*"[^"]{8,}"',
        "(?i)(api[_-]?key|access[_-]?token|secret|password)\s*=\s*'[^']{8,}'",
        '(?i)authorization\s*:\s*bearer\s+[A-Za-z0-9._-]{12,}'
    )

    foreach ($relativePath in $candidateFiles) {
        $normalizedPath = $relativePath.Replace('\', '/')
        $fullPath = Join-Path $RepoRoot $normalizedPath

        if ($normalizedPath -match '(?i)(^|/)\.env($|\.)' -or
            $normalizedPath -match '(?i)\.(pem|key|p12|pfx)$' -or
            $normalizedPath -match '(?i)(^|/)id_(rsa|ed25519)$') {
            $sensitiveFiles.Add($normalizedPath)
        }

        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $item = Get-Item -LiteralPath $fullPath
            if ($item.Length -gt 90MB) {
                $largeFiles.Add("$normalizedPath ($([math]::Round($item.Length / 1MB, 2)) MB)")
            }

            $extension = [IO.Path]::GetExtension($fullPath).ToLowerInvariant()
            if ($textExtensions -contains $extension) {
                if (Select-String -LiteralPath $fullPath -Pattern $secretPatterns -Quiet -ErrorAction SilentlyContinue) {
                    $secretContentFiles.Add($normalizedPath)
                }
            }
        }
    }

    if ($sensitiveFiles.Count -gt 0) {
        Write-Host "Potentially sensitive filenames:" -ForegroundColor Red
        $sensitiveFiles | ForEach-Object { Write-Host "  $_" }
        Stop-WithError "Review or ignore these files before publishing."
    }

    if ($secretContentFiles.Count -gt 0) {
        Write-Host "Files containing possible secrets:" -ForegroundColor Red
        $secretContentFiles | ForEach-Object { Write-Host "  $_" }
        Stop-WithError "Review the listed files before publishing."
    }

    if ($largeFiles.Count -gt 0) {
        Write-Host "Files larger than 90 MB:" -ForegroundColor Red
        $largeFiles | ForEach-Object { Write-Host "  $_" }
        Stop-WithError "Large files were not staged. Use Git LFS or remove them."
    }

    Write-Host "Safety checks passed." -ForegroundColor Green

    if ($DryRun) {
        Write-Host ""
        Write-Host "DRY RUN COMPLETE: no files were staged, committed, or pushed." -ForegroundColor Yellow
        exit 0
    }

    if ($resolvedScopes.Count -eq 0) {
        if (-not (Confirm-Action "Stage ALL changes listed above?")) {
            Write-Host "Canceled. Nothing was staged."
            exit 0
        }
        & git -C $RepoRoot add -A
    }
    else {
        & git -C $RepoRoot add -A -- @resolvedScopes
    }

    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "git add failed."
    }

    $stagedFiles = @(& git -C $RepoRoot -c "core.quotepath=false" diff --cached --name-only)
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Could not inspect staged files."
    }

    if ($resolvedScopes.Count -gt 0) {
        $outsideScope = @($stagedFiles | Where-Object { -not (Test-InScope $_ $resolvedScopes) })
        if ($outsideScope.Count -gt 0) {
            Write-Host "Already-staged files outside the selected scope:" -ForegroundColor Red
            $outsideScope | ForEach-Object { Write-Host "  $_" }
            Stop-WithError "Commit scope is mixed. Review the staged files before continuing."
        }
    }

    if ($stagedFiles.Count -eq 0) {
        Stop-WithError "Nothing is staged for commit."
    }

    Write-Step "Staged summary"
    & git -C $RepoRoot -c "core.quotepath=false" status --short
    & git -C $RepoRoot -c "core.quotepath=false" diff --cached --stat

    if ([string]::IsNullOrWhiteSpace($Message)) {
        $Message = Read-Host "Enter a commit message"
    }

    if ([string]::IsNullOrWhiteSpace($Message)) {
        Stop-WithError "Commit message cannot be empty."
    }

    if (-not (Confirm-Action "Create commit '$Message'?")) {
        Write-Host "Canceled. Files remain staged, but no commit was created."
        exit 0
    }

    & git -C $RepoRoot commit -m $Message
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Commit failed."
    }

    if (-not (Confirm-Action "Push the new commit to origin/main now?")) {
        Write-Host "Commit created locally. It was not pushed. Run this script again to push it later." -ForegroundColor Yellow
        exit 0
    }

    & git -C $RepoRoot push origin main
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "Push failed. The local commit is still safe on this computer."
    }

    Write-Step "Final status"
    & git -C $RepoRoot status
    Write-Host ""
    Write-Host "SUCCESS: changes were committed and pushed to origin/main." -ForegroundColor Green
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
