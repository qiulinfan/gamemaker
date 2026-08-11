# Google Drive mounted-folder publication

This disabled-by-default adapter publishes already validated playtest evidence
through Google Drive for Desktop. Configure `mount_root` and optional
`base_url` locally or in the target project's own profile; do not commit
credentials, cookies, private share tokens, or personal mount paths to the
portable core.

Preflight the explicitly configured values:

~~~powershell
Get-Process GoogleDriveFS -ErrorAction SilentlyContinue
Test-Path -LiteralPath '<configured absolute mount root>'
~~~

Complete a recording with:

~~~powershell
& '<skill-dir>\scripts\Invoke-WindowsPlaytestCapture.ps1' `
  -Action Complete `
  -StatePath '<capture state>' `
  -IssueId '<issue>' `
  -Revision '<revision>' `
  -Verdict PASS `
  -Summary '<evidence-based summary>' `
  -PublishRoot '<configured absolute mount root>' `
  -PublishBaseUrl '<optional folder URL>' `
  -PublishProcessName 'GoogleDriveFS'
~~~

`PUBLISHED_TO_MOUNT` means the script copied and hash-verified the MP4 and
receipt in the mounted directory. It does not prove that Drive completed remote
sync. Claim remote visibility only after a Drive API, connector, or browser
independently sees the object.

If the process or mount is unavailable, retain `VALIDATED_LOCAL` evidence and
report the returned publish blocker. Do not change the core Skill or script
defaults to embed a workstation path.
