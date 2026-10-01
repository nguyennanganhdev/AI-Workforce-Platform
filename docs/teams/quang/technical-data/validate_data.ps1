param()

$ErrorActionPreference = 'Stop'
$dataRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$issuesFile = Join-Path (Split-Path -Parent $dataRoot) 'general.md'
$errors = [System.Collections.Generic.List[string]]::new()

function Read-Jsonl([string]$name) {
    $path = Join-Path $dataRoot $name
    $records = [System.Collections.Generic.List[object]]::new()
    $lineNumber = 0
    foreach ($line in Get-Content -LiteralPath $path -Encoding utf8) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $records.Add(($line | ConvertFrom-Json -ErrorAction Stop)) }
        catch { $errors.Add("$name`:$lineNumber invalid JSON: $($_.Exception.Message)") }
    }
    return $records.ToArray()
}

$manifest = Read-Jsonl 'RAG_SOURCE_MANIFEST.jsonl'
$chunks = Read-Jsonl 'RAG_CHUNKS.jsonl'
$evals = Read-Jsonl 'RAG_EVAL.jsonl'
$cases = Read-Jsonl 'VN_PUBLIC_CASES.jsonl'
$facts = @(Read-Jsonl 'SOURCE_FACTS.jsonl') + @(Read-Jsonl 'DEEP_SOURCE_FACTS.jsonl') + @(Read-Jsonl 'VN_SOURCE_FACTS.jsonl')
$synthetic = @(Read-Jsonl 'SYNTHETIC_CASES.jsonl') + @(Read-Jsonl 'EDGE_CASES.jsonl')

$registerIds = @{}
foreach ($name in @('SOURCE_REGISTER.md', 'DEEP_SOURCE_REGISTER.md', 'VN_SOURCE_REGISTER.md')) {
    foreach ($line in Get-Content -LiteralPath (Join-Path $dataRoot $name) -Encoding utf8) {
        if ($line -notmatch '^\| ([A-Z][A-Z0-9-]+) \|') { continue }
        $id = $Matches[1]
        if ($id -eq 'ID') { continue }
        if ($registerIds.ContainsKey($id)) { $errors.Add("duplicate register ID $id") }
        $registerIds[$id] = $name
    }
}

$sourceIds = @{}
foreach ($source in $manifest) {
    if ($sourceIds.ContainsKey($source.source_id)) { $errors.Add("duplicate source_id $($source.source_id)") }
    $sourceIds[$source.source_id] = $true
    if (@($source.source_urls).Count -eq 0) { $errors.Add("source $($source.source_id) has no URL") }
    if ($source.approval_status -ne 'not_published') { $errors.Add("source $($source.source_id) unexpectedly published") }
    if (-not $registerIds.ContainsKey($source.source_id)) { $errors.Add("source $($source.source_id) missing register entry") }
    elseif ($source.register_file -ne $registerIds[$source.source_id]) { $errors.Add("source $($source.source_id) has wrong register_file") }
}
foreach ($id in $registerIds.Keys) {
    if (-not $sourceIds.ContainsKey($id)) { $errors.Add("register ID $id missing manifest entry") }
}

$issueMatches = [regex]::Matches((Get-Content -LiteralPath $issuesFile -Raw -Encoding utf8), 'TECH\.[A-Z]+\.[A-Z_]+')
$issueIds = @{}
foreach ($match in $issueMatches) { $issueIds[$match.Value] = $true }

$factIds = @{}
foreach ($fact in $facts) {
    if ($factIds.ContainsKey($fact.fact_id)) { $errors.Add("duplicate fact_id $($fact.fact_id)") }
    $factIds[$fact.fact_id] = $fact
    if (-not $sourceIds.ContainsKey($fact.source_id)) { $errors.Add("fact $($fact.fact_id) missing source $($fact.source_id)") }
    if ($fact.PSObject.Properties.Name -notcontains 'source_location') { $errors.Add("fact $($fact.fact_id) missing source_location field") }
    if ($fact.approval_status -ne 'not_published') { $errors.Add("fact $($fact.fact_id) unexpectedly published or missing approval_status") }
    foreach ($issue in @($fact.issue_codes)) {
        if ($issue -and -not $issueIds.ContainsKey($issue)) { $errors.Add("fact $($fact.fact_id) unknown issue $issue") }
    }
}

