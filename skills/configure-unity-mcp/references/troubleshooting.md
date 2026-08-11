# Troubleshooting Unity MCP

## Contents

1. Use the symptom ladder
2. Codex has no Unity tools
3. Server is not listening
4. Port listens but Unity is absent
5. Unity registered but tools are missing
6. Unity does not compile
7. Stale Bee and PackageCache references
8. Visual Scripting partial-import failure
9. Play Mode and Game View issues
10. Inspector mutation safety
11. Multiple Unity instances
12. Console noise classification
13. Known-good incident baseline

## Use the symptom ladder

Diagnose from the lowest layer upward:

1. **Project baseline** — Unity opens and compiles without MCP.
2. **Package layer** — `manifest.json` and lock file resolve the plugin.
3. **Server layer** — the configured TCP port listens.
4. **Bridge layer** — the Unity plugin registers over WebSocket.
5. **MCP layer** — list-tools/list-resources succeeds.
6. **Editor layer** — scene/resources reflect live Unity state.
7. **Control layer** — Play/Stop and Game View capture work.

Do not repair an upper layer while a lower layer is still failing.

## Codex has no Unity tools

### Symptoms

- Unity plugin is installed and connected.
- `codex mcp list` may show `unityMCP`.
- The current task exposes no Unity tools.

### Causes

- Codex started before the MCP config existed.
- The current task cached its initial tool schema.
- Config was written globally but the current client reads project config, or vice versa.
- The project is not trusted.
- The endpoint omits `/mcp`.

### Recovery

1. Run `codex mcp list` from the Unity project root.
2. Confirm `http://127.0.0.1:<port>/mcp`.
3. Fully quit and restart Codex Desktop/CLI.
4. Reopen the trusted Unity project.
5. Start a fresh task if the existing task still lacks tools.

Do not keep reconfiguring Unity when the missing step is a Codex restart.

## Server is not listening

### Symptoms

- Connection refused.
- No process owns the configured port.
- Unity MCP window shows `No Session`.

### Causes

- The local server was never started.
- The first-launch confirmation was not accepted.
- `uv`/`uvx` is missing from Unity's environment.
- Python launch failed.
- The current-session server was never started. Disabled Auto-Start is expected
  unless persistent setup was explicitly authorized.

### Recovery

1. Verify `uv` and `uvx` from a fresh shell.
2. Open the MCP for Unity window.
3. Start the local HTTP server.
4. Accept the one-time background launch confirmation.
5. Inspect `Library/MCPForUnity/Logs/server-launch-<port>.log`.

This recovery is bounded current-session setup by default. Leave Auto-Start
disabled and stop the session-started bridge at handoff. Only after the user
explicitly authorizes persistent background startup may you enable Auto-Start
in the Advanced tab, restart Unity, and run acceptance Gate G to verify
persistence rather than trusting the toggle alone. Diagnose, repair, validate,
or test language does not grant that authority.

On GUI-launched macOS applications, shell profile changes may not reach Unity. Restart Unity/Hub after installing `uv`.

## Port listens but Unity is absent

### Symptoms

- Python/FastMCP listens.
- MCP handshake may work.
- Logs lack `Plugin registered`.
- Editor tools return no active Unity instance.

### Causes

- Unity is still compiling or reloading.
- The package failed to compile.
- WebSocket bridge did not reconnect after domain reload.
- Server belongs to a different Unity project.

### Recovery

1. Inspect the Unity Console and Editor log for C# errors.
2. Wait until `isCompiling` and asset updating are false.
3. Confirm the launch log's project/session identity.
4. Restart the server through the Unity plugin.
5. If multiple sessions exist, select the intended instance explicitly.
6. Restart Unity only after saving clean project state.

## Unity registered but tools are missing

### Symptoms

- Launch log contains `Plugin registered`.
- Tool count is zero or lower than expected.
- Some tool groups are unavailable.

### Causes

- Tool-group visibility settings disabled groups.
- Registration was sampled before Unity finished sending transforms.
- Unity domain reload interrupted registration.
- Client/server versions are mismatched.

### Recovery

1. Wait for the log line indicating Unity-side tools registered.
2. Read `mcpforunity://tool-groups` and `mcpforunity://custom-tools`.
3. Inspect the plugin's Tools/Resources tabs.
4. Verify package/server release alignment.
5. Restart the Unity bridge.
6. Re-run list-tools and list-resources.

Counts vary by release and enabled groups; validate required tool names rather than pinning one universal count.

## Unity does not compile

### Symptoms

- Play Mode is rejected.
- New MCP component types cannot load.
- Console contains `error CS...`.
- Package Manager resolution completes but domain reload fails.

### Causes

- The project was created on an older Unity/package combination.
- Several first-party packages use APIs removed by a newer Unity Editor.
- Package updates occurred while stale compile response files remained.
- A pre-release package has incompatible dependencies.

### Recovery

1. Save the original compiler errors.
2. Determine whether each error originates in project `Assets/` or `Library/PackageCache/`.
3. For PackageCache errors, look up the package's officially compatible release for the exact Unity stream.
4. Update the smallest coherent package set in `Packages/manifest.json`.
5. Let Unity update `packages-lock.json`.
6. Wait for domain reload and check again.
7. If errors reference removed PackageCache hashes or nonexistent files, use the cache recovery sequence below.

