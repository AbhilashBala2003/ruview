$msvcBin = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64"
$wkDir   = (Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
$wkBin   = "$wkDir\x64"
$env:PATH = "C:\Users\91949\.cargo\bin;$msvcBin;$wkBin;$env:PATH"

Write-Host "cargo: $(& 'C:\Users\91949\.cargo\bin\cargo.exe' --version)"
Write-Host "link.exe: $(where.exe link.exe)"
Write-Host "Starting build..."

Set-Location "$PSScriptRoot\v2"
& "C:\Users\91949\.cargo\bin\cargo.exe" build --release --no-default-features -p wifi-densepose-sensing-server
Write-Host "BUILD_EXIT=$LASTEXITCODE"
