Get-ChildItem -Path ".\tests\*.py" | ForEach-Object {
  Write-Host "Running tests in $($_.FullName)"
  try {
      # Run the Python unittest command
      python -m unittest $_.FullName

      # Check if the previous command succeeded
      if ($LASTEXITCODE -ne 0) {
          throw "Tests failed in $($_.FullName)"
      }
  } catch {
      # Stop the loop and return the error
      Write-Error $_
      exit 1
  }
}