param(
    [ValidateSet("dashboard", "hud")]
    [string]$Page = "dashboard",
    [int]$Port = 5000
)

$url = if ($Page -eq "hud") { "http://localhost:$Port/hud" } else { "http://localhost:$Port/" }
$size = if ($Page -eq "hud") { "420,160" } else { "1280,900" }

$browserPaths = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$browser = $browserPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $browser) {
    Write-Error "No Chrome or Edge install found. Install one, or edit this script with your browser's path."
    exit 1
}

# --app= opens a chromeless window (no tabs, address bar, or toolbar) pointed
# at the given URL - just the page content plus minimize/close controls.
& $browser --app=$url --window-size=$size
