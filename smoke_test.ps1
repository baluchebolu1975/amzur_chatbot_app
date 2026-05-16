$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8001'
$sid  = 'smoke-default-' + (Get-Random)
$sid2 = 'smoke-upload-'  + (Get-Random)
$pass = [System.Collections.Generic.List[string]]::new()
$fail = [System.Collections.Generic.List[string]]::new()

function Q {
    param([string]$Label, [string]$Session, [string]$Question, [string[]]$Must=@(), [string[]]$MustNot=@())
    $body = @{ session_id=$Session; question=$Question } | ConvertTo-Json
    $r = (Invoke-RestMethod -Method Post -Uri "$base/df-agent/query" -ContentType 'application/json' -Body $body -TimeoutSec 90).answer
    $short = $r.Substring(0, [Math]::Min(160, $r.Length))
    $ok = $true
    foreach ($m in $Must)    { if ($r -notmatch $m) { $ok=$false; Write-Output "  FAIL [$Label] missing '$m' | $short" } }
    foreach ($m in $MustNot) { if ($r -match  $m) { $ok=$false; Write-Output "  FAIL [$Label] forbidden '$m' | $short" } }
    if ($ok) { $pass.Add($Label); Write-Output "  PASS [$Label]" } else { $fail.Add($Label) }
}

# ── Load default sheet ──────────────────────────────────────────────────────
Write-Output "Loading default sheet (force_reload)..."
Invoke-RestMethod -Method Post -Uri "$base/df-agent/load-default-file" `
    -ContentType 'application/json' `
    -Body (@{ session_id=$sid; force_reload=$true } | ConvertTo-Json) `
    -TimeoutSec 120 | Out-Null

Write-Output ""
Write-Output "=== DEFAULT SHEET TESTS ==="
Q 'row-count'      $sid 'how many rows are in the data'                                  @('row|record|employee|entr') @()
Q 'columns'        $sid 'what columns does the dataset have'                             @('Emp Name|Name|column|field') @()
Q 'kavya-comments' $sid 'comments by onshore offshore heads for kavya sampathi'          @('Kavya') @('Tarun','Akhil','Priya')
Q 'kavya-areas'    $sid 'areas of improvement for kavya sampathi'                        @('Kavya') @('Tarun','Akhil','Priya')
Q 'tarun-comments' $sid 'comments by onshore offshore heads for tarun dasari'            @('Tarun') @('Kavya','Akhil','Priya')
Q 'all-rows'       $sid 'show all rows in the data'                                      @('Kavya|Tarun|Name|row|data') @()
Q 'questions-list' $sid 'what questions are listed in the data'                          @('\S') @()
Q 'row-by-index'   $sid 'show me row 1'                                                  @('\S') @()

# ── Build & upload minimal CSV via curl ─────────────────────────────────────
Write-Output ""
Write-Output "Uploading test CSV..."
$csv = "Name,Score,Department,Comments`nAlice Smith,95,Engineering,Great performer`nBob Jones,80,HR,Needs improvement`nCarol White,88,Engineering,On track"
$tmp = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.csv'
[System.IO.File]::WriteAllText($tmp, $csv)

$curlOut = & curl.exe -s -X POST "$base/df-agent/upload-file?session_id=$sid2" -F "file=@$tmp;type=text/csv" 2>&1
Remove-Item $tmp -Force
Write-Output "Upload response: $curlOut"

Write-Output ""
Write-Output "=== UPLOADED SHEET TESTS ==="
Q 'u-row-count'   $sid2 'how many rows are in the data'               @('3|three') @()
Q 'u-columns'     $sid2 'what are the columns'                        @('Name|Score|Department|Comments') @()
Q 'u-alice-score' $sid2 'what is the score for alice smith'           @('95|Alice') @('Bob','Carol')
Q 'u-bob-comment' $sid2 'comments for bob jones'                      @('Needs improvement|Bob') @('Alice','Carol')
Q 'u-all-rows'    $sid2 'show all rows'                               @('Alice|Bob|Carol') @()
Q 'u-carol-dept'  $sid2 'what department is carol white in'           @('Engineering|Carol') @('HR')
Q 'u-isolation'   $sid2 'what is the score for alice'                 @('95') @('Kavya','Tarun','Sampathi')
Q 'u-row-count2'  $sid2 'total number of records'                     @('3|three') @()

# ── Summary ──────────────────────────────────────────────────────────────────
Write-Output ""
Write-Output "=============================="
Write-Output "PASSED : $($pass.Count)  -- $($pass -join ', ')"
$failStr = if ($fail.Count) { "$($fail.Count)  -- $($fail -join ', ')" } else { "0" }
Write-Output "FAILED : $failStr"
Write-Output "ALL_PASS: $($fail.Count -eq 0)"
Write-Output "=============================="
