[CmdletBinding()]
param(
    [ValidatePattern('^[a-z0-9]+$')]
    [string]$ProfileName = 'kingsynapse',

    [string]$PacketPath = '',

    [string]$DatabasePath = '',

    [switch]$Release,

    [switch]$SkipBuild,

    [switch]$RefreshHermesRuntime
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$integrationRoot = Join-Path $repoRoot 'integrations\hermes'
$hermesTag = 'v2026.7.7.2'
$runtimeRoot = Join-Path $env:LOCALAPPDATA 'king-synapse'
$runtimeToolDir = Join-Path $runtimeRoot 'uv-tools'
$runtimeBinDir = Join-Path $runtimeRoot 'bin'
$hermesCommand = Join-Path $runtimeBinDir 'hermes.exe'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required to install the isolated Hermes Agent runtime.'
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw 'Cargo is not installed or is not available on PATH.'
}

$originalUvToolDir = $env:UV_TOOL_DIR
$originalUvToolBinDir = $env:UV_TOOL_BIN_DIR
$env:UV_TOOL_DIR = $runtimeToolDir
$env:UV_TOOL_BIN_DIR = $runtimeBinDir

if ($RefreshHermesRuntime -or -not (Test-Path -LiteralPath $hermesCommand)) {
    & uv tool install "hermes-agent[mcp] @ git+https://github.com/NousResearch/hermes-agent.git@$hermesTag" --python 3.13 --force
    if ($LASTEXITCODE -ne 0) {
        throw "Hermes Agent runtime installation failed with exit code $LASTEXITCODE"
    }
}
if (-not (Test-Path -LiteralPath $hermesCommand)) {
    throw "Hermes Agent runtime not found: $hermesCommand"
}
$hermesVersion = @(& $hermesCommand --version 2>&1)
if (-not ($hermesVersion -match 'Hermes Agent v0\.18\.2')) {
    throw "Unexpected Hermes Agent runtime. Expected v0.18.2 at $hermesCommand"
}

if ([string]::IsNullOrWhiteSpace($PacketPath)) {
    $PacketPath = Join-Path $repoRoot 'crates\eval\datasets\phase8\phase8_lcn_v0_1_private_work_task_company_introduction_retrieval_packet_v1.json'
}
$PacketPath = (Resolve-Path -LiteralPath $PacketPath).Path

$buildProfile = if ($Release) { 'release' } else { 'debug' }
$binaryName = if ($IsWindows -or $env:OS -eq 'Windows_NT') { 'synapse-mcp.exe' } else { 'synapse-mcp' }
$binaryPath = Join-Path $repoRoot "target\$buildProfile\$binaryName"

if (-not $SkipBuild) {
    Push-Location $repoRoot
    try {
        $cargoArgs = @('build', '-p', 'synapse-mcp')
        if ($Release) {
            $cargoArgs += '--release'
        }
        & cargo @cargoArgs
        if ($LASTEXITCODE -ne 0) {
            throw "cargo build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
if (-not (Test-Path -LiteralPath $binaryPath)) {
    throw "King Synapse MCP binary not found: $binaryPath"
}
$binaryPath = (Resolve-Path -LiteralPath $binaryPath).Path

$hermesRoot = Join-Path $HOME '.hermes'
$profileHome = Join-Path $hermesRoot "profiles\$ProfileName"
$originalHermesHome = $env:HERMES_HOME

try {
    Remove-Item Env:HERMES_HOME -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $profileHome)) {
        & $hermesCommand profile create $ProfileName --no-alias --no-skills
        if ($LASTEXITCODE -ne 0) {
            throw "Hermes profile creation failed with exit code $LASTEXITCODE"
        }
        foreach ($fileName in @('config.yaml', '.env')) {
            $sourcePath = Join-Path $hermesRoot $fileName
            if (Test-Path -LiteralPath $sourcePath) {
                Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $profileHome $fileName) -Force
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($DatabasePath)) {
        $DatabasePath = Join-Path $profileHome 'king-synapse.sqlite'
    }
    $DatabasePath = [IO.Path]::GetFullPath($DatabasePath)

    Copy-Item -LiteralPath (Join-Path $integrationRoot 'SOUL.md') -Destination (Join-Path $profileHome 'SOUL.md') -Force
    $env:HERMES_HOME = $profileHome

    & $hermesCommand mcp remove king-synapse 2>$null | Out-Null
    $mcpArgs = @(
        'mcp', 'add', 'king-synapse',
        '--command', $binaryPath,
        '--env',
        'KING_SYNAPSE_MCP_TOOL_PROFILE=agent_read_only',
        "KING_SYNAPSE_ENTERPRISE_PACKET=$PacketPath",
        "KING_SYNAPSE_DB=$DatabasePath"
    )
    @('Y') | & $hermesCommand @mcpArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Hermes MCP configuration failed with exit code $LASTEXITCODE"
    }

    & $hermesCommand mcp test king-synapse
    if ($LASTEXITCODE -ne 0) {
        throw "Hermes MCP health check failed with exit code $LASTEXITCODE"
    }

    Write-Output ''
    Write-Output "King Synapse Hermes profile is ready: $profileHome"
    Write-Output "Start chat: .\scripts\agent\synapse_chat.ps1"
    Write-Output "One question: .\scripts\agent\synapse_chat.ps1 -Prompt '公司套餐多少钱？'"
}
finally {
    if ([string]::IsNullOrEmpty($originalHermesHome)) {
        Remove-Item Env:HERMES_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:HERMES_HOME = $originalHermesHome
    }
    if ([string]::IsNullOrEmpty($originalUvToolDir)) {
        Remove-Item Env:UV_TOOL_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:UV_TOOL_DIR = $originalUvToolDir
    }
    if ([string]::IsNullOrEmpty($originalUvToolBinDir)) {
        Remove-Item Env:UV_TOOL_BIN_DIR -ErrorAction SilentlyContinue
    }
    else {
        $env:UV_TOOL_BIN_DIR = $originalUvToolBinDir
    }
}
