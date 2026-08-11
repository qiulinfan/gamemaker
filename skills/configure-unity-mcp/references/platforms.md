# Cross-platform setup

## Contents

1. Shared requirements
2. macOS
3. Windows
4. Linux
5. Codex configuration scope
6. Networking and process checks
7. Moving the skill to another machine

## Shared requirements

Use the same architecture on every OS:

```text
Codex client
  → http://127.0.0.1:8080/mcp
  → Python/FastMCP server launched by MCP for Unity
  → WebSocket bridge
  → Unity Editor package
```

Required components:

- a Unity Editor version that supports the project;
- Git, because the Unity package is normally installed from a Git URL;
- Codex Desktop or CLI;
- `uv` and `uvx`;
- loopback TCP access;
- a writable Unity generated-cache area;
- permission to launch a background Python process.

Always verify current official installation instructions. Package managers and supported Unity/OS versions change.

## macOS

### Install uv

Preferred:

```text
brew install uv
```

Official standalone installer:

```text
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the shell if the installer changes `PATH`. Verify `uv` and `uvx`.

### Common Unity paths

Unity Hub editors commonly live at:

```text
/Applications/Unity/Hub/Editor/<version>/Unity.app/Contents/MacOS/Unity
```

The user may install Hub or Editors elsewhere. Read Hub configuration instead of assuming this path.

### Process and port inspection

```text
lsof -nP -iTCP:8080 -sTCP:LISTEN
ps aux | grep mcp-for-unity
```

Unity Editor logs are commonly under the user's Library, while this integration also writes project-local launch logs under:

```text
Library/MCPForUnity/Logs/
```

macOS Accessibility permission is needed only for UI automation. MCP itself does not require Accessibility permission.

### Safe cache moves

With Unity closed:

```text
mv Library/Bee /tmp/<project>-Bee-backup-<timestamp>
```

If a full reimport is required:

```text
mv Library /tmp/<project>-Library-backup-<timestamp>
```

Use an explicit project path and a unique backup destination. Never use a broad or unresolved variable as the move/delete target.

## Windows

### Install uv

Preferred WinGet route when available:

```text
winget install --id=astral-sh.uv -e
```

Official PowerShell installer:

```text
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new PowerShell session and verify:

```text
uv --version
uvx --version
```

### Common Unity paths

Unity Hub editors commonly live at:

```text
C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe
```

Do not assume the system drive or installation root. Unity Hub supports custom locations.

### Process and port inspection

PowerShell:

```text
Get-NetTCPConnection -LocalPort 8080 -State Listen
Get-Process Unity, python, uv -ErrorAction SilentlyContinue
```

Fallback:

```text
netstat -ano | findstr :8080
tasklist /FI "PID eq <pid>"
```

If Windows Defender Firewall prompts for Python, loopback-only access should be sufficient. Do not expose the server publicly just to clear the prompt.

### Git URL and credentials

Unity Package Manager requires Git on `PATH`. Test:

```text
git --version
git ls-remote https://github.com/CoplayDev/unity-mcp.git
```

Corporate TLS inspection, proxies, or credential helpers can break UPM Git dependencies before MCP code ever compiles.

### Safe cache moves

Close Unity, Hub project operations, IDEs, and test runners first.

```text
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Move-Item -LiteralPath ".\Library\Bee" -Destination "$env:TEMP\unity-project-Bee-$stamp"
```

For a full generated-cache rebuild:

```text
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
Move-Item -LiteralPath ".\Library" -Destination "$env:TEMP\unity-project-Library-$stamp"
```

Replace `unity-project` with a safe name derived from the actual project.

Long path policies and antivirus scans can make Unity imports appear stuck. Inspect Editor logs and disk activity before interrupting.

## Linux

### Install uv

Official installer:

```text
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Some distributions package `uv`, but repository versions may lag. Verify against official uv releases.

### Unity availability

Unity Hub and Editor support only specific Linux distributions and desktop environments. Verify the exact Editor stream's current system requirements before installation. Headless/batch-mode Unity is not a substitute for full Game View and Inspector workflows.

Common custom locations include:

```text
~/Unity/Hub/Editor/<version>/Editor/Unity
/opt/unityhub/
```

### Process and port inspection

```text
ss -ltnp | grep ':8080'
lsof -nP -iTCP:8080 -sTCP:LISTEN
ps -ef | grep mcp-for-unity
```

### Display-session considerations

- Full Game View capture requires a graphical Unity Editor session.
- Wayland/X11 behavior can affect UI automation, not normal MCP calls.
- Remote desktop or containerized sessions may lack GPU/graphics features even when the MCP server connects.
- If Unity uses software rendering, treat render failures separately from bridge failures.

### Safe cache moves

With Unity closed:

```text
mv Library/Bee "/tmp/<project>-Bee-$(date +%Y%m%d-%H%M%S)"
mv Library "/tmp/<project>-Library-$(date +%Y%m%d-%H%M%S)"
```

Perform only the first move initially. Move the full Library only if targeted Bee recovery fails.

## Codex configuration scope

Preferred project configuration:

```text
<project>/.codex/config.toml
```

This makes the Unity server available only when Codex operates in that trusted project. A user-global entry under the Codex home directory affects every project and may create connection noise when Unity is closed.

Use one `unityMCP` definition per effective configuration. After plugin-assisted client configuration:

1. inspect the project config;
2. inspect the global config;
3. run `codex mcp list` inside and outside the project;
4. keep only the intended scope.

Codex Desktop and existing tasks may cache the tool schema. Restart Codex after adding or changing the MCP server.

## Networking and process checks

The normal endpoint is loopback-only:

```text
http://127.0.0.1:8080/mcp
```

Check all four layers independently:

1. the port is listening;
2. the HTTP MCP handshake succeeds;
3. Unity registered its plugin session;
4. Unity-side tools/resources are available.

A listening Python process alone is not proof that Unity is connected. Conversely, a Unity package window showing “configured” is not proof that Codex loaded the tool schema.

When port 8080 is occupied:

- identify the owning PID;
- determine whether it is a valid server for another Unity project;
- stop it through its owning application when possible;
- otherwise choose a different port and update both Unity and Codex consistently.

Do not bind to `0.0.0.0` unless remote access is explicitly required and secured.

## Moving the product to another machine

Clone the complete `gamemaker` product repository on the target machine. From
that checkout run `scripts/link.ps1` with PowerShell 7+ on Windows, or
`scripts/link.sh` on POSIX, followed by the matching `doctor` command. The
bundle linker installs direct working-tree links for the complete manifest,
including this Skill, namespaced agents, and the canonical product root used to
discover workflows and profiles.

Do not copy this individual Skill into `${CODEX_HOME}/skills`. A real copied
directory conflicts with the bundle's ownership-safe linker, goes stale when
the checkout changes, and omits the manifest/workflow/agent contract. Set
`CODEX_HOME` before running the linker when using a non-default Codex home.

Do not copy generated Unity `Library/` state between operating systems. Copy only version-controlled project files, then let the target Unity Editor rebuild generated caches locally.