Do not edit code inside `Library/PackageCache`; it is generated and will be replaced.

## Stale Bee and PackageCache references

### Symptoms

- `CS2001: Source file ... could not be found`.
- The missing path contains an old package hash.
- The package exists under a different current hash.
- Unity continues compiling a removed package version.

### Cause

Bee compilation response files or the SourceAssetDB retained stale paths after live package replacement.

### Recovery sequence

1. Close Unity.
2. Confirm no Unity import/compiler process still owns the project.
3. Move `Library/Bee` to a dated temporary backup.
4. Reopen Unity and wait for compilation.
5. If stale response files persist, close Unity again.
6. Move the entire `Library` to a dated temporary backup.
7. Reopen Unity and allow a full import.
8. Inspect the new response files and compiler log.

Preserve the backups until the project opens and validates. Never move or delete `Assets`, `Packages`, or `ProjectSettings`.

## Visual Scripting partial-import failure

### Symptoms

- A Visual Scripting type such as `VisualScriptingHelpURLAttribute` is missing.
- The source file exists in the current PackageCache.
- The relevant `.rsp` file does not list it.

### Cause

The package content is correct, but Unity's generated compilation graph omitted a source file after incremental package updates.

### Recovery

1. Verify the missing source file exists in the official package.
2. Inspect the generated `.rsp` file for that assembly.
3. If the file is absent from the response file, close Unity and perform a full `Library` rebuild.
4. Confirm the new response file includes the source.
5. Confirm the latest Editor log contains no C# compiler errors.

Changing package versions repeatedly will not fix a stale compilation graph.

## Play Mode and Game View issues

### Play reports success but editor state remains changing

Some versions expose `is_changing=true` longer than expected even after `is_playing=true`. Confirm with at least two signals:

- the Play command succeeded;
- `is_playing=true`;
- Game View capture succeeds;
- runtime-only Inspector change can be read back.

Do not wait forever for one advisory flag. Use bounded polling and always Stop in a `finally` path.

### Screenshot request succeeds but file is absent

Game View capture can be asynchronous.

1. Read `data.fullPath`.
2. Poll for a non-empty file with a bounded timeout.
3. Keep output inside the project, preferably `Temp/MCPValidation`.
4. Verify the image format and dimensions.

### Screenshot contains only sky/ground

That may be correct for an empty scene. Prove the capture path, then judge scene content separately.

### Memoryless depth messages

URP/Game View capture may log messages such as:

- `Ignoring depth surface load action as it is memoryless`
- `Ignoring depth surface store action as it is memoryless`

If capture succeeds and no compiler/runtime exception follows, report these as render-path noise rather than an MCP connection failure. Investigate further when the image is corrupt or the target platform shows rendering defects.

## Inspector mutation safety

An Undo can restore a component value while leaving the scene marked dirty. Therefore:

- use read-only Inspector resources for the first smoke test;
- expect both generic and specialized mutation tools to reject writes during Play Mode in some releases;
- for a full automated test, require a clean saved scene, mutate in Edit Mode, read the value back, restore it, and reopen the same scene from disk through a tightly scoped `execute_code` call;
- reacquire instance IDs after the reload and confirm the serialized value returned;
- confirm `isDirty=false`;
- avoid saving solely to clear a test-induced dirty flag, because saving may serialize Unity version migrations.

If reopening the active scene is unacceptable, use a disposable saved test scene and restore the user's active scene afterward.

## Multiple Unity instances

### Symptoms

- Commands affect the wrong project.
- The server reports more than one instance.
- Calls fail because no active instance is selected.

### Recovery

1. Read `mcpforunity://instances`.
2. Copy the exact opaque `Name@hash` identifier.
3. Call `set_active_instance`.
4. Re-read active project and scene before mutation.

Never derive or reformat instance identifiers.

## Console noise classification

Classify before fixing:

- **Compiler errors** — `error CS...`; block all mutation requiring compiled code.
- **MCP launch/bridge errors** — block connection and registration.
- **Unity runtime exceptions** — evaluate against the tested scene.
- **Render capture notices** — may be non-blocking if output is valid.
- **Service entitlement errors** — for example Unity AI `NoSubscription`; unrelated to MCP unless that service is part of the task.
- **Historical Console entries** — clear Console immediately before a controlled test.

Report unrelated errors instead of removing unrelated packages without authorization.

## Known-good incident baseline

This skill was derived from a successful setup on 2026-07-31:

- macOS;
- Unity `6000.5.6f1`;
- MCP for Unity `v10.1.0`;
- local HTTP endpoint `http://127.0.0.1:8080/mcp`;
- FastMCP `3.4.5`;
- full handshake with 48 MCP tools and 19 resources;
- 35 Unity-side tools registered for that configuration.

The project initially contained packages too old for Unity 6.5. A coherent update included AI Navigation, Collaborate/Version Control, Input System, Timeline, and Visual Scripting. Incremental updates left stale Bee and Visual Scripting response files; moving `Library/Bee` was insufficient, while a recoverable full `Library` rebuild succeeded.

Treat these values as historical evidence, not current universal recommendations.
