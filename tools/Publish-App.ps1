# Publish-App.ps1 - upload an app to the TOPWAY catalog and update the manifest.
#
# Usage:
#   .\Publish-App.ps1 path\to\app.apk
#   .\Publish-App.ps1 path\to\app.apk -Category "מדיה" -Name "My App"
#
# You can also right-click > Run with PowerShell and paste the APK path when asked.

param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string]$Apk,
    [string]$Name,
    [string]$Category,
    [string]$Icon
)

if (-not $Apk) {
    $Apk = Read-Host "Path to the APK file"
}
if (-not (Test-Path $Apk)) {
    Write-Host "File not found: $Apk" -ForegroundColor Red
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyArgs = @("$scriptDir\publish_app.py", $Apk)
if ($Name)     { $pyArgs += @("--name", $Name) }
if ($Category) { $pyArgs += @("--category", $Category) }
if ($Icon)     { $pyArgs += @("--icon", $Icon) }

python @pyArgs
