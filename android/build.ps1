# =====================================================================
#  build.ps1 — Compila BioAccessMobile.apk SIN Android Studio / Gradle
#  Requiere: JDK 21 (java/javac/keytool) + Android SDK (build-tools, platform)
#
#  Uso:   powershell -ExecutionPolicy Bypass -File android\build.ps1
#  Salida: dist\BioAccessMobile.apk
# =====================================================================
param(
    [string]$Out = "",
    [switch]$SkipSign
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# ---------------- rutas ----------------
$Root = Split-Path -Parent $PSScriptRoot
if (-not $Out) { $Out = Join-Path $Root "dist\BioAccessMobile.apk" }

$Sdk = $env:ANDROID_HOME
if (-not $Sdk -or -not (Test-Path $Sdk)) { $Sdk = "$env:LOCALAPPDATA\Android\Sdk" }
if (-not (Test-Path $Sdk)) { throw "No se encontró el Android SDK. Define ANDROID_HOME." }

$BuildTools = Get-ChildItem "$Sdk\build-tools" -Directory -ErrorAction Stop |
              Sort-Object { [version]($_.Name) } -Descending | Select-Object -First 1
if (-not $BuildTools) { throw "No hay build-tools instalados en $Sdk\build-tools" }

$Aapt2     = Join-Path $BuildTools.FullName "aapt2.exe"
$D8        = Join-Path $BuildTools.FullName "d8.bat"
$Zipalign  = Join-Path $BuildTools.FullName "zipalign.exe"
$Apksigner = Join-Path $BuildTools.FullName "apksigner.bat"
foreach ($exe in @($Aapt2, $D8, $Zipalign, $Apksigner)) {
    if (-not (Test-Path $exe)) { throw "Falta herramienta: $exe" }
}

$AndroidJar = Get-ChildItem "$Sdk\platforms" -Directory |
              Where-Object { Test-Path (Join-Path $_.FullName "android.jar") } |
              Sort-Object {
                  $v = ($_.Name -replace '[^0-9\.]', '')
                  if ($v -notmatch '\.') { $v = "$v.0" }
                  [version]$v
              } -Descending |
              Select-Object -First 1 | ForEach-Object { Join-Path $_.FullName "android.jar" }
if (-not $AndroidJar) { throw "No hay platforms con android.jar en $Sdk\platforms" }

$JavaBin = Split-Path (Get-Command java.exe).Source -Parent
$Javac   = Join-Path $JavaBin "javac.exe"
$Keytool = Join-Path $JavaBin "keytool.exe"

$App       = Join-Path $PSScriptRoot "app\src\main"
$Manifest  = Join-Path $App "AndroidManifest.xml"
$ResDir    = Join-Path $App "res"
$JavaDir   = Join-Path $App "java"
$AssetsDir = Join-Path $App "assets"
$BuildDir  = Join-Path $PSScriptRoot "build"
$GenDir    = Join-Path $BuildDir "gen"
$ClassesDir= Join-Path $BuildDir "classes"
$DexDir    = Join-Path $BuildDir "dex"
$KsPath    = Join-Path $PSScriptRoot "bioaccess.keystore"
$KsPass    = "bioaccess"
$KsAlias   = "bioaccess"

Write-Host "=== BioAccess APK builder ===" -ForegroundColor Cyan
Write-Host "  build-tools : $($BuildTools.Name)"
Write-Host "  android.jar : $AndroidJar"
Write-Host "  salida      : $Out"

# ---------------- limpieza ----------------
foreach ($d in @($BuildDir)) { if (Test-Path $d) { Remove-Item $d -Recurse -Force } }
New-Item -ItemType Directory -Force -Path $GenDir, $ClassesDir, $DexDir, (Split-Path $Out -Parent) | Out-Null

# ---------------- assets (interfaz móvil compartida) ----------------
$SrcMobile = Join-Path $Root "mobile"
if (-not (Test-Path $SrcMobile)) { throw "No existe la carpeta mobile\ con la interfaz" }
$AssetsMobile = Join-Path $AssetsDir "mobile"
if (Test-Path $AssetsMobile) { Remove-Item $AssetsMobile -Recurse -Force }
New-Item -ItemType Directory -Force -Path $AssetsMobile | Out-Null
Copy-Item "$SrcMobile\*" $AssetsMobile -Recurse -Force
Write-Host "[1/7] assets copiados ($((Get-ChildItem $AssetsMobile -Recurse -File).Count) archivos)"

# ---------------- recursos ----------------
$ResZip = Join-Path $BuildDir "res.zip"
& $Aapt2 compile --dir $ResDir -o $ResZip
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile falló" }
Write-Host "[2/7] recursos compilados"

$BaseApk = Join-Path $BuildDir "base.apk"
& $Aapt2 link -o $BaseApk -I $AndroidJar --manifest $Manifest `
    -R $ResZip --java $GenDir --auto-add-overlay -A $AssetsDir `
    --min-sdk-version 28 --target-sdk-version 35 `
    --version-code 1 --version-name "2.0.1"
if ($LASTEXITCODE -ne 0) { throw "aapt2 link falló" }
Write-Host "[3/7] APK base enlazada (manifest + recursos + assets)"

# ---------------- java -> class ----------------
$Sources = @(Get-ChildItem $JavaDir -Recurse -Filter *.java | ForEach-Object { $_.FullName })
$RJava = Get-ChildItem $GenDir -Recurse -Filter R.java | ForEach-Object { $_.FullName }
if (-not $Sources) { throw "No hay fuentes .java" }

$ZxingJar = Join-Path $PSScriptRoot "libs\core-3.5.3.jar"
if (-not (Test-Path $ZxingJar)) { throw "Falta $ZxingJar" }

& $Javac -encoding UTF-8 -nowarn -source 8 -target 8 `
    -classpath "$AndroidJar;$ZxingJar" -d $ClassesDir ($Sources + $RJava)
if ($LASTEXITCODE -ne 0) { throw "javac falló" }
Write-Host "[4/7] clases Java compiladas ($($Sources.Count) fuentes)"

# ---------------- dex ----------------
$ClassFiles = @(Get-ChildItem $ClassesDir -Recurse -Filter *.class | ForEach-Object { $_.FullName })
& $D8 --release --min-api 28 --lib $AndroidJar --output $DexDir @ClassFiles $ZxingJar
if ($LASTEXITCODE -ne 0) { throw "d8 falló" }
$DexFile = Join-Path $DexDir "classes.dex"
if (-not (Test-Path $DexFile)) { throw "d8 no generó classes.dex" }
Write-Host "[5/7] dex generado ($([math]::Round((Get-Item $DexFile).Length/1KB,1)) KB)"

# ---------------- unir dex al apk ----------------
# Se empaqueta con Python (zip estándar): el ZipFile de PowerShell dejaba
# el APK en un estado que AssetManager no podía leer (assets invisibles).
$Unsigned = Join-Path $BuildDir "unsigned.apk"
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = "C:\Python314\python.exe" }
$Packer = Join-Path $PSScriptRoot "..\tools\pack_apk.py"
& $Python $Packer $BaseApk $DexFile $Unsigned
if ($LASTEXITCODE -ne 0) { throw "pack_apk falló" }

