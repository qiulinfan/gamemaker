# Programmatic source APIs

Machine-readable acquisition routes for sources whose licensing is uniform
enough to automate safely. Field-tested 2026-08-21. Everything else still goes
through the per-candidate manual license audit.

## Poly Haven (CC0 — textures, models, HDRIs)

Uniformly CC0, so programmatic acquisition is safe once provenance is
recorded. Public JSON API, no auth key:

- `https://api.polyhaven.com/assets?type=textures|models|hdris` — full
  catalog; filter locally by id keywords (e.g. `plaster`, `worn`, `damaged`).
- `https://api.polyhaven.com/info/<id>` — asset name and `authors` for the
  provenance record.
- `https://api.polyhaven.com/files/<id>` — per-map, per-resolution download
  URLs on `dl.polyhaven.org`, **including an `md5` per file** — record it next
  to a locally computed SHA-256 in the provenance table.

Practical notes:

- **Send a real `User-Agent` header.** Default Python `urllib` requests get
  HTTP 403; any descriptive UA string passes. Large batches may also hit
  transient TLS resets — retry with backoff, and skip files that already
  exist locally so reruns are idempotent.
- Useful map set for engine PBR materials: `Diffuse`, `nor_gl` (OpenGL-Y
  normal, what Godot expects), `Rough`, `AO`; 1k–2k JPEG is usually enough
  for prototype-grade surfaces.
- Record each acquisition in the target project's third-party notices with:
  creator, source page (`https://polyhaven.com/a/<id>`), license + license
  page, resolution, and the file table (direct URL, API MD5, local SHA-256).

## Non-uniform sources

Sketchfab, itch.io, OpenGameArt, asset stores: license varies per item —
never automate acquisition there; follow the standard selection → per-item
license verification → audited acquisition flow in the main Skill.
