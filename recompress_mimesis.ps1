# =====================================================================
#  Mimesis 录像批量压缩 (续跑版)
#  - 只处理视频码率 > 15Mbps 的 mp4, 压成 15Mbps HEVC (NVENC 硬编码)
#  - 每个文件: 编码 -> 校验(时长+全片解码) -> 删原件 -> 放回原名
#  - 已完成的文件有 .done 标记, 重复运行会自动跳过 (可随时中断续跑)
#  - 中断不会损坏任何东西; 未完成的部分输出会被下次运行覆盖
# =====================================================================
$ErrorActionPreference = 'Continue'
$ff = 'E:\Tools\ffmpeg\bin\ffmpeg.exe'
$fp = 'E:\Tools\ffmpeg\bin\ffprobe.exe'
$work = 'E:\tmp\mimesis_recompress'
$log = "$work\progress.log"
if (-not (Test-Path $ff)) { Write-Host "错误: 找不到 $ff" -ForegroundColor Red; exit 1 }
New-Item "$work\state", "$work\compare" -ItemType Directory -Force | Out-Null
function L($m, $c = 'Gray') {
    $t = Get-Date -Format 'HH:mm:ss'
    Write-Host "[$t] $m" -ForegroundColor $c
    Add-Content -Path $log -Value "[$t] $m"
}

# 动态定位 Mimesis 目录 (H 盘下唯一包含 Mimesis 子目录的文件夹)
$mis = $null
foreach ($d in (Get-ChildItem 'H:\' -Directory)) {
    $c = Join-Path $d.FullName 'Mimesis'
    if (Test-Path $c) { $mis = $c; break }
}
if (-not $mis) { L "错误: H 盘上找不到 Mimesis 目录" 'Red'; exit 1 }

function ProbeBitrate([string]$f) {
    $j = & $fp -v error -select_streams v:0 -show_entries stream=bit_rate -of csv=p=0 $f 2>$null
    if ("$j" -match '(\d+)') { return [long]$Matches[1] }
    return 0
}
function ProbeDuration([string]$f) {
    $j = & $fp -v error -show_entries format=duration -of csv=p=0 $f 2>$null
    if ("$j" -match '([\d\.]+)') { return [double]$Matches[1] }
    return 0
}

$todo = @()
foreach ($f in (Get-ChildItem $mis -File -Filter *.mp4 | Sort-Object Length)) {
    $br = ProbeBitrate $f.FullName
    if ($br -gt 15000000) { $todo += $f }
}

$remaining = 0
foreach ($f in $todo) { if (-not (Test-Path "$work\state\$($f.BaseName).done")) { $remaining++ } }
Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host " Mimesis 录像压缩 | 目标: $mis" -ForegroundColor Cyan
Write-Host " 待处理: $remaining 个文件 (已完成的自动跳过)" -ForegroundColor Cyan
if ($remaining -eq 0) { Write-Host " 没有需要处理的文件, 全部完成!" -ForegroundColor Green; exit 0 }
Write-Host " 预计总耗时 ~$([int]($remaining * 12)) 分钟 (GPU 编码, 可正常使用电脑)" -ForegroundColor Cyan
Write-Host " 随时可关窗口中断, 再次运行会接着跑" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

$ok = 0; $fail = 0; $savedGB = 0.0
foreach ($f in $todo) {
    $base = $f.BaseName
    $marker = "$work\state\$base.done"
    if (Test-Path $marker) { L "跳过(已完成)  $base" 'DarkGray'; $ok++; continue }

    $srcDur = ProbeDuration $f.FullName
    $srcSize = $f.Length
    $out = "$work\$base.mp4"

    # 压缩前截图 (25%/50%/75% 处), 留作画质对比
    foreach ($p in 25, 50, 75) {
        & $ff -y -v error -ss ([int]($srcDur * $p / 100)) -i $f.FullName -frames:v 1 -q:v 3 "$work\compare\${base}_${p}pct_SRC.jpg" 2>$null
    }

    L ("开始编码  {0}  ({1:N2}GB / {2:N0}分钟素材)" -f $base, ($srcSize / 1GB), ($srcDur / 60)) 'Yellow'
    $t0 = Get-Date
    & $ff -y -hide_banner -loglevel error -stats -i $f.FullName -map 0 -c:v hevc_nvenc -preset p5 -rc vbr -b:v 15M -maxrate 18M -bufsize 45M -c:a copy -movflags +faststart $out 2> "$work\state\$base.enc.log"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $out)) { L "编码失败  $base (exit $LASTEXITCODE, 详见 state\$base.enc.log) - 原件保留" 'Red'; $fail++; continue }
    $encMin = ((Get-Date) - $t0).TotalMinutes

    # 校验: 时长一致 + 全片解码无错误
    $outDur = ProbeDuration $out
    $tolOK = ($outDur -gt 0) -and ([math]::Abs($outDur - $srcDur) / $srcDur -lt 0.005)
    Write-Host "   校验中 (全片解码, 约需几分钟)..." -ForegroundColor DarkGray
    $decErr = & $ff -v error -i $out -f null - 2>&1
    $decErrStr = if ($decErr) { "$decErr" } else { '' }
    $decOK = ($decErrStr.Trim().Length -eq 0)
    if (-not ($tolOK -and $decOK)) {
        L "校验失败  $base (时长ok=$tolOK 解码ok=$decOK) - 原件保留, 输出移入 state\*.failed" 'Red'
        $fail++
        Move-Item $out "$work\state\$base.failed.mp4" -Force
        continue
    }

    foreach ($p in 25, 50, 75) {
        & $ff -y -v error -ss ([int]($outDur * $p / 100)) -i $out -frames:v 1 -q:v 3 "$work\compare\${base}_${p}pct_NEW.jpg" 2>$null
    }
    $newSize = (Get-Item $out).Length

    # 校验通过: 删除原件, 新文件放回原名
    Remove-Item -LiteralPath $f.FullName -Force
    Move-Item -LiteralPath $out -Destination $f.FullName -Force
    New-Item $marker -ItemType File -Force | Out-Null
    $savedGB += ($srcSize - $newSize) / 1GB
    L ("完成替换  {0}: {1:N2}GB -> {2:N2}GB  (编码 {3:N1} 分钟, {4:N1}x 实时)" -f $base, ($srcSize / 1GB), ($newSize / 1GB), $encMin, ($srcDur / 60 / [math]::Max($encMin, 0.01))) 'Green'
    $ok++
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
$sumColor = if ($fail -eq 0) { 'Green' } else { 'Yellow' }
L "全部结束: 成功 $ok / 失败 $fail, 本次累计节省 $([math]::Round($savedGB,2))GB" $sumColor
Get-Volume -DriveLetter H | ForEach-Object { Write-Host (" H 盘当前可用: {0:N1} GB" -f ($_.SizeRemaining / 1GB)) -ForegroundColor Cyan }
Write-Host " 画质对比截图: $work\compare  (SRC=压缩前 NEW=压缩后)" -ForegroundColor Cyan
Write-Host " 运行日志:     $log" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
