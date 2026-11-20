<#
رفع مقاطع مقرر إلى تخزين الإنتاج من جهاز المالك، عبر نفق Postgres بلا كشف القاعدة.

1) في طرفية: railway connect Postgres --tunnel-only   (اتركها مفتوحة واقرأ المنفذ الذي تطبعه)
2) في أخرى، من جذر المستودع أو أي شجرة منه:
   railway run --service web -- pwsh -NoProfile -File scripts/publish_assets_tunnel.ps1 -Port <المنفذ> -Course g10-s1 -Source '<مجلد المقاطع>'

Railway يحقن متغيرات خدمة web (ومنها ASSETS_S3_* وDATABASE_URL بمضيفه الداخلي)؛ السكربت يبدّل في DATABASE_URL
المضيف والمنفذ وحدهما بالنفق المحلي (كلمة السر واسم القاعدة كما حقنهما Railway، فلا تُكتب في الأمر)، ثم يشغّل
publish_assets. الأمر idempotent: إعادة التشغيل تعطي «بلا تغيير» لكل مقطع.
#>
param(
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][string]$Course,
    [Parameter(Mandatory = $true)][string]$Source,
    [string]$Python
)
$ErrorActionPreference = 'Stop'
if (-not $env:DATABASE_URL) { throw 'DATABASE_URL غير موجود: شغّل السكربت داخل railway run --service web' }
if (-not (Test-Path -LiteralPath $Source -PathType Container)) { throw "مجلد المقاطع غير موجود: $Source" }

$repo = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    # الشجرة الفرعية بلا .venv: البيئة في جذر المستودع الرئيسي (أب مجلد git المشترك).
    # مخرج git UTF-8، وبغير هذا يقرؤه PowerShell بترميز الطرفية فيفسد المسار العربي.
    [Console]::OutputEncoding = [Text.Encoding]::UTF8
    $common = (git -C $repo rev-parse --path-format=absolute --git-common-dir).Trim()
    $Python = Join-Path (Split-Path -Parent $common) '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $Python)) { throw "مفسّر بايثون غير موجود: $Python (مرّره بـ -Python)" }

$u = [Uri]$env:DATABASE_URL
$env:DATABASE_URL = "$($u.Scheme)://$($u.UserInfo)@127.0.0.1:$Port$($u.AbsolutePath)"
Write-Host "القاعدة عبر النفق: 127.0.0.1:$Port$($u.AbsolutePath)"

Set-Location -LiteralPath $repo
& $Python manage.py publish_assets $Course --source $Source
exit $LASTEXITCODE
