[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Prompt = '',

    [ValidatePattern('^[a-z0-9]+$')]
    [string]$ProfileName = 'kingsynapse',

    [ValidateRange(1, 90)]
    [int]$MaxTurns = 12
)

$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$integrationRoot = Join-Path $repoRoot 'integrations\hermes'
$profileHome = Join-Path (Join-Path $HOME '.hermes') "profiles\$ProfileName"
$hermesCommand = Join-Path $env:LOCALAPPDATA 'king-synapse\bin\hermes.exe'

if (-not (Test-Path -LiteralPath $hermesCommand)) {
    throw 'The isolated Hermes Agent runtime is missing. Run .\scripts\agent\setup_hermes_synapse.ps1 first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $profileHome 'config.yaml'))) {
    throw "Hermes profile '$ProfileName' is not configured. Run .\scripts\agent\setup_hermes_synapse.ps1 first."
}

$originalHermesHome = $env:HERMES_HOME
$env:HERMES_HOME = $profileHome

Push-Location $integrationRoot
try {
    $chatArgs = @(
        'chat',
        '--toolsets', 'king-synapse',
        '--max-turns', $MaxTurns,
        '--source', 'king-synapse'
    )
    if (-not [string]::IsNullOrWhiteSpace($Prompt)) {
        $chatArgs += @('--query', $Prompt, '--quiet')
    }
    & $hermesCommand @chatArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    if ([string]::IsNullOrEmpty($originalHermesHome)) {
        Remove-Item Env:HERMES_HOME -ErrorAction SilentlyContinue
    }
    else {
        $env:HERMES_HOME = $originalHermesHome
    }
}
