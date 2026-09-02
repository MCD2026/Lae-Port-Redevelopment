[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [switch]$Replace,
    [switch]$SkipTerrain,
    [switch]$DryRun,
    [switch]$Publish,
    [switch]$Yes,
    [ValidateRange(800, 4000)]
    [int]$MaxSize = 2000,
    [ValidateRange(50, 95)]
    [int]$Quality = 78
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$siteRoot = Join-Path $repoRoot 'github-pages'
$pythonScript = Join-Path $PSScriptRoot 'rebuild_lae_port_site.py'
$requirements = Join-Path $PSScriptRoot 'requirements.txt'
$temporaryRoot = $null

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

try {
    if (-not (Test-Path -LiteralPath $pythonScript -PathType Leaf)) {
        throw "Rebuild utility is missing: $pythonScript"
    }
    $resolvedSource = (Resolve-Path -LiteralPath $Source).Path
    $resolvedRepo = (Resolve-Path -LiteralPath $repoRoot).Path

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw 'Python 3 is required. Install Python from python.org, then run this command again.'
    }
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($Publish -and -not $gitCommand) {
        throw 'Git is required for -Publish. Install Git for Windows, then run this command again.'
    }

    if ($Publish) {
        Push-Location $resolvedRepo
        try {
            $branch = (git branch --show-current).Trim()
            if ($branch -ne 'main') {
                throw "Publishing must be run from the main branch. Current branch: $branch"
            }
            $pending = git status --porcelain
            if ($pending) {
                throw 'The repository has uncommitted changes. Commit or discard them before publishing.'
            }
            Invoke-Checked { git pull --ff-only origin main } 'Could not update the local main branch from GitHub.'
        }
        finally {
            Pop-Location
        }
    }

    & $pythonCommand.Source -c 'from PIL import Image'
    if ($LASTEXITCODE -ne 0) {
        Invoke-Checked { & $pythonCommand.Source -m pip install -r $requirements } 'Could not install the required Python package.'
    }

    $workingSource = $resolvedSource
    if ([IO.Path]::GetExtension($resolvedSource).Equals('.zip', [StringComparison]::OrdinalIgnoreCase)) {
        $temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("lae-port-rebuild-" + [Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
        Write-Host "Extracting $resolvedSource"
        Expand-Archive -LiteralPath $resolvedSource -DestinationPath $temporaryRoot
        $workingSource = $temporaryRoot
    }

    $arguments = @($pythonScript, $workingSource, $siteRoot, '--max-size', $MaxSize, '--quality', $Quality)
    if ($Replace) { $arguments += '--replace' }
    if ($SkipTerrain) { $arguments += '--skip-terrain' }
    if ($DryRun) { $arguments += '--dry-run' }
    Invoke-Checked { & $pythonCommand.Source @arguments } 'The Lae Port Redevelopment rebuild failed.'

    if ($DryRun) {
        exit 0
    }

    if ($Publish) {
        if (-not $Yes) {
            $confirmation = Read-Host 'Type PUBLISH to update the stakeholder website'
            if ($confirmation -cne 'PUBLISH') {
                throw 'Publishing was cancelled. The rebuilt files remain available locally.'
            }
        }
        Push-Location $resolvedRepo
        try {
            git add -- github-pages/index.html github-pages/3d/index.html github-pages/data/Lae_Port_Photos.js github-pages/map github-pages/terrain
            git diff --cached --quiet
            if ($LASTEXITCODE -eq 0) {
                Write-Host 'No website changes were detected; nothing needs publishing.'
                exit 0
            }
            $message = 'Update Lae Port PhotoMap ' + (Get-Date -Format 'yyyy-MM-dd')
            Invoke-Checked { git commit -m $message } 'Could not create the website update commit.'
            Invoke-Checked { git push origin main } 'Could not push the website update to GitHub.'
            Write-Host ''
            Write-Host 'Published successfully.' -ForegroundColor Green
            Write-Host 'Stakeholder link: https://mcd2026.github.io/Lae-Port-Redevelopment/'
            Write-Host 'GitHub Pages normally refreshes within a few minutes.'
        }
        finally {
            Pop-Location
        }
    }
    else {
        Write-Host ''
        Write-Host 'Rebuild complete. Preview locally with:' -ForegroundColor Green
        Write-Host "python -m http.server 8000 --directory `"$siteRoot`""
        Write-Host 'Then open http://localhost:8000/'
    }
}
finally {
    if ($temporaryRoot -and (Test-Path -LiteralPath $temporaryRoot)) {
        $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        $resolvedTemporary = [IO.Path]::GetFullPath($temporaryRoot)
        if (-not $resolvedTemporary.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove unexpected temporary path: $resolvedTemporary"
        }
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}
