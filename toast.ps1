param(
    [string]$Title = "Trae",
    [string]$Text = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$icon = New-Object System.Windows.Forms.NotifyIcon
$icon.Icon = [System.Drawing.SystemIcons]::Information
$icon.Visible = $true
$icon.BalloonTipTitle = $Title
$icon.BalloonTipText = $Text
$icon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Warning
$icon.ShowBalloonTip(10000)
Start-Sleep -Seconds 8
$icon.Visible = $false
$icon.Dispose()
