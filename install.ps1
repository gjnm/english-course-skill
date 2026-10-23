# 英文绘本精品课 · 安装脚本（Windows PowerShell）
# 用法：右键"使用 PowerShell 运行"，或在解压目录里执行：
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = "Stop"

$RepoSlug = if ($env:ECP_REPO_SLUG) { $env:ECP_REPO_SLUG } else { "gjnm/english-course-skill" }
$ZipUrl = if ($env:ECP_ZIP_URL) { $env:ECP_ZIP_URL } else { "https://github.com/$RepoSlug/releases/latest/download/english-course-skills.zip" }
$SkillsDir = if ($env:WORKBUDDY_SKILLS_DIR) { $env:WORKBUDDY_SKILLS_DIR } else { Join-Path $HOME ".workbuddy\skills" }
$CredDir = Join-Path $HOME ".english-course-producer"
$CredFile = Join-Path $CredDir "credentials.env"
$Producer = "english-course-producer"
$Cards = "english-picturebook-cards"

Write-Host "=============================="
Write-Host " 英文绘本精品课 · 安装"
Write-Host "=============================="
Write-Host ""

$SelfDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TempDir = $null

if (Test-Path (Join-Path $SelfDir "skills\$Producer")) {
    $Src = Join-Path $SelfDir "skills"
    Write-Host "安装源：本地目录 $Src"
}
else {
    $TempDir = Join-Path $env:TEMP ("ecp-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $TempDir | Out-Null
    $ZipPath = Join-Path $TempDir "pkg.zip"
    Write-Host "安装源：下载 $ZipUrl"
    Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath -UseBasicParsing
    Expand-Archive -Path $ZipPath -DestinationPath (Join-Path $TempDir "x") -Force
    $found = Get-ChildItem -Path (Join-Path $TempDir "x") -Directory -Recurse -Filter $Producer | Select-Object -First 1
    if (-not $found) { throw "压缩包里没找到 $Producer" }
    $Src = $found.Parent.FullName
}

if (-not (Test-Path (Join-Path $HOME ".workbuddy"))) {
    Write-Host "提示：没找到 %USERPROFILE%\.workbuddy，看起来还没装 WorkBuddy。"
    Write-Host "      这个技能跑在 WorkBuddy 里：https://www.workbuddy.cn"
    Write-Host "      20 秒后继续安装技能文件，Ctrl+C 可取消。"
    Start-Sleep -Seconds 20
}

New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($name in @($Producer, $Cards)) {
    $target = Join-Path $SkillsDir $name
    if (Test-Path $target) {
        $bak = "$target.bak-$Stamp"
        Move-Item -Path $target -Destination $bak
        Write-Host "已备份旧版：$bak"
    }
    Copy-Item -Path (Join-Path $Src $name) -Destination $target -Recurse
    Write-Host "已安装：$target"
}

New-Item -ItemType Directory -Path $CredDir -Force | Out-Null
if (-not (Test-Path $CredFile)) {
    Copy-Item (Join-Path $SkillsDir "$Producer\references\credentials.example.env") $CredFile
    Write-Host "已生成凭证模板：$CredFile"
}
else {
    Write-Host "已有凭证文件，保持不动：$CredFile"
}

$Py = $env:ECP_PYTHON
$cands = @(
    (Join-Path $HOME ".workbuddy\binaries\python\envs\default\python.exe"),
    (Join-Path $HOME ".workbuddy\binaries\python\envs\default\Scripts\python.exe")
)
if (-not $Py) {
    foreach ($c in $cands) { if (Test-Path $c) { $Py = $c; break } }
}
if (-not $Py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $Py = $cmd.Source }
}
if (-not $Py) { throw "没找到 python。装一个 3.8+ 的 Python（python.org，安装时勾选 Add to PATH）再来。" }
Write-Host "Python：$Py"

& $Py -c "import PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "缺 Pillow，安装中……"
    & $Py -m pip install --user --quiet pillow
}
& $Py -c "import requests" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "缺 requests，安装中……"
    & $Py -m pip install --user --quiet requests
}

Write-Host ""
& $Py (Join-Path $SkillsDir "$Producer\scripts\check_env.py")

Write-Host ""
Write-Host "=============================="
Write-Host " 装完了，下一步"
Write-Host "=============================="
Write-Host "1. 打开 WorkBuddy（已开着就重开一次，让它加载新技能）"
Write-Host "2. 填凭证：$CredFile"
Write-Host "3. 在对话里说：「这几张绘本照片，做成能听能读的英文课」并附上照片"
Write-Host ""
Write-Host "本工具不往任何服务器上传课程，全部在你本机跑完，最后给你一个 HTML 展示页。"

if ($TempDir -and (Test-Path $TempDir)) { Remove-Item $TempDir -Recurse -Force }
