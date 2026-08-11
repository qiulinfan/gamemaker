---
name: record-windows-playtest
description: Record a bounded Windows Unity playtest as a validated local MP4 and generate a source-traceable JSON receipt, with optional publication to an explicitly configured mounted destination. Use after a player-facing build, scene, feature, or fix is ready for independent play evidence; do not use to implement or repair the game, and never assume a cloud provider or project-specific path.
---

# Record Windows Playtest

Produce reviewable video evidence for an independent Unity playtest on Windows.
Pair this Skill with `play-unity-game`: that Skill defines and executes what to
test; this Skill records the named target window, validates the artifact, and
optionally copies it to an authorized mounted destination.

## Preserve the boundary

- Run only on Windows.
- Test an explicit issue, revision, build or scene, and acceptance contract.
- Prefer a standalone Windows player. Capture the Unity Editor only when no
  representative player exists, and disclose that fallback.
- Record only the exact named game or Unity window. Never capture the desktop,
  credentials, messages, notifications, webcam, or microphone.
- Do not add system-wide audio drivers or persistent recording software.
- Do not edit scripts, scenes, prefabs, assets, packages, settings, or design
  documents. Report defects to the owning agent.
- Distinguish `VALIDATED_LOCAL` from `PUBLISHED_TO_MOUNT` and from any
  independently confirmed remote state.
- Load a publishing profile only when the user or target repository explicitly
  selects it. Local validation is the portable default.

## Resolve required inputs

Obtain or derive:

- issue ID and test objective;
- exact repository or build path and target revision;
- scene, build, or launch instructions;
- observable acceptance cases, including reset/recovery when stateful;
- exact capture window title;
- planned recording duration;
- absolute local staging directory;
- optional mounted publish root, base URL, and owning sync-process name from an
  explicitly selected profile.

Return `BLOCKED` rather than inventing a playable target or pass criterion.

## Establish a clean target

Use `play-unity-game` to inspect project guidance, choose the closest
player-like input path, clear stale diagnostics, and confirm the target is ready.
Record the exact revision. Do not accept implementer prose as evidence.

For player-visible stateful work, plan at least:

1. intended path;
2. one invalid or boundary action;
3. recovery from that action;
4. reset or reload;
5. a second complete intended path after reset.

## Preflight the recorder

This Skill requires PowerShell 7 or newer (`pwsh`); Windows PowerShell 5.1 is
unsupported. The script has both a `#requires -Version 7.0` directive and a
runtime version gate, so an older host fails before starting FFmpeg or writing
state. Confirm the runtime, recorder, and exact target window:

```powershell
pwsh --version
Get-Command ffmpeg, ffprobe -ErrorAction SilentlyContinue
Get-Process | Where-Object { $_.MainWindowTitle -eq '<exact window title>' } |
  Select-Object Id, ProcessName, MainWindowTitle
```

Do not print unrelated window titles. If `ffmpeg` is not on `PATH`, the
bundled script also searches the standard WinGet FFmpeg package directory under
`%LOCALAPPDATA%`.

When a publishing profile is selected, validate only its configured mount and
optional sync process. Do not probe unrelated cloud folders or processes.

## Start a bounded capture

Keep staging outside the game repository when possible. The script starts
FFmpeg in a hidden process and stops at the requested duration:

```powershell
$start = & '<skill-dir>\scripts\Invoke-WindowsPlaytestCapture.ps1' `
  -Action Start `
  -WindowTitle '<exact window title>' `
  -OutputDirectory '<absolute staging directory>' `
  -BaseName '<issue-id>-playtest' `
  -DurationSeconds 180 `
  -Framerate 30 | ConvertFrom-Json
```

Retain `$start.state_path`. Never broaden an unresolved title to desktop
capture.

## Play the acceptance cases

Immediately execute the planned cases with player-like input. Keep the target
visible and unminimized. Narration is optional and is not captured; make state
changes readable through the game UI and written receipt.

If a crash, hang, or blocker occurs, preserve the recording and finish it with
verdict `FAIL` or `BLOCKED`. Do not repair the defect in this workflow.

## Validate locally

After FFmpeg reaches its bound, finalize without publishing:

```powershell
$result = & '<skill-dir>\scripts\Invoke-WindowsPlaytestCapture.ps1' `
  -Action Complete `
  -StatePath $start.state_path `
  -IssueId '<issue-id>' `
  -Revision '<commit, changelist, or build identifier>' `
  -Verdict PASS `
  -Summary '<short evidence-based result>' `
  -SkipPublish | ConvertFrom-Json
```

The completion action validates a readable video stream with `ffprobe`,
computes SHA-256, and writes a JSON receipt beside the MP4. The receipt uses
logical artifact IDs and relative publish identifiers only; absolute staging,
mount, and user-directory paths remain local operational state and are never
copied into a published receipt. It never overwrites a prior run.
Before mount publication it also rejects any public receipt value containing an
absolute filesystem path, the local user identity, staging root, or publish
mount. Keep local paths only in the `.capture.json` state and the final command
result, neither of which is a published artifact.

## Publish only through an explicit profile

When publication is authorized, pass the selected profile values:

```powershell
$result = & '<skill-dir>\scripts\Invoke-WindowsPlaytestCapture.ps1' `
  -Action Complete `
  -StatePath $start.state_path `
  -IssueId '<issue-id>' `
  -Revision '<revision>' `
  -Verdict PASS `
  -Summary '<evidence-based result>' `
  -PublishRoot '<absolute mounted destination>' `
  -PublishBaseUrl '<optional review URL>' `
  -PublishProcessName '<optional sync process>' | ConvertFrom-Json
```

The script verifies copied bytes. `PUBLISHED_TO_MOUNT` proves only that the
validated files reached the mounted directory. Claim remote visibility only
after an API, connector, or browser independently observes the remote object.
Provider-specific setup belongs under `profiles/`, not in this Skill.
`PublishBaseUrl` must be an absolute HTTP(S) public base without userinfo,
query parameters, or a fragment; signed/private URLs are rejected rather than
embedded in the receipt.
Never publish the `.capture.json` state file: it intentionally contains local
process and filesystem details needed to complete the bounded recording.

## Return the handoff

Report:

- verdict: `PASS`, `FAIL`, or `BLOCKED`;
- issue, target revision, scene/build, and input path;
- cases attempted and observed results;
- capture mode: standalone player or Unity Editor fallback;
- MP4 filename, duration, resolution, and SHA-256;
- receipt filename;
- delivery state exactly as returned by the script;
- selected publishing profile, mounted relative path, and review URL when used;
- defects with reproduction steps and owner routing.

## Apply failure rules

- Missing or ambiguous target window: stop before recording.
- Early recorder exit, unreadable MP4, or missing video stream: invalidate the
  evidence; retry once only after diagnosing the recorder.
- Game defect: preserve evidence and hand off; do not fix it.
- Missing publish mount or optional sync process: retain local evidence and
  report `VALIDATED_LOCAL`.
- Copy hash mismatch: retain local evidence, label the publish attempt failed,
  and remove only the incomplete current-run destination when it is safe and
  explicitly identified.
- Never accept production merely because a video exists.

Match user-facing prompts, receipts, and handoffs to the user's language unless
they request another language. Preserve identifiers, action codes, paths,
hashes, and raw errors unchanged.

Use `scripts/Invoke-WindowsPlaytestCapture.ps1` directly instead of
reimplementing FFmpeg argument handling or mounted-destination publication.
