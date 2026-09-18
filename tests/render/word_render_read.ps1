<#
  word_render_read.ps1 — Word-COM RENDER reader for the LI Report Conformer acceptance harness.
  Opens a .docx in Word (invisible, read-only), reads the ACTUAL rendered state via the Word object
  model (effective fonts, table style + header fill/size/bold, list markers, field results), and emits
  JSON. This is how we verify "renders correctly", not just "XML shape is right".

  Params:
    -Path         (required) the .docx to read
    -Out          (optional) write JSON here; else JSON to stdout
    -UpdateFields (switch)   update all fields first (SLOW on big docs) so TOC/PAGEREF results are live
    -MaxTables    (int=600)  cap tables scanned
    -MaxListParas (int=25000) cap paragraphs scanned for list markers

  No writes to the source (read-only, closed without saving). Always quits Word in finally.
#>
param(
  [Parameter(Mandatory=$true)][string]$Path,
  [string]$Out,
  [switch]$UpdateFields,
  [int]$MaxTables = 600,
  [int]$MaxListParas = 25000
)
$ErrorActionPreference = 'Stop'
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$word = $null; $doc = $null
$wdFieldRef = 3; $wdFieldPageRef = 37
$result = [ordered]@{
  path=$Path; ok=$false; error=$null; timing_ms=[ordered]@{};
  counts=[ordered]@{}; fields=$null; tables=@(); table_styles=@(); lists=@(); toc_samples=@()
}
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false; $word.DisplayAlerts = 0
  try { $word.Options.UpdateFieldsAtPrint = $false } catch {}
  $doc = $word.Documents.Open($Path, $false, $true)   # ConfirmConversions=false, ReadOnly=true
  $result.timing_ms.open = $sw.ElapsedMilliseconds
  $result.counts.paragraphs = $doc.Paragraphs.Count
  $result.counts.tables = $doc.Tables.Count
  $result.counts.fields = $doc.Fields.Count

  # ---- per-table: style, nested, header row rendered state (collect distinct styles in the same pass) ----
  $seen = @{}
  $ti = 0
  foreach ($tb in $doc.Tables) {
    $ti++; if ($ti -gt $MaxTables) { break }
    $e = [ordered]@{ index=$ti }
    $sn = $null; try { $sn = $tb.Style.NameLocal } catch {}
    $e.style = $sn
    try { $e.nested = ($tb.Tables.Count -gt 0) } catch { $e.nested = $false }
    try {
      $hdr = $tb.Rows.Item(1)
      try { $e.header_repeat = [bool]$hdr.HeadingFormat } catch {}
      $c1 = $hdr.Cells.Item(1)             # read one cell, not the whole row range (much faster)
      try { $e.header_cell1_fill_bgr = $c1.Shading.BackgroundPatternColor } catch {}
      $cf = $c1.Range.Font
      try { $e.header_size = $cf.Size } catch {}     # effective (style+direct); 9999999=mixed
      try { $e.header_bold = $cf.Bold } catch {}
      try { $e.header_name = $cf.Name } catch {}
    } catch { $e.header_error = $_.Exception.Message }
    $result.tables += $e
    # distinct-style firstRow conditional (style-driven header teal). wdFirstRow = 1.
    if ($sn -and -not $seen.ContainsKey($sn)) {
      $seen[$sn] = $true
      $se = [ordered]@{ name=$sn; firstrow_fill_bgr=$null; firstrow_bold=$null; firstrow_size=$null }
      try {
        $c = $doc.Styles.Item($sn).Table.Condition(1)
        try { $se.firstrow_fill_bgr = $c.Shading.BackgroundPatternColor } catch {}
        try { $se.firstrow_bold = $c.Font.Bold } catch {}
        try { $se.firstrow_size = $c.Font.Size } catch {}
      } catch {}
      $result.table_styles += $se
    }
  }
  $result.timing_ms.tables = $sw.ElapsedMilliseconds

  # ---- optional field update (SLOW) + TOC/PAGEREF/REF summary ----
  if ($UpdateFields) {
    try { $doc.Fields.Update() | Out-Null } catch {}
    foreach ($toc in $doc.TablesOfContents) { try { $toc.Update() } catch {} }
    foreach ($tof in $doc.TablesOfFigures) { try { $tof.Update() } catch {} }
    $result.timing_ms.fields_update = $sw.ElapsedMilliseconds
  }
  $pr=0;$pr1=0;$prBlank=0;$rf=0;$rfe=0
  foreach ($f in $doc.Fields) {
    $t=$f.Type; $r=''; try { $r=$f.Result.Text } catch {}
    if ($t -eq $wdFieldPageRef) { $pr++; $rt=$r.Trim(); if ($rt -eq '1'){$pr1++} elseif ($rt -eq ''){$prBlank++} }
    if ($t -eq $wdFieldRef) { $rf++; if ($r -like '*Bookmark not found*'){$rfe++} }
  }
  $result.fields = [ordered]@{
    updated=[bool]$UpdateFields; pageref_total=$pr; pageref_showing_1=$pr1; pageref_blank=$prBlank;
    ref_total=$rf; ref_bookmark_errors=$rfe
  }
  # sample the List of Tables / TOF and TOC text (first 600 chars each) as concrete evidence
  foreach ($tof in $doc.TablesOfFigures) {
    $txt=''; try { $txt=$tof.Range.Text } catch {}
    $result.toc_samples += [ordered]@{ kind='TableOfFigures'; text=$txt.Substring(0,[Math]::Min(600,$txt.Length)) }
  }
  foreach ($toc in $doc.TablesOfContents) {
    $txt=''; try { $txt=$toc.Range.Text } catch {}
    $result.toc_samples += [ordered]@{ kind='TableOfContents'; text=$txt.Substring(0,[Math]::Min(600,$txt.Length)) }
  }

  # ---- lists: iterate ONLY list paragraphs (Document.ListParagraphs) — fast; classify by the rendered
  #      marker (ListString), NOT ListType (which reports the list DEFINITION, e.g. 4=outline, for both
  #      bullets and numbers in a multilevel list). ----
  $li=0
  $lps = $doc.ListParagraphs
  $lpcount = $lps.Count
  foreach ($p in $lps) {
    $li++; if ($li -gt $MaxListParas) { break }
    $e = [ordered]@{}
    try { $e.style = $p.Style.NameLocal } catch {}
    $lf = $p.Range.ListFormat
    try { $e.marker = $lf.ListString } catch { $e.marker = $null }
    try { $e.list_type = $lf.ListType } catch { $e.list_type = $null }
    $tx=''; try { $tx=$p.Range.Text } catch {}
    $e.text = $tx.Substring(0,[Math]::Min(45,$tx.Length))
    $result.lists += $e
  }
  $result.counts.list_paragraphs = $lpcount
  $result.counts.list_items = $li
  $result.timing_ms.total = $sw.ElapsedMilliseconds
  $result.ok = $true
}
catch { $result.error = $_.Exception.Message }
finally {
  if ($doc) { try { $doc.Close($false) } catch {} }
  if ($word) { try { $word.Quit() } catch {} }
}
$json = $result | ConvertTo-Json -Depth 8
if ($Out) { [System.IO.File]::WriteAllText($Out, $json, [System.Text.Encoding]::UTF8) } else { $json }
