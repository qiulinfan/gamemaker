from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "create-2d-game-art"
PIPELINE = SKILL / "scripts" / "sprite_pipeline.py"
EXAMPLE = SKILL / "assets" / "examples"


class Create2DGameArtContractTests(unittest.TestCase):
    def test_skill_owns_standalone_2d_and_hands_unity_off(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for marker in (
            "standalone 2D",
            "sprite sheets",
            "tilesets",
            "$search-game-art",
            "$auto-ta",
            "$build-unity-scene",
            "This Skill does not mutate Unity",
            "Match user-facing explanations",
        ):
            self.assertIn(marker, text)
        script = PIPELINE.read_text(encoding="utf-8")
        self.assertIn("# /// script", script)
        self.assertIn('"numpy>=2.0,<3"', script)
        self.assertIn('"pillow>=11,<13"', script)
        self.assertTrue((PIPELINE.parent / "sprite_pipeline.py.lock").is_file())

    def test_auto_ta_remains_3d_only_and_routes_2d(self) -> None:
        text = (ROOT / "skills" / "auto-ta" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Do not use this Skill for standalone 2D art", text)
        self.assertIn("$create-2d-game-art", text)

    def test_unity_importer_consumes_the_2d_manifest_contract(self) -> None:
        skill = (ROOT / "skills" / "build-unity-scene" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        reference = (
            ROOT
            / "skills"
            / "build-unity-scene"
            / "references"
            / "2d-sprite-import.md"
        ).read_text(encoding="utf-8")
        self.assertIn("references/2d-sprite-import.md", skill)
        for marker in (
            "TextureImporterType.Sprite",
            "SpriteImportMode.Multiple",
            "Sprite Editor Data Provider API",
            "unity_y = sheet_height - rect_px_top_left.y - rect_px_top_left.height",
            "pivot_normalized_x",
            "duration_ms",
            "SpriteRenderer.sprite",
            "delivery hash",
        ):
            self.assertIn(marker, reference)

    def test_receipt_and_handoff_share_closed_status_and_gate_enums(self) -> None:
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        handoff = (ROOT / "workflows" / "handoff-contract.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("status `prototype`", skill)
        self.assertIn("never as a fifth status value", skill)
        self.assertIn("required: true", handoff)
        self.assertIn("pass|fail|not_tested|not_applicable", handoff)
        self.assertIn("reason:", handoff)

    def test_legacy_source_revision_and_exclusions_are_recorded(self) -> None:
        manifest = (ROOT / "workflow.bundle.toml").read_text(encoding="utf-8")
        for marker in (
            "https://github.com/qiulinfan/ImageToPixel.git",
            "152bab66d3def65e6eaa5cd6ba97c00ac754ee31",
            'source_license = "none_declared"',
            "migrated_project_assets = false",
            "migrated_notebooks = false",
        ):
            self.assertIn(marker, manifest)

    def test_sprite_search_has_source_tiers_and_file_level_evidence(self) -> None:
        search_skill = (
            ROOT / "skills" / "search-game-art" / "SKILL.md"
        ).read_text(encoding="utf-8")
        source_map = (
            ROOT
            / "skills"
            / "search-game-art"
            / "references"
            / "2d-sprite-sources.md"
        ).read_text(encoding="utf-8")
        self.assertIn("references/2d-sprite-sources.md", search_skill)
        self.assertIn("$create-2d-game-art", search_skill)
        for marker in (
            "Tier A",
            "Tier B",
            "Tier C",
            "Kenney",
            "OpenGameArt",
            "itch.io",
            "GameDev Market",
            "Unity Asset Store",
            "Fab",
            "editable_sources_claimed",
            "editable_sources_verified",
            "exact_download_filename",
        ):
            self.assertIn(marker, source_map)


class SpritePipelineIntegrationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.assertIsNotNone(
            shutil.which("uv"),
            "uv is a required Gamemaker runtime; run doctor before tests",
        )
        temp_parent = ROOT / "Temp"
        temp_parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="create-2d-art-", dir=temp_parent
        )
        self.root = Path(self.temporary.name)
        self.output_root = self.root / "output"
        self.output_root.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_pipeline(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["UV_NO_PROGRESS"] = "1"
        return subprocess.run(
            [shutil.which("uv") or "uv", "run", str(PIPELINE), *arguments],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )

    def example_build_arguments(self) -> list[str]:
        return [
            "build",
            "--frame-data",
            str(EXAMPLE / "orb-frames.json"),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--fit",
            "contain",
            "--anchor",
            "bottom-center",
            "--resample",
            "nearest",
            "--background",
            "corner-connected",
            "--background-tolerance",
            "8",
            "--alpha-threshold",
            "1",
            "--palette",
            "oklab",
            "--colors",
            "5",
            "--seed",
            "123",
            "--columns",
            "2",
            "--padding",
            "1",
            "--pivot",
            "bottom-center",
            "--output-root",
            str(self.output_root),
            "--output",
            "orb.png",
            "--manifest",
            "orb.json",
            "--preview",
            "orb-preview.png",
            "--preview-scale",
            "4",
        ]

    def test_committed_example_rebuilds_deterministically_and_audits(self) -> None:
        built = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, built.returncode, msg=built.stderr)
        manifest = json.loads((self.output_root / "orb.json").read_text(encoding="utf-8"))
        committed = json.loads(
            (EXAMPLE / "generated" / "orb-idle-sheet.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            committed["artifact"]["rgba_sha256"],
            manifest["artifact"]["rgba_sha256"],
        )
        self.assertEqual(
            committed["artifact"]["sha256"],
            hashlib.sha256((self.output_root / "orb.png").read_bytes()).hexdigest(),
        )
        self.assertEqual("PNG", manifest["artifact"]["format"])
        self.assertEqual("RGBA", manifest["artifact"]["mode"])
        self.assertEqual(
            ["orb_idle_0", "orb_idle_1"],
            [frame["id"] for frame in manifest["frames"]],
        )
        self.assertEqual([35, 18], manifest["artifact"]["size_px"])
        self.assertEqual(5, manifest["artifact"]["palette_color_count_visible"])
        self.assertEqual(144, manifest["artifact"]["alpha"]["fully_opaque_pixels"])
        self.assertTrue(
            all(frame["duration_ms"] == 140 for frame in manifest["frames"])
        )

        def strings(value: object) -> list[str]:
            if isinstance(value, str):
                return [value]
            if isinstance(value, dict):
                return [item for child in value.values() for item in strings(child)]
            if isinstance(value, list):
                return [item for child in value for item in strings(child)]
            return []

        for value in strings(manifest):
            self.assertFalse(Path(value).is_absolute(), msg=value)
            self.assertNotIn(str(Path.home()), value)

        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "orb.png"),
            "--manifest",
            str(self.output_root / "orb.json"),
            "--output-root",
            str(self.output_root),
            "--output",
            "orb-audit.json",
        )
        self.assertEqual(0, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "orb-audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual("pass", report["verdict"])
        self.assertTrue(all(check["result"] == "pass" for check in report["checks"]))

    def test_existing_output_and_output_escape_are_rejected(self) -> None:
        first = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, first.returncode, msg=first.stderr)
        replay = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(2, replay.returncode)
        self.assertIn("refusing to overwrite", replay.stderr)

        escaped = self.run_pipeline(
            "pixelize",
            "--input",
            str(EXAMPLE / "source" / "orb-idle-0.ppm"),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "../escaped.png",
            "--manifest",
            "escaped.json",
        )
        self.assertEqual(2, escaped.returncode)
        self.assertIn("escapes --output-root", escaped.stderr)
        self.assertFalse((self.root / "escaped.png").exists())

        nonportable = self.run_pipeline(
            "pixelize",
            "--input",
            str(EXAMPLE / "source" / "orb-idle-0.ppm"),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "bad\\name.png",
            "--manifest",
            "bad.json",
        )
        self.assertEqual(2, nonportable.returncode)
        self.assertIn("output path is not portable", nonportable.stderr)

        audit_alias = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "orb.png"),
            "--manifest",
            str(self.output_root / "orb.json"),
            "--output-root",
            str(self.output_root),
            "--output",
            "ORB.JSON",
            "--force",
        )
        self.assertEqual(2, audit_alias.returncode)
        self.assertIn("audit output must differ from its inputs", audit_alias.stderr)

    def test_audit_reports_tampered_png_as_failure(self) -> None:
        built = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, built.returncode, msg=built.stderr)
        shutil.copy2(
            EXAMPLE / "generated" / "orb-idle-preview.png",
            self.output_root / "orb.png",
        )
        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "orb.png"),
            "--manifest",
            str(self.output_root / "orb.json"),
            "--output-root",
            str(self.output_root),
            "--output",
            "tamper-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "tamper-audit.json").read_text(encoding="utf-8")
        )
        self.assertEqual("fail", report["verdict"])
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("artifact.sha256", failures)
        self.assertIn("artifact.rgba_sha256", failures)

    def test_audit_rejects_rgb_encoded_artifact_with_matching_rgba_pixels(self) -> None:
        converted = self.run_pipeline(
            "pixelize",
            "--input",
            str(EXAMPLE / "source" / "orb-idle-0.ppm"),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--background",
            "keep",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "encoded-mode.png",
            "--manifest",
            "encoded-mode.json",
        )
        self.assertEqual(0, converted.returncode, msg=converted.stderr)
        image_path = self.output_root / "encoded-mode.png"
        rewrite = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--with",
                "pillow>=11,<13",
                "python",
                "-c",
                (
                    "from pathlib import Path; from PIL import Image; import sys; "
                    "p=Path(sys.argv[1]); "
                    "im=Image.open(p); im.load(); im.convert('RGB').save(p, format='PNG')"
                ),
                str(image_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, rewrite.returncode, msg=rewrite.stderr)
        manifest_path = self.output_root / "encoded-mode.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact"]["sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        audit = self.run_pipeline(
            "audit",
            "--image",
            str(image_path),
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(self.output_root),
            "--output",
            "encoded-mode-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "encoded-mode-audit.json").read_text(encoding="utf-8")
        )
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("artifact.mode", failures)

    def test_audit_rejects_tiff_bytes_behind_png_name(self) -> None:
        built = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, built.returncode, msg=built.stderr)
        image_path = self.output_root / "orb.png"
        rewritten = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--with",
                "pillow>=11,<13",
                "python",
                "-c",
                (
                    "from pathlib import Path; from PIL import Image; import sys; "
                    "p=Path(sys.argv[1]); im=Image.open(p); im.load(); "
                    "im.save(p, format='TIFF')"
                ),
                str(image_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, rewritten.returncode, msg=rewritten.stderr)
        manifest_path = self.output_root / "orb.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifact"]["sha256"] = hashlib.sha256(image_path.read_bytes()).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        audit = self.run_pipeline(
            "audit",
            "--image",
            str(image_path),
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(self.output_root),
            "--output",
            "format-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "format-audit.json").read_text(encoding="utf-8")
        )
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("artifact.format", failures)

    def test_audit_rejects_preview_aliasing_the_delivery(self) -> None:
        built = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, built.returncode, msg=built.stderr)
        manifest_path = self.output_root / "orb.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["preview"] = {
            "path": "orb.png",
            "scale": 1,
            "sha256": manifest["artifact"]["sha256"],
            "size_px": manifest["artifact"]["size_px"],
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "orb.png"),
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(self.output_root),
            "--output",
            "preview-binding-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "preview-binding-audit.json").read_text(
                encoding="utf-8"
            )
        )
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("preview.path_binding", failures)

    def test_audit_rejects_a_hash_consistent_forged_preview(self) -> None:
        built = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, built.returncode, msg=built.stderr)
        preview_path = self.output_root / "orb-preview.png"
        forged = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--with",
                "pillow>=11,<13",
                "python",
                "-c",
                (
                    "from PIL import Image; import sys; "
                    "Image.new('RGBA',(140,72),(0,255,0,255)).save(sys.argv[1])"
                ),
                str(preview_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, forged.returncode, msg=forged.stderr)
        manifest_path = self.output_root / "orb.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["preview"]["sha256"] = hashlib.sha256(
            preview_path.read_bytes()
        ).hexdigest()
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "orb.png"),
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(self.output_root),
            "--output",
            "forged-preview-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "forged-preview-audit.json").read_text(
                encoding="utf-8"
            )
        )
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("preview.content", failures)

    def test_audit_rejects_manifest_frame_digest_tampering(self) -> None:
        built = self.run_pipeline(*self.example_build_arguments())
        self.assertEqual(0, built.returncode, msg=built.stderr)
        manifest_path = self.output_root / "orb.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["frames"][0]["processed_rgba_sha256"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "orb.png"),
            "--manifest",
            str(manifest_path),
            "--output-root",
            str(self.output_root),
            "--output",
            "manifest-tamper-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "manifest-tamper-audit.json").read_text(
                encoding="utf-8"
            )
        )
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("frame.0.rgba_sha256", failures)
        self.assertIn("artifact.binding", failures)

    def test_audit_rejects_source_and_processing_contract_tampering(self) -> None:
        for name, mutate in (
            (
                "source",
                lambda manifest: manifest["frames"][0]["source"].__setitem__(
                    "sha256", "0" * 64
                ),
            ),
            (
                "processing",
                lambda manifest: manifest["contract"]["processing"].__setitem__(
                    "contrast", 1.5
                ),
            ),
        ):
            with self.subTest(name=name):
                case_root = self.root / name
                case_root.mkdir()
                original_root = self.output_root
                self.output_root = case_root
                try:
                    built = self.run_pipeline(*self.example_build_arguments())
                    self.assertEqual(0, built.returncode, msg=built.stderr)
                    manifest_path = case_root / "orb.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    mutate(manifest)
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    audit = self.run_pipeline(
                        "audit",
                        "--image",
                        str(case_root / "orb.png"),
                        "--manifest",
                        str(manifest_path),
                        "--output-root",
                        str(case_root),
                        "--output",
                        "binding-audit.json",
                    )
                    self.assertEqual(1, audit.returncode, msg=audit.stderr)
                    report = json.loads(
                        (case_root / "binding-audit.json").read_text(encoding="utf-8")
                    )
                    failures = {
                        check["id"]
                        for check in report["checks"]
                        if check["result"] == "fail"
                    }
                    self.assertIn("artifact.binding", failures)
                finally:
                    self.output_root = original_root

    def test_pixelize_binding_rejects_replaced_pixels_with_self_consistent_facts(self) -> None:
        converted = self.run_pipeline(
            "pixelize",
            "--input",
            str(EXAMPLE / "source" / "orb-idle-0.ppm"),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--background",
            "keep",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "bound.png",
            "--manifest",
            "bound.json",
        )
        self.assertEqual(0, converted.returncode, msg=converted.stderr)
        forged = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--with",
                "pillow>=11,<13",
                "python",
                "-c",
                (
                    "import hashlib,json,sys; from pathlib import Path; "
                    "from PIL import Image; from PIL.PngImagePlugin import PngInfo; "
                    "p=Path(sys.argv[1]); m=Path(sys.argv[2]); old=Image.open(p); "
                    "binding=old.info['create-2d-game-art-binding-sha256']; "
                    "im=Image.new('RGBA',old.size,(0,255,0,255)); info=PngInfo(); "
                    "info.add_text('create-2d-game-art-binding-sha256',binding); "
                    "im.save(p,format='PNG',pnginfo=info,compress_level=9); "
                    "raw=im.tobytes(); d=hashlib.sha256(); d.update(b'RGBA\\0'); "
                    "d.update(im.width.to_bytes(8,'big')); d.update(im.height.to_bytes(8,'big')); "
                    "d.update(raw); data=json.loads(m.read_text()); a=data['artifact']; "
                    "a['sha256']=hashlib.sha256(p.read_bytes()).hexdigest(); "
                    "a['rgba_sha256']=d.hexdigest(); a['palette_color_count_visible']=1; "
                    "a['alpha']={'fully_opaque_pixels':im.width*im.height,"
                    "'fully_transparent_pixels':0,'partially_transparent_pixels':0}; "
                    "m.write_text(json.dumps(data,indent=2,sort_keys=True)+'\\n')"
                ),
                str(self.output_root / "bound.png"),
                str(self.output_root / "bound.json"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, forged.returncode, msg=forged.stderr)
        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "bound.png"),
            "--manifest",
            str(self.output_root / "bound.json"),
            "--output-root",
            str(self.output_root),
            "--output",
            "bound-audit.json",
        )
        self.assertEqual(1, audit.returncode, msg=audit.stderr)
        report = json.loads(
            (self.output_root / "bound-audit.json").read_text(encoding="utf-8")
        )
        failures = {check["id"] for check in report["checks"] if check["result"] == "fail"}
        self.assertIn("artifact.binding", failures)

    def test_single_image_pixelize_median_cut_round_trip(self) -> None:
        converted = self.run_pipeline(
            "pixelize",
            "--input",
            str(EXAMPLE / "source" / "orb-idle-0.ppm"),
            "--frame-width",
            "12",
            "--frame-height",
            "8",
            "--fit",
            "cover",
            "--anchor",
            "center",
            "--resample",
            "nearest",
            "--background",
            "corner-connected",
            "--background-tolerance",
            "8",
            "--palette",
            "median-cut",
            "--colors",
            "4",
            "--dither",
            "--output-root",
            str(self.output_root),
            "--output",
            "single.png",
            "--manifest",
            "single.json",
            "--preview",
            "single-preview.png",
            "--preview-scale",
            "5",
            "--pivot",
            "bottom-center",
        )
        self.assertEqual(0, converted.returncode, msg=converted.stderr)
        manifest = json.loads(
            (self.output_root / "single.json").read_text(encoding="utf-8")
        )
        self.assertEqual("pixelize", manifest["operation"])
        self.assertEqual([12, 8], manifest["artifact"]["size_px"])
        self.assertLessEqual(manifest["artifact"]["palette_color_count_visible"], 4)
        self.assertEqual([6, 0], manifest["sprite"]["pivot_px_from_bottom_left"])
        self.assertEqual([60, 40], manifest["preview"]["size_px"])

        audit = self.run_pipeline(
            "audit",
            "--image",
            str(self.output_root / "single.png"),
            "--manifest",
            str(self.output_root / "single.json"),
            "--output-root",
            str(self.output_root),
            "--output",
            "single-audit.json",
        )
        self.assertEqual(0, audit.returncode, msg=audit.stderr)

    def test_force_cannot_overwrite_an_input_through_a_symlink_alias(self) -> None:
        source = self.output_root / "source.png"
        shutil.copy2(EXAMPLE / "generated" / "orb-idle-sheet.png", source)
        alias = self.output_root / "alias.png"
        try:
            alias.symlink_to(source.name)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        attempted = self.run_pipeline(
            "build",
            "--input-dir",
            str(self.output_root),
            "--pattern",
            "alias.png",
            "--frame-width",
            "35",
            "--frame-height",
            "18",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "source.png",
            "--manifest",
            "alias-overwrite.json",
            "--force",
        )
        self.assertEqual(2, attempted.returncode)
        self.assertIn("output must not overwrite an input frame", attempted.stderr)
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_force_cannot_overwrite_an_input_through_a_case_alias(self) -> None:
        source = self.output_root / "Frame.png"
        shutil.copy2(EXAMPLE / "generated" / "orb-idle-sheet.png", source)
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        attempted = self.run_pipeline(
            "build",
            "--input-dir",
            str(self.output_root),
            "--pattern",
            "Frame.png",
            "--frame-width",
            "35",
            "--frame-height",
            "18",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "frame.png",
            "--manifest",
            "case-alias.json",
            "--force",
        )
        self.assertEqual(2, attempted.returncode)
        self.assertIn("output must not overwrite an input frame", attempted.stderr)
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_input_contracts_reject_true_schema_and_ambiguous_natural_order(self) -> None:
        frames_root = self.root / "ambiguous"
        frames_root.mkdir()
        shutil.copy2(EXAMPLE / "source" / "orb-idle-0.ppm", frames_root / "frame1.ppm")
        shutil.copy2(EXAMPLE / "source" / "orb-idle-1.ppm", frames_root / "frame01.ppm")
        ambiguous = self.run_pipeline(
            "build",
            "--input-dir",
            str(frames_root),
            "--pattern",
            "*.ppm",
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "ambiguous.png",
            "--manifest",
            "ambiguous.json",
        )
        self.assertEqual(2, ambiguous.returncode)
        self.assertIn("ambiguous natural order", ambiguous.stderr)

        frame_data = self.root / "true-schema.json"
        frame_data.write_text(
            json.dumps(
                {
                    "schema_version": True,
                    "frames": [
                        {
                            "id": "frame",
                            "path": str(
                                (EXAMPLE / "source" / "orb-idle-0.ppm").relative_to(
                                    ROOT
                                )
                            ),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        true_schema = self.run_pipeline(
            "build",
            "--frame-data",
            str(frame_data),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "true.png",
            "--manifest",
            "true.json",
        )
        self.assertEqual(2, true_schema.returncode)
        self.assertIn("schema_version 1", true_schema.stderr)

    def test_oklab_nearest_centroid_assignment_is_memory_bounded(self) -> None:
        script = PIPELINE.read_text(encoding="utf-8")
        self.assertIn("OKLAB_DISTANCE_BUDGET = 1_000_000", script)
        self.assertIn("def _nearest_centroids", script)
        self.assertNotIn("data[:, None, :] - centroid_array[None, :, :]", script)
        self.assertNotIn("unique_oklab[:, None, :] - palette_oklab[None, :, :]", script)

    def test_oklab_rejects_unbounded_total_work(self) -> None:
        source = self.root / "high-entropy.ppm"
        pixels = bytearray()
        for value in range(256 * 256):
            pixels.extend((value >> 8, value & 255, (value * 131) & 255))
        source.write_bytes(b"P6\n256 256\n255\n" + pixels)
        attempted = self.run_pipeline(
            "pixelize",
            "--input",
            str(source),
            "--frame-width",
            "256",
            "--frame-height",
            "256",
            "--resample",
            "nearest",
            "--palette",
            "oklab",
            "--colors",
            "256",
            "--output-root",
            str(self.output_root),
            "--output",
            "entropy.png",
            "--manifest",
            "entropy.json",
        )
        self.assertEqual(2, attempted.returncode)
        self.assertIn("bounded work budget", attempted.stderr)

    def test_staging_cleanup_and_incomplete_rollback_preserve_recovery_files(self) -> None:
        probe = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--with",
                "numpy>=2,<3",
                "--with",
                "pillow>=11,<13",
                "python",
                "-c",
                r'''
import importlib.util, os, sys
from pathlib import Path

pipeline, source, root = map(Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("sprite_pipeline_probe", pipeline)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

original_stage_json = module._stage_json
def fail_stage_json(*_args, **_kwargs):
    raise module.PipelineError("injected stage failure")
module._stage_json = fail_stage_json
code = module.main([
    "pixelize", "--input", str(source), "--frame-width", "16",
    "--frame-height", "16", "--palette", "none", "--output-root",
    str(root), "--output", "cleanup.png", "--manifest", "cleanup.json",
])
assert code == 2
assert not list(root.glob("*.tmp")), list(root.glob("*.tmp"))
module._stage_json = original_stage_json

dest1, dest2 = root / "one.bin", root / "two.bin"
temp1, temp2 = root / "one.tmp", root / "two.tmp"
dest1.write_bytes(b"old-one"); dest2.write_bytes(b"old-two")
temp1.write_bytes(b"new-one"); temp2.write_bytes(b"new-two")
original_replace, original_unlink = module.os.replace, Path.unlink
def fail_second_install(source_path, destination_path):
    if Path(source_path) == temp2:
        raise OSError("injected install failure")
    return original_replace(source_path, destination_path)
def deny_new_destination_unlink(path, *args, **kwargs):
    if path == dest1 and path.exists() and path.read_bytes() == b"new-one":
        raise OSError("injected rollback removal failure")
    return original_unlink(path, *args, **kwargs)
module.os.replace = fail_second_install
Path.unlink = deny_new_destination_unlink
try:
    try:
        module._commit_staged([(temp1, dest1), (temp2, dest2)])
    except module.PipelineError as error:
        assert "rollback was incomplete" in str(error)
    else:
        raise AssertionError("commit unexpectedly succeeded")
finally:
    module.os.replace = original_replace
    Path.unlink = original_unlink
backups = list(root.glob(".one.bin.*.rollback"))
assert len(backups) == 1 and backups[0].read_bytes() == b"old-one", backups
assert dest1.read_bytes() == b"new-one"
assert dest2.read_bytes() == b"old-two"
''',
                str(PIPELINE),
                str(EXAMPLE / "source" / "orb-idle-0.ppm"),
                str(self.output_root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, probe.returncode, msg=probe.stdout + probe.stderr)

    def test_decompression_bomb_is_a_stable_invalid_input_error(self) -> None:
        crafted = self.root / "oversized.png"
        import struct
        import zlib

        def chunk(kind: bytes, payload: bytes) -> bytes:
            body = kind + payload
            return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

        crafted.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 20000, 10000, 8, 6, 0, 0, 0))
            + chunk(b"IEND", b"")
        )
        attempted = self.run_pipeline(
            "pixelize",
            "--input",
            str(crafted),
            "--frame-width",
            "16",
            "--frame-height",
            "16",
            "--palette",
            "none",
            "--output-root",
            str(self.output_root),
            "--output",
            "oversized.png",
            "--manifest",
            "oversized.json",
        )
        self.assertEqual(2, attempted.returncode)
        self.assertIn("ERROR:", attempted.stderr)
        self.assertNotIn("Traceback", attempted.stderr)


if __name__ == "__main__":
    unittest.main()
