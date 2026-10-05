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
$documents = @(Read-Jsonl 'rag/RAG_DOCUMENTS.jsonl')
$evals = Read-Jsonl 'rag/RAG_EVAL.jsonl'
$evalDataset = (Get-Content -LiteralPath (Join-Path $dataRoot 'rag/eval/technical-a2.v1.json') -Raw -Encoding utf8 | ConvertFrom-Json -ErrorAction Stop)
$mockProfiles = Read-Jsonl 'rag/mock/PROCEDURE_PROFILES.jsonl'
$mockPocs = Read-Jsonl 'rag/mock/POC_LIFECYCLE.jsonl'
$mockLearning = Read-Jsonl 'rag/mock/Q07_LEARNING_FLOW.jsonl'
$mockToolData = Read-Jsonl 'rag/mock/TOOL_DATA_FIXTURES.jsonl'
$supervision = Read-Jsonl 'rag/mock/SUPERVISION_CASES.jsonl'
$mockTraces = Read-Jsonl 'rag/mock/MULTI_TURN_TRACES.jsonl'
$mockEval = (Get-Content -LiteralPath (Join-Path $dataRoot 'rag/mock/eval/technical-a2-mock.v1.json') -Raw -Encoding utf8 | ConvertFrom-Json -ErrorAction Stop)
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
$sourceById = @{}
foreach ($source in $manifest) {
    if ($sourceIds.ContainsKey($source.source_id)) { $errors.Add("duplicate source_id $($source.source_id)") }
    $sourceIds[$source.source_id] = $true
    $sourceById[$source.source_id] = $source
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

$documentCodes = @{}
$documentKeys = @{}
foreach ($document in $documents) {
    $code = [string]$document.document_code
    if ($documentCodes.ContainsKey($code)) { $errors.Add("duplicate document_code $code") }
    $documentCodes[$code] = $document
    if ($documentKeys.ContainsKey($document.document_key)) { $errors.Add("duplicate document_key $($document.document_key)") }
    $documentKeys[$document.document_key] = $true
    if (@($document.issue_codes).Count -ne $issueIds.Count -or @($document.issue_codes | Sort-Object -Unique).Count -ne $issueIds.Count -or @($document.issue_codes | Where-Object { -not $issueIds.ContainsKey($_) }).Count -gt 0) { $errors.Add("document $code invalid issue coverage") }
    if ($document.scope_key -ne '01-vinhomes' -or $document.knowledge_base_key -ne 'technical_reference_internal_poc') { $errors.Add("document $code invalid internal scope/KB") }
    if ($document.approval_status -ne 'not_published' -or $document.audience -ne 'internal_poc' -or $document.sop_available -ne $false -or $document.source_snapshot_required_before_production -ne $true) { $errors.Add("document $code unsafe publication metadata") }
    if ($document.relative_path -notmatch '^rag/corpus/01-vinhomes/[^/]+\.md$' -or $code -ne $document.relative_path.Substring('rag/corpus/'.Length)) { $errors.Add("document $code invalid corpus path") ; continue }
    $markdownPath = Join-Path $dataRoot $document.relative_path
    if (-not (Test-Path -LiteralPath $markdownPath -PathType Leaf)) { $errors.Add("document $code missing Markdown") ; continue }
    $markdown = Get-Content -LiteralPath $markdownPath -Raw -Encoding utf8
    if ($markdown -notmatch '(?s)^---\r?\n.*?\r?\n---\r?\n') { $errors.Add("document $code missing YAML front matter") }
    if (-not $markdown.Contains("# $($document.title)")) { $errors.Add("document $code title differs from manifest") }
    if ($markdown -notmatch '(?m)^approval_status: not_published$' -or $markdown -notmatch '(?m)^trang_thai: tham-khao-noi-bo-chua-duyet$' -or $markdown -notmatch '(?m)^sop_available: false$' -or $markdown -notmatch '(?m)^source_snapshot_required_before_production: true$') { $errors.Add("document $code missing safety front matter") }
    $hasSourceHeading = $markdown.Contains('### Ngu')
    $hasDocumentText = $markdown.Contains([string]$document.text_vi)
    if ($hasSourceHeading -ne $true -or $hasDocumentText -ne $true) { $errors.Add("document $code missing text or source section") }
    if (@($document.source_ids).Count -eq 0 -or @($document.citation_fact_refs).Count -eq 0) { $errors.Add("document $code has no provenance") }
    foreach ($sourceId in @($document.source_ids)) {
        if (-not $sourceIds.ContainsKey($sourceId)) { $errors.Add("document $code missing source $sourceId") }
    }
    foreach ($ref in @($document.citation_fact_refs)) {
        if ($ref.source_id -notin @($document.source_ids)) { $errors.Add("document $code fact source not cited") }
        if (-not $factIds.ContainsKey($ref.fact_id)) { $errors.Add("document $code missing fact $($ref.fact_id)") ; continue }
        if ($factIds[$ref.fact_id].source_id -ne $ref.source_id -or $factIds[$ref.fact_id].source_location -ne $ref.source_location) { $errors.Add("document $code fact $($ref.fact_id) provenance mismatch") }
        if ([string]::IsNullOrWhiteSpace($ref.source_location)) { $errors.Add("document $code missing source location") }
        if ($sourceById.ContainsKey($ref.source_id)) {
            $citation = "$($ref.source_id) ($($ref.fact_id); $($ref.source_location)): $($sourceById[$ref.source_id].source_urls -join ' | ')"
            if (-not $markdown.Contains("- $citation")) { $errors.Add("document $code Markdown citation differs from source manifest") }
        }
    }
}

$corpusFiles = @(Get-ChildItem -LiteralPath (Join-Path $dataRoot 'rag/corpus') -Recurse -File)
if ($corpusFiles.Count -ne $documents.Count -or @($corpusFiles | Where-Object { $_.Extension -ne '.md' }).Count -gt 0) { $errors.Add('corpus contains files outside the document manifest') }

$mockCodes = @{}
$mockIssues = @{}
foreach ($profile in $mockProfiles) {
    $code = [string]$profile.code
    if ($mockCodes.ContainsKey($code)) { $errors.Add("duplicate mock procedure $code") }
    $mockCodes[$code] = $profile
    if (-not $issueIds.ContainsKey($profile.issue_code)) { $errors.Add("mock procedure $code unknown issue") }
    if ($mockIssues.ContainsKey($profile.issue_code)) { $errors.Add("duplicate mock issue $($profile.issue_code)") }
    $mockIssues[$profile.issue_code] = $true
    if ($profile.fixture_only -ne $true -or $profile.publication_status -ne 'draft' -or $profile.audience -ne 'technician' -or $profile.version_no -ne 1) { $errors.Add("mock procedure $code unsafe status") }
    if ($profile.document_code -ne '01-vinhomes/quy-trinh-gia-lap-a2.md') { $errors.Add("mock procedure $code invalid collection path") ; continue }
    $path = Join-Path $dataRoot ("rag/mock-corpus/" + $profile.document_code)
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { $errors.Add("mock procedure $code missing Markdown") ; continue }
    $markdown = Get-Content -LiteralPath $path -Raw -Encoding utf8
    if ($markdown -notmatch '(?m)^fixture_only: true$' -or $markdown -notmatch '(?m)^approval_status: not_published$' -or $markdown -notmatch '(?m)^sop_available: false$' -or $markdown -notmatch '(?m)^audience: technician_test_only$' -or $markdown -notmatch '(?m)^version: mock-v1$' -or $markdown -notmatch '(?m)^trang_thai: du-lieu-gia-lap-khong-xuat-ban$') { $errors.Add("mock procedure $code unsafe Markdown status") }
    $issueMarker = '**Issue code:** `' + $profile.issue_code + '`'
    if (-not $markdown.Contains($issueMarker) -or -not $markdown.Contains("### $code ")) { $errors.Add("mock procedure $code metadata/title mismatch") }
    $hasMockSourceHeading = $markdown.Contains('### Ngu')
    $hasMockCitation = $markdown.Contains("- ${code}-v1:")
    if ($hasMockSourceHeading -ne $true -or $hasMockCitation -ne $true) { $errors.Add("mock procedure $code missing fixture citation") }
    if (@($profile.preconditions).Count -eq 0 -or @($profile.contraindications).Count -eq 0 -or @($profile.stop_conditions).Count -eq 0 -or @($profile.acceptance_criteria).Count -eq 0) { $errors.Add("mock procedure $code missing structured rules") }
    $criterionIds = @{}
    foreach ($criterion in @($profile.acceptance_criteria)) {
        if ($criterionIds.ContainsKey($criterion.id)) { $errors.Add("mock procedure $code duplicate criterion $($criterion.id)") }
        $criterionIds[$criterion.id] = $true
        if ($criterion.check.kind -notin @('manual', 'checklist', 'evidence', 'measurement')) { $errors.Add("mock procedure $code invalid criterion kind") }
        if ($criterion.check.kind -eq 'evidence' -and ($criterion.check.purpose -notin @('before', 'after') -or $criterion.check.min -lt 1)) { $errors.Add("mock procedure $code invalid evidence criterion") }
    }
}
$mockCorpusFiles = @(Get-ChildItem -LiteralPath (Join-Path $dataRoot 'rag/mock-corpus') -Recurse -File)
if ($mockCorpusFiles.Count -ne 1 -or @($mockCorpusFiles | Where-Object { $_.Extension -ne '.md' }).Count -gt 0) { $errors.Add('mock corpus must contain one Markdown collection') }
if ($mockProfiles.Count -ne $issueIds.Count -or $mockIssues.Count -ne $issueIds.Count) { $errors.Add('mock procedures do not cover all issue codes') }

$pocIds = @{}
$pocWorkOrders = @{}
foreach ($poc in $mockPocs) {
    if ($pocIds.ContainsKey($poc.case_id)) { $errors.Add("duplicate POC case $($poc.case_id)") }
    $pocIds[$poc.case_id] = $true
    $pocWorkOrders[$poc.work_order.workorder_id] = $true
    if ($poc.data_kind -ne 'synthetic_fixture' -or $poc.scope.tenant_id -ne '91000000-0000-4000-8000-000000000001' -or $poc.scope.building_key -ne 'SYN-B-01') { $errors.Add("POC $($poc.case_id) unsafe scope") }
    if (-not $mockCodes.ContainsKey($poc.procedure_code) -or $mockCodes[$poc.procedure_code].issue_code -ne $poc.issue_code) { $errors.Add("POC $($poc.case_id) missing/mismatched procedure") }
    if ($poc.ticket.ticket_id -ne $poc.work_order.ticket_id -or $poc.assessment.issue_code -ne $poc.issue_code) { $errors.Add("POC $($poc.case_id) ticket/work order/assessment mismatch") }
    if ($poc.work_order.workorder_id -notmatch '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-8[0-9a-f]{3}-[0-9a-f]{12}$') { $errors.Add("POC $($poc.case_id) invalid mock workorder UUID") }
    if (@($poc.ticket.facts).Count -eq 0 -or @($poc.expected.forbidden_claims).Count -eq 0 -or @($poc.negative_variants).Count -lt 3) { $errors.Add("POC $($poc.case_id) insufficient lifecycle coverage") }
    foreach ($evidence in @($poc.evidence)) {
        if ($evidence.ticket_id -ne $poc.ticket.ticket_id -or $evidence.scan_status -notin @('not_uploaded', 'not_available_no_grant', 'simulated_clean')) { $errors.Add("POC $($poc.case_id) invalid evidence") }
    }
    foreach ($measurement in @($poc.measurements)) {
        if (-not $measurement.unit -or -not $measurement.measured_at -or -not $measurement.measured_by.source_id -or $measurement.quality -notlike 'fixture_only*') { $errors.Add("POC $($poc.case_id) invalid measurement provenance") }
    }
}
foreach ($profile in $mockProfiles) {
    if ($profile.source_work_order_id -and -not $pocWorkOrders.ContainsKey($profile.source_work_order_id)) { $errors.Add("mock procedure $($profile.code) missing POC work order") }
}
if ($mockPocs.Count -ne 5) { $errors.Add('expected five POC lifecycle cases') }

$pocTicketIds = @{}
$pocAssetIds = @{}
foreach ($poc in $mockPocs) {
    $pocTicketIds[$poc.ticket.ticket_id] = $true
    $pocAssetIds[$poc.asset.asset_id] = $true
}
$toolFixtureIds = @{}
foreach ($fixture in $mockToolData) {
    if ($toolFixtureIds.ContainsKey($fixture.fixture_id)) { $errors.Add("duplicate mock tool fixture $($fixture.fixture_id)") }
    $toolFixtureIds[$fixture.fixture_id] = $true
    if ($fixture.data_kind -ne 'synthetic_fixture' -or $fixture.tenant_id -ne '91000000-0000-4000-8000-000000000001') { $errors.Add("mock tool fixture $($fixture.fixture_id) unsafe scope") }
    switch ($fixture.record_kind) {
        'sensor_reading' {
            if ($fixture.quality -notin @('good', 'uncertain', 'bad', 'unknown') -or -not $fixture.unit -or -not $fixture.observed_at -or ($fixture.asset_id -and -not $pocAssetIds.ContainsKey($fixture.asset_id))) { $errors.Add("mock sensor $($fixture.fixture_id) invalid") }
            $age = ([datetime]$fixture.test_now - [datetime]$fixture.observed_at).TotalSeconds
            $expectedFreshness = if ($age -gt $fixture.max_age_seconds) { 'stale' } else { 'fresh' }
            if ($fixture.expected_freshness -ne $expectedFreshness) { $errors.Add("mock sensor $($fixture.fixture_id) freshness mismatch") }
        }
        'maintenance_event' {
            if (-not $pocAssetIds.ContainsKey($fixture.asset_id) -or ($fixture.workorder_id -and -not $pocWorkOrders.ContainsKey($fixture.workorder_id)) -or @($fixture.source_refs).Count -eq 0) { $errors.Add("mock maintenance $($fixture.fixture_id) invalid provenance") }
        }
        'service_interruption' {
            if ($fixture.utility -notin @('water', 'power') -or $fixture.status -notin @('proposed', 'cancelled', 'approved', 'notified', 'active', 'restored') -or @($fixture.scope_ids).Count -eq 0) { $errors.Add("mock interruption $($fixture.fixture_id) invalid") }
            if ($fixture.status -in @('proposed', 'cancelled') -and ($fixture.expected_get_active_outage -ne 'exclude' -or $fixture.expected_utility_schedule -ne 'exclude')) { $errors.Add("mock interruption $($fixture.fixture_id) leaks unapproved data") }
        }
        'approval_request' {
            if (-not $pocTicketIds.ContainsKey($fixture.ticket_id) -or $fixture.status -ne 'PENDING_APPROVAL' -or $fixture.physical_action_done -ne $false -or -not $fixture.idempotency_key) { $errors.Add("mock request $($fixture.fixture_id) invalid/premature action") }
        }
        'vendor_candidate' {
            if ($fixture.booking_status -ne 'not_booked' -or $null -ne $fixture.price) { $errors.Add("mock vendor $($fixture.fixture_id) booked or priced") }
        }
        'repair_cost_observation' {
            $sum = $fixture.labor_amount + $fixture.materials_amount + $fixture.other_amount + $fixture.tax_amount - $fixture.discount_amount
            if (-not $pocWorkOrders.ContainsKey($fixture.workorder_id) -or $fixture.status -ne 'draft' -or $fixture.verified_by -or $fixture.reference_status -ne 'insufficient_data' -or $sum -ne $fixture.total_amount) { $errors.Add("mock cost $($fixture.fixture_id) unsafe or incorrect") }
        }
        default { $errors.Add("mock tool fixture $($fixture.fixture_id) unknown record kind") }
    }
}
if ($mockToolData.Count -ne 16) { $errors.Add('expected 16 mock tool-data records') }

$supervisionIds = @{}
$supervisionCoverage = @{}
$expectedVariants = @('routine', 'hazard', 'missing', 'conflict', 'closeout')
$allowedTools = @('asset.read', 'maintenance_history.read', 'technical.get_active_outage', 'sensor.read')
foreach ($case in $supervision) {
    if ($supervisionIds.ContainsKey($case.id)) { $errors.Add("duplicate supervision case $($case.id)") }
    $supervisionIds[$case.id] = $true
    if ($case.fixture_only -ne $true -or -not $mockIssues.ContainsKey($case.issue_code)) { $errors.Add("supervision $($case.id) unsafe or unknown issue") }
    $expectedCode = (@($mockProfiles | Where-Object { $_.issue_code -eq $case.issue_code })[0]).code
    if ($case.source_ref -ne "${expectedCode}-v1") { $errors.Add("supervision $($case.id) source ref mismatch") }
    $key = "$($case.issue_code)|$($case.variant)"
    if ($supervisionCoverage.ContainsKey($key)) { $errors.Add("duplicate supervision issue/variant $key") }
    $supervisionCoverage[$key] = $true
    if ($case.variant -notin $expectedVariants -or $case.split -notin @('train', 'dev', 'test')) { $errors.Add("supervision $($case.id) invalid variant/split") }
    if (($case.variant -in @('routine', 'hazard', 'missing') -and $case.split -ne 'train') -or ($case.variant -eq 'conflict' -and $case.split -ne 'dev') -or ($case.variant -eq 'closeout' -and $case.split -ne 'test')) { $errors.Add("supervision $($case.id) wrong split") }
    if (-not $case.input.message -or -not $case.target.reply -or @($case.target.avoid).Count -eq 0) { $errors.Add("supervision $($case.id) incomplete input/target") }
    if ($case.variant -eq 'hazard' -and ($case.target.route -ne 'escalate_now' -or @($case.target.tools).Count -ne 0)) { $errors.Add("supervision $($case.id) hazard not escalated") }
    if ($case.variant -eq 'missing' -and ($case.target.route -ne 'ask_clarification' -or @($case.input.unknown).Count -eq 0)) { $errors.Add("supervision $($case.id) missing facts not asked") }
    if ($case.variant -eq 'routine' -and $case.target.route -ne 'staff_assessment') { $errors.Add("supervision $($case.id) wrong routine route") }
    if ($case.variant -eq 'conflict' -and $case.target.route -ne 'human_review') { $errors.Add("supervision $($case.id) conflict not reviewed") }
    if ($case.variant -eq 'closeout' -and $case.target.route -notin @('needs_evidence', 'human_review')) { $errors.Add("supervision $($case.id) unsafe closeout route") }
    if ($case.variant -eq 'closeout' -and @($case.target.tools) -contains 'technical.verify_resolution') { $errors.Add("supervision $($case.id) verifies unsubmitted result") }
    foreach ($tool in @($case.target.tools)) {
        if ($tool -notin $allowedTools) { $errors.Add("supervision $($case.id) unexpected tool $tool") }
    }
}
foreach ($issue in $issueIds.Keys) {
    foreach ($variant in $expectedVariants) {
        if (-not $supervisionCoverage.ContainsKey("$issue|$variant")) { $errors.Add("supervision missing $issue/$variant") }
    }
}
if ($supervision.Count -ne 80 -or @($supervision | Where-Object { $_.split -eq 'train' }).Count -ne 48 -or @($supervision | Where-Object { $_.split -eq 'dev' }).Count -ne 16 -or @($supervision | Where-Object { $_.split -eq 'test' }).Count -ne 16) { $errors.Add('supervision split/count mismatch') }

$mockTraceIds = @{}
foreach ($trace in $mockTraces) {
    if ($mockTraceIds.ContainsKey($trace.trace_id)) { $errors.Add("duplicate mock trace $($trace.trace_id)") }
    $mockTraceIds[$trace.trace_id] = $true
    if ($trace.fixture_only -ne $true -or -not $pocIds.ContainsKey($trace.case_id)) { $errors.Add("mock trace $($trace.trace_id) missing POC") ; continue }
    $poc = @($mockPocs | Where-Object { $_.case_id -eq $trace.case_id })[0]
    if ($trace.issue_code -ne $poc.issue_code -or $trace.expected_final.verification -ne $poc.expected.verify_resolution) { $errors.Add("mock trace $($trace.trace_id) disagrees with POC") }
    $turnNumber = 0
    foreach ($turn in @($trace.turns)) {
        $turnNumber++
        if ($turn.seq -ne $turnNumber -or -not $turn.content -or -not $turn.expected_state) { $errors.Add("mock trace $($trace.trace_id) invalid turn $turnNumber") }
        if ($turn.tool -eq 'technical.verify_resolution' -and $poc.executor_result.status -in @('not_submitted', 'not_completed', 'assessment_only')) { $errors.Add("mock trace $($trace.trace_id) verifies missing result") }
    }
    if ($turnNumber -lt 5 -or $trace.expected_final.ticket_closed -ne $false -or @($trace.expected_final.forbidden_claims).Count -eq 0) { $errors.Add("mock trace $($trace.trace_id) incomplete/unsafe") }
}
if ($mockTraces.Count -ne 5) { $errors.Add('expected five multi-turn POC traces') }

if ($mockLearning.Count -ne 3) { $errors.Add('expected three Q07 learning-flow fixtures') }
foreach ($step in $mockLearning) {
    if ($step.data_kind -ne 'synthetic_fixture' -or $step.tenant_id -ne '91000000-0000-4000-8000-000000000001') { $errors.Add("Q07 $($step.fixture_id) unsafe scope") }
    if ($step.record_kind -eq 'procedure_candidate') {
        if (-not $pocWorkOrders.ContainsKey($step.source_work_order_id) -or -not $mockCodes.ContainsKey($step.structured_profile_code)) { $errors.Add("Q07 $($step.fixture_id) source/profile missing") }
        if ($step.eligible_for_retrieval -ne $false -or $step.publication_id -or $step.document_version_id -or $step.review_status -notin @('draft', 'rejected')) { $errors.Add("Q07 $($step.fixture_id) unsafe publication") }
    } elseif ($step.record_kind -eq 'eligibility_test') {
        if ($step.self_help_attempt_created -ne $false -or $step.price_estimate_status -ne 'insufficient_data' -or @($step.eligible_procedure_versions).Count -ne 0) { $errors.Add("Q07 $($step.fixture_id) incorrectly offers self-help or price") }
    } else { $errors.Add("Q07 $($step.fixture_id) unknown record kind") }
}

$mockEvalIds = @{}
foreach ($case in @($mockEval.cases)) {
    if ($mockEvalIds.ContainsKey($case.id)) { $errors.Add("duplicate mock eval $($case.id)") }
    $mockEvalIds[$case.id] = $true
    if ($case.expect -notin @('answer', 'no_data', 'off_topic', 'trap')) { $errors.Add("mock eval $($case.id) invalid expectation") }
    if ($case.expect -eq 'answer') {
        $issueTag = @($case.tags | Where-Object { $_ -like 'TECH.*' } | Select-Object -First 1)
        if ($issueTag.Count -ne 1 -or -not $mockIssues.ContainsKey($issueTag[0])) { $errors.Add("mock eval $($case.id) missing issue tag") ; continue }
        $profile = @($mockProfiles | Where-Object { $_.issue_code -eq $issueTag[0] })[0]
        $markdown = Get-Content -LiteralPath (Join-Path $dataRoot ("rag/mock-corpus/" + $profile.document_code)) -Raw -Encoding utf8
        if (@($case.contains).Count -eq 0 -or -not $markdown.Contains([string]$case.contains[0])) { $errors.Add("mock eval $($case.id) contains not in target document") }
    }
}
if ($mockEval.version -ne 'technical-a2-mock-v1' -or @($mockEval.cases).Count -ne 18 -or @($mockEval.cases | Where-Object { $_.expect -eq 'answer' }).Count -ne 16) { $errors.Add('mock EvalDataset version/count incorrect') }

$evalIds = @{}
if ($evalDataset.version -ne 'technical-a2-v1' -or @($evalDataset.cases).Count -ne $evals.Count) { $errors.Add('EvalDataset version/count differs from JSONL') }
for ($i = 0; $i -lt $evals.Count; $i++) {
    $eval = $evals[$i]
    if ($evalIds.ContainsKey($eval.id)) { $errors.Add("duplicate eval id $($eval.id)") }
    $evalIds[$eval.id] = $true
    if ($eval.expect -notin @('answer', 'no_data', 'off_topic', 'trap')) { $errors.Add("eval $($eval.id) unknown expectation") }
    if ($eval.scope -ne '01-vinhomes' -and $eval.expect -ne 'trap') { $errors.Add("eval $($eval.id) invalid scope") }
    foreach ($code in @($eval.expected_document_codes)) {
        if (-not $documentCodes.ContainsKey($code)) { $errors.Add("eval $($eval.id) missing document $code") }
    }
    if ($eval.expect -eq 'answer' -and @($eval.expected_document_codes).Count -ne 1) { $errors.Add("eval $($eval.id) answer missing target document") }
    $runtime = @($evalDataset.cases)[$i]
    if ($null -eq $runtime -or $runtime.id -ne $eval.id -or $runtime.scope -ne $eval.scope -or $runtime.query -ne $eval.query -or $runtime.expect -ne $eval.expect -or (@($runtime.contains) -join '|') -ne (@($eval.contains) -join '|') -or (@($runtime.tags) -join '|') -ne (@($eval.tags) -join '|')) { $errors.Add("eval $($eval.id) differs from runtime EvalDataset") }
    if ($eval.expect -eq 'answer' -and $documentCodes.ContainsKey($eval.expected_document_codes[0])) {
        $target = $documentCodes[$eval.expected_document_codes[0]]
        $targetText = (@($target.sections | ForEach-Object { $_.text_vi }) -join "`n")
        if (@($eval.contains).Count -eq 0 -or -not $targetText.Contains([string]$eval.contains[0])) { $errors.Add("eval $($eval.id) contains text absent from target") }
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

if ($documents.Count -ne 1 -or @($documents[0].issue_codes).Count -ne $issueIds.Count) { $errors.Add('RAG collection does not cover all issue codes') }

foreach ($fixture in $synthetic) {
    if (-not $issueIds.ContainsKey($fixture.issue_code)) { $errors.Add("fixture $($fixture.case_id) unknown issue") }
    foreach ($sourceId in @($fixture.source_ids)) {
        if ($sourceId -and -not $sourceIds.ContainsKey($sourceId)) { $errors.Add("fixture $($fixture.case_id) missing source $sourceId") }
    }
    foreach ($factId in @($fixture.source_fact_ids)) {
        if ($factId -and -not $factIds.ContainsKey($factId)) { $errors.Add("fixture $($fixture.case_id) missing fact $factId") }
    }
}

Write-Output "issues=$($issueIds.Count) sources=$($manifest.Count) facts=$($facts.Count) rag_documents=$($documents.Count) mock_procedures=$($mockProfiles.Count) mock_pocs=$($mockPocs.Count) mock_traces=$($mockTraces.Count) mock_q07=$($mockLearning.Count) mock_tools=$($mockToolData.Count) supervision=$($supervision.Count) mock_evals=$(@($mockEval.cases).Count) public_cases=$($cases.Count) synthetic=$($synthetic.Count) evals=$($evals.Count)"
if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Output "ERROR: $_" }
    exit 1
}
Write-Output 'Validation OK'
