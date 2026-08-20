[CmdletBinding()]
param(
    [switch]$ConfigureFirewall,
    [switch]$InstallDockerDesktop
)

$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $RepoDir "docker-compose.local.yml"
$EnvFile = Join-Path $RepoDir ".env"
$DockerCommand = $null

function Get-LanHostIp {
    if (Test-Path -LiteralPath $EnvFile) {
        $line = Select-String -LiteralPath $EnvFile -Pattern '^\s*LAN_HOST_IP\s*=\s*(.+?)\s*$' |
            Select-Object -First 1
        if ($line) {
            $value = $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
            if ($value) { return $value }
        }
    }

    $configuration = Get-NetIPConfiguration |
        Where-Object { $_.NetAdapter.Status -eq "Up" -and $_.IPv4DefaultGateway } |
        Select-Object -First 1
    if ($configuration -and $configuration.IPv4Address) {
        return $configuration.IPv4Address.IPAddress
    }

    return "127.0.0.1"
}

function Start-DockerDesktopIfInstalled {
    $desktopPath = Find-DockerDesktopPath
    if (-not $desktopPath) { return $false }

    Write-Host "Docker CLI is not ready. Starting Docker Desktop..."
    Start-Process -FilePath $desktopPath -WindowStyle Hidden
    return $true
}

function Find-DockerDesktopPath {
    $candidates = @(
        (Join-Path ${env:ProgramFiles} "Docker\Docker\Docker Desktop.exe"),
        (Join-Path ${env:ProgramW6432} "Docker\Docker\Docker Desktop.exe"),
        (Join-Path ${env:LocalAppData} "Programs\Docker Desktop\Docker Desktop.exe"),
        (Join-Path ${env:LocalAppData} "Docker\Docker Desktop.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    return $null
}

function Resolve-DockerCommand {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) { return $docker.Source }

    $dockerExe = Join-Path ${env:ProgramFiles} "Docker\Docker\resources\bin\docker.exe"
    if (Test-Path -LiteralPath $dockerExe) { return $dockerExe }

    return $null
}

function Add-DockerToolsToProcessPath {
    $dockerTools = Join-Path ${env:ProgramFiles} "Docker\Docker\resources\bin"
    if (Test-Path -LiteralPath $dockerTools) {
        $pathEntries = $env:Path -split ';'
        if ($pathEntries -notcontains $dockerTools) {
            $env:Path = "$dockerTools;$env:Path"
        }
    }
}

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "docker-compose.local.yml was not found at $ComposeFile"
}

Add-DockerToolsToProcessPath
$DockerCommand = Resolve-DockerCommand
$DockerReady = $false
if ($DockerCommand) {
    try {
        & $DockerCommand version 2>$null | Out-Null
        $DockerReady = ($LASTEXITCODE -eq 0)
    } catch {
        $DockerReady = $false
    }
}

if (-not $DockerReady) {
    if ($InstallDockerDesktop -and -not (Find-DockerDesktopPath)) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            throw "winget is unavailable; install Docker Desktop manually from https://www.docker.com/products/docker-desktop/"
        }
        Write-Host "Installing Docker Desktop with winget..."
        & winget install --id Docker.DockerDesktop --exact --source winget --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "Docker Desktop installation failed."
        }
    }

    $desktopStarted = Start-DockerDesktopIfInstalled
    if (-not $desktopStarted -and -not $DockerCommand) {
        throw "Docker is unavailable. Install Docker Desktop, enable WSL 2 integration, and reopen PowerShell."
    }

    $deadline = (Get-Date).AddSeconds(90)
    do {
        Start-Sleep -Seconds 2
        $DockerCommand = Resolve-DockerCommand
        if ($DockerCommand) {
            try {
                $versionOutput = & $DockerCommand version 2>$null
                if ($LASTEXITCODE -eq 0) { break }
            } catch {
                continue
            }
        }
    } while ((Get-Date) -lt $deadline)
}

if (-not $DockerCommand) {
    throw "Docker is unavailable. Install Docker Desktop, enable WSL 2 integration, and reopen PowerShell."
}

try {
    & $DockerCommand version
    if ($LASTEXITCODE -ne 0) {
        throw "Docker engine returned a non-zero status."
    }
} catch {
    throw "Docker Desktop is installed but the Docker engine is not running. Start Docker Desktop and retry."
}

& $DockerCommand compose version
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose is unavailable. Enable the Docker Compose plugin/Desktop integration."
}

$LanHostIp = Get-LanHostIp
Write-Host "LAN host IP: $LanHostIp"
Write-Host "Starting PostgreSQL and SRS..."

& $DockerCommand compose -f $ComposeFile up -d postgres srs
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed to start the media stack."
}

$SrsRunning = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    $state = & $DockerCommand inspect -f '{{.State.Running}}' hominsu-srs 2>$null
    if ($state -eq "true") {
        $SrsRunning = $true
        break
    }
    Start-Sleep -Seconds 1
}

if (-not $SrsRunning) {
    & $DockerCommand compose -f $ComposeFile logs --tail=100 srs
    throw "hominsu-srs did not become ready."
}

& $DockerCommand compose -f $ComposeFile ps
Write-Host "Published SRS ports:"
& $DockerCommand port hominsu-srs

$RtmpMapping = & $DockerCommand port hominsu-srs 1935/tcp 2>$null
if (-not $RtmpMapping) {
    & $DockerCommand compose -f $ComposeFile logs --tail=100 srs
    throw "SRS is running, but port 1935 is not published."
}

if ($ConfigureFirewall) {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run PowerShell as Administrator when using -ConfigureFirewall."
    }

    $firewallPorts = @(
        @{ Name = "Hominsu SRS RTMP 1935"; Port = 1935 },
        @{ Name = "Hominsu SRS HLS 8080"; Port = 8080 },
        @{ Name = "Hominsu Nginx 8088"; Port = 8088 }
    )
    foreach ($firewallPort in $firewallPorts) {
        if (-not (Get-NetFirewallRule -DisplayName $firewallPort.Name -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $firewallPort.Name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $firewallPort.Port -Profile Private | Out-Null
        }
    }
    Write-Host "Windows Firewall rules configured for RTMP, HLS, and Nginx."
}

$tcpTest = Test-NetConnection -ComputerName 127.0.0.1 -Port 1935 -WarningAction SilentlyContinue
if (-not $tcpTest.TcpTestSucceeded) {
    & $DockerCommand compose -f $ComposeFile logs --tail=100 srs
    throw "Windows cannot connect to local RTMP port 1935. Check Docker port publishing and SRS logs."
}

Write-Host ""
Write-Host "SRS is listening on Windows port 1935."
Write-Host "Insta360 RTMP URL: rtmp://${LanHostIp}:1935/live/insta-001"
Write-Host "Direct HLS URL:    http://${LanHostIp}:8080/live/insta-001.m3u8"
Write-Host ""
Write-Host "Next check: Test-NetConnection $LanHostIp -Port 1935"
