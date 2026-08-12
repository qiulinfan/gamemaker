# Dreamweaver profile

This disabled-by-default profile contains project and workstation facts that
must not become portable Skill defaults.

Select it only when the user or Dreamweaver repository explicitly identifies
the target as the canonical workspace recorded in `profile.toml`. Re-resolve
the path before each writing run; a copied or isolated work directory is not the
production checkout.

## Workspace adaptation

- Require all writing agents to use the canonical absolute root.
- Preserve the configured SSH remote and authentication transport.
- Verify the first write and every Git command from that root.
- Treat any artifact created only in an isolated runner directory as
  `WRONG_WORKSPACE`.

## Unity adaptation

- Use the already-running Unity Editor only when its resolved project root
  equals the canonical root.
- Do not open an isolated work directory as a Unity project.
- Do not start a second Editor or independent long-lived MCP bridge as a
  fallback.
- Re-resolve the instance after restart, domain reload, branch switch, or
  reconnect.

## Historical evidence

`case-studies/character-rig-animation-alignment.md` preserves the migrated
2026-08-11 Dream Traveler retargeting case and its 2026-08-12 animation-evidence
continuation. It is evidence for
diagnostic order and acceptance gates, not a reusable preset. Re-hash current
artifacts and never reuse its names, paths, counts, tolerances, colors, or hashes
as current truth.
