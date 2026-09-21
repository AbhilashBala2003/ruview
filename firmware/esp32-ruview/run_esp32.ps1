$pyPath = "C:\Users\91949\AppData\Local\Programs\Python\Python313\python.exe"
$mpremote = "$pyPath -m mpremote"

Write-Host "=== RuView ESP32 Monitor ===" -ForegroundColor Cyan
Write-Host "Watching serial output from COM11..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

& $pyPath -m mpremote connect COM11 repl