$Aligned = Join-Path $BuildDir "aligned.apk"
& $Zipalign -f 4 $Unsigned $Aligned
if ($LASTEXITCODE -ne 0) { throw "zipalign falló" }
Write-Host "[6/7] APK alineada"

# ---------------- firma ----------------
if (-not $SkipSign) {
    if (-not (Test-Path $KsPath)) {
        Write-Host "      generando keystore de desarrollo..."
        & $Keytool -genkeypair -v -keystore $KsPath -alias $KsAlias `
            -storepass $KsPass -keypass $KsPass -keyalg RSA -keysize 2048 -validity 10000 `
            -dname "CN=BioAccess, OU=Mobile, O=BioAccess, L=MX, ST=MX, C=MX"
        if ($LASTEXITCODE -ne 0) { throw "keytool falló" }
    }
    & $Apksigner sign --ks $KsPath --ks-key-alias $KsAlias `
        --ks-pass "pass:$KsPass" --key-pass "pass:$KsPass" `
        --v1-signing-enabled true --v2-signing-enabled true `
        --out $Out $Aligned
    if ($LASTEXITCODE -ne 0) { throw "apksigner sign falló" }

    $verifyOut = & $Apksigner verify --print-certs $Out 2>&1
    $verifyCode = $LASTEXITCODE
    $verifyOut | Select-Object -First 4
    if ($verifyCode -ne 0) { throw "firma inválida`n$($verifyOut -join "`n")" }
} else {
    Copy-Item $Aligned $Out -Force
}
Write-Host "[7/7] APK firmada"

$size = [math]::Round((Get-Item $Out).Length / 1KB, 1)
Write-Host ""
Write-Host "LISTO: $Out  ($size KB)" -ForegroundColor Green
Write-Host "Instalar con: adb install -r `"$Out`""
