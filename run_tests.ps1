Get-ChildItem -Path ".\tests\*.py" | ForEach-Object {
    Write-Host "Running tests in $($_.FullName)"
    python -m unittest $_.FullName
}