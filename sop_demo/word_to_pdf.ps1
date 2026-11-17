param([Parameter(Mandatory=$true)][string]$Source,[Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $inputPath = [IO.Path]::GetFullPath($Source)
    $outputPath = [IO.Path]::GetFullPath($Destination)
    $confirm = $false
    $readOnly = $true
    $addRecent = $false
    $document = $word.Documents.Open([ref]$inputPath, [ref]$confirm, [ref]$readOnly, [ref]$addRecent)
    $document.ExportAsFixedFormat($outputPath, 17)
} finally {
    $save = 0
    if ($null -ne $document) { $document.Close([ref]$save); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit([ref]$save); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
