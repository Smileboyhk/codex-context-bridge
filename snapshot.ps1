param(
  [switch]$IncludeSource,
  [switch]$Sync
)

$argsList = @("snapshot", "--run-checks")
if ($IncludeSource) { $argsList += "--include-source" }
if ($Sync) { $argsList += "--sync" }
& ccb @argsList
exit $LASTEXITCODE