$chunkIds = @{}
foreach ($chunk in $chunks) {
    if ($chunkIds.ContainsKey($chunk.chunk_id)) { $errors.Add("duplicate chunk_id $($chunk.chunk_id)") }
    $chunkIds[$chunk.chunk_id] = $true
    if (@($chunk.issue_codes).Count -ne 1 -or -not $issueIds.ContainsKey($chunk.issue_codes[0])) { $errors.Add("chunk $($chunk.chunk_id) invalid issue") }
    foreach ($sourceId in @($chunk.citation_source_ids)) {
        if (-not $sourceIds.ContainsKey($sourceId)) { $errors.Add("chunk $($chunk.chunk_id) missing source $sourceId") }
    }
    foreach ($ref in @($chunk.citation_fact_refs)) {
        if ($ref.source_id -notin @($chunk.citation_source_ids)) { $errors.Add("chunk $($chunk.chunk_id) fact source not cited") }
        if (-not $factIds.ContainsKey($ref.fact_id)) { $errors.Add("chunk $($chunk.chunk_id) missing fact $($ref.fact_id)") }
        elseif ($factIds[$ref.fact_id].source_id -ne $ref.source_id) { $errors.Add("chunk $($chunk.chunk_id) fact $($ref.fact_id) belongs to another source") }
        elseif ($factIds[$ref.fact_id].source_location -ne $ref.source_location) { $errors.Add("chunk $($chunk.chunk_id) fact $($ref.fact_id) has mismatched source_location") }
        if ([string]::IsNullOrWhiteSpace($ref.source_location)) { $errors.Add("chunk $($chunk.chunk_id) missing source location") }
    }
    if ($chunk.policy_status -eq 'published' -or $chunk.resident_instruction_allowed -eq $true -or $chunk.diagnosis_allowed -eq $true) { $errors.Add("chunk $($chunk.chunk_id) has unsafe publication flag") }
}

foreach ($eval in $evals) {
    foreach ($chunkId in @($eval.expected_chunk_ids)) {
        if (-not $chunkIds.ContainsKey($chunkId)) { $errors.Add("eval $($eval.eval_id) missing chunk $chunkId") }
    }
}

$allowedClaim = @('unverified', 'agency_confirmed', 'not_observed_at_inspection')
$allowedRepair = @('no_completion_evidence', 'agency_reports_restored_no_work_order')
foreach ($case in $cases) {
    if (-not $sourceIds.ContainsKey($case.source_id)) { $errors.Add("case $($case.case_id) missing source $($case.source_id)") }
    $matchedSource = $manifest | Where-Object { $_.source_id -eq $case.source_id } | Select-Object -First 1
    if ($matchedSource -and $case.source_url -notin @($matchedSource.source_urls)) { $errors.Add("case $($case.case_id) URL differs from manifest") }
    if ($case.claim_evidence_status -notin $allowedClaim) { $errors.Add("case $($case.case_id) invalid claim status") }
    if ($case.repair_evidence_status -notin $allowedRepair) { $errors.Add("case $($case.case_id) invalid repair status") }
    if ($case.confirmed_issue_code -and -not $issueIds.ContainsKey($case.confirmed_issue_code)) { $errors.Add("case $($case.case_id) invalid confirmed issue") }
    if ($case.PSObject.Properties.Name -contains 'repair_verified') { $errors.Add("case $($case.case_id) still uses ambiguous repair_verified") }
}

if ($chunks.Count -ne $issueIds.Count) { $errors.Add('RAG chunks do not cover all issue codes') }
if (($chunks | ForEach-Object { $_.issue_codes[0] } | Sort-Object -Unique).Count -ne $issueIds.Count) { $errors.Add('RAG chunk issue codes are duplicated or missing') }

foreach ($fixture in $synthetic) {
    if (-not $issueIds.ContainsKey($fixture.issue_code)) { $errors.Add("fixture $($fixture.case_id) unknown issue") }
    foreach ($sourceId in @($fixture.source_ids)) {
        if ($sourceId -and -not $sourceIds.ContainsKey($sourceId)) { $errors.Add("fixture $($fixture.case_id) missing source $sourceId") }
    }
    foreach ($factId in @($fixture.source_fact_ids)) {
        if ($factId -and -not $factIds.ContainsKey($factId)) { $errors.Add("fixture $($fixture.case_id) missing fact $factId") }
    }
}

Write-Output "issues=$($issueIds.Count) sources=$($manifest.Count) facts=$($facts.Count) chunks=$($chunks.Count) public_cases=$($cases.Count) synthetic=$($synthetic.Count) evals=$($evals.Count)"
if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Output "ERROR: $_" }
    exit 1
}
Write-Output 'Validation OK'
