[CmdletBinding()]
param([string]$DockerBin = '', [string]$ProxyUrl = '', [switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$taskProject = Split-Path -Parent $PSScriptRoot
$taskComposeFile = Join-Path $taskProject 'docker-compose.yml'
if ($DockerBin) {
    $taskResolvedBin = [System.IO.Path]::GetFullPath($DockerBin)
    $taskDocker = Join-Path $taskResolvedBin 'docker.exe'
}
else {
    $taskDockerCommand = Get-Command 'docker.exe' -ErrorAction SilentlyContinue
    if (-not $taskDockerCommand) { throw 'docker.exe was not found on PATH; pass -DockerBin with its directory.' }
    $taskDocker = $taskDockerCommand.Source
    $taskResolvedBin = Split-Path -Parent $taskDocker
}
$taskStandaloneCompose = Join-Path $taskResolvedBin 'docker-compose.exe'
if (Test-Path -LiteralPath $taskStandaloneCompose -PathType Leaf) {
    $taskCompose = $taskStandaloneCompose
    $taskComposePrefix = @()
}
else {
    $taskCompose = $taskDocker
    $taskComposePrefix = @('compose')
}
foreach ($taskFile in @($taskDocker, $taskComposeFile)) {
    if (-not (Test-Path -LiteralPath $taskFile -PathType Leaf)) { throw "Missing file: $taskFile" }
}
if ($ProxyUrl) {
    $taskUri = [uri]$ProxyUrl
    if (-not $taskUri.IsAbsoluteUri -or $taskUri.Scheme -notin @('http', 'https') -or -not $taskUri.Host) {
        throw 'ProxyUrl must be an absolute HTTP or HTTPS proxy URL.'
    }
}
$taskPrevious = @{}
foreach ($taskName in @('HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'PATH')) {
    $taskPrevious[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process')
}
Push-Location -LiteralPath $taskProject
try {
    $env:PATH = $taskResolvedBin + ';' + $env:PATH
    if ($ProxyUrl) {
        $env:HTTP_PROXY = $ProxyUrl
        $env:HTTPS_PROXY = $ProxyUrl
        $env:NO_PROXY = 'localhost,127.0.0.1,::1'
    }
    & $taskDocker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop or your existing safe launcher, then retry.' }
    & $taskCompose @taskComposePrefix config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed; .env was not changed.' }
    if (-not $SkipBuild) {
        & $taskCompose @taskComposePrefix --progress plain build api
        if ($LASTEXITCODE -ne 0) { throw 'Image build failed; services were not started.' }
    }
    & $taskCompose @taskComposePrefix up --no-build --pull never -d --wait --wait-timeout 180
    if ($LASTEXITCODE -ne 0) { throw 'Services did not all become healthy; inspect Compose status and logs.' }
    & $taskCompose @taskComposePrefix ps
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Compose service status.' }
}
finally {
    foreach ($taskName in $taskPrevious.Keys) {
        if ($null -eq $taskPrevious[$taskName]) {
            Remove-Item -LiteralPath ("Env:\" + $taskName) -ErrorAction SilentlyContinue
        }
        else {
            [Environment]::SetEnvironmentVariable($taskName, $taskPrevious[$taskName], 'Process')
        }
    }
    Pop-Location
}
