# ==========================================
# Allow-Hominsu-SRS-RTMP.ps1
# Opens TCP Port 1935 for SRS RTMP Server
# ==========================================

$RuleName = "Hominsu SRS RTMP"
$Port = 1935

# Check if the firewall rule already exists
$ExistingRule = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue

if ($ExistingRule) {
    Write-Host "Firewall rule '$RuleName' already exists." -ForegroundColor Yellow
}
else {
    New-NetFirewallRule `
        -DisplayName $RuleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -Profile Private

    Write-Host "Firewall rule created successfully!" -ForegroundColor Green
}

# Display the rule
Get-NetFirewallRule -DisplayName $RuleName | Get-NetFirewallPortFilter | Format-Table -AutoSize