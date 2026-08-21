from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "create-2d-game-art"
VALIDATOR = SKILL / "scripts" / "validate_receipt.py"
EXAMPLE_ROOT = SKILL / "assets" / "examples"
EXAMPLE_RECEIPT = EXAMPLE_ROOT / "generated" / "orb-production-receipt.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(shutil.which("uv"), "uv is required for PEP 723 dependencies")
class Create2DReceiptValidatorTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        temp_parent = ROOT / "Temp"
        temp_parent.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="create-2d-receipt-", dir=temp_parent
        )
        self.root = Path(self.temporary.name)
        for name, content in {
            "source.bin": b"source",
            "delivery.png": b"delivery",
            "manifest.json": (
                b'{"contract":{"processing":{"palette":"none"}},'
                b'"operation":"pixelize"}\n'
            ),
            "preview.png": b"preview",
            "engine-import.json": b'{"import": "pass"}\n',
        }.items():
            (self.root / name).write_bytes(content)
        self.write_audit()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def entry(self, path: str, role: str) -> dict[str, str]:
        return {"path": path, "role": role, "sha256": sha256(self.root / path)}

    def audit_data(self) -> dict:
        check_ids = {
            "schema.version",
            "schema.tool",
            "schema.operation",
            "schema.top_level",
            "artifact.record",
            "artifact.schema",
            "artifact.path",
            "artifact.path_confined",
            "artifact.path_binding",
            "artifact.sha256",
            "artifact.rgba_sha256",
            "artifact.binding",
            "artifact.size",
            "artifact.format",
            "artifact.mode",
            "artifact.palette",
            "artifact.alpha",
            "contract.record",
            "contract.schema",
            "contract.processing_schema",
            "contract.processing_values",
            "source.record",
            "sprite.record",
            "pixelize.frame_size",
        }
        return {
            "artifact": {
                "manifest_sha256": sha256(self.root / "manifest.json"),
                "png": {
                    "alpha": {
                        "fully_opaque_pixels": 1,
                        "fully_transparent_pixels": 0,
                        "partially_transparent_pixels": 0,
                    },
                    "binding_sha256": "1" * 64,
                    "format": "PNG",
                    "mode": "RGBA",
                    "palette_color_count_visible": 1,
                    "rgba_sha256": "2" * 64,
                    "size_px": [1, 1],
                },
                "png_sha256": sha256(self.root / "delivery.png"),
            },
            "checks": [
                {"id": check_id, "observed": "ok", "result": "pass"}
                for check_id in sorted(check_ids)
            ],
            "operation": "audit",
            "schema_version": 1,
            "tool": {
                "name": "create-2d-game-art.sprite-pipeline",
                "version": "1.0.0",
            },
            "verdict": "pass",
        }

    def write_audit(self, value: dict | None = None) -> None:
        (self.root / "audit.json").write_text(
            json.dumps(value if value is not None else self.audit_data(), indent=2) + "\n",
            encoding="utf-8",
        )

    def valid_receipt(self) -> dict:
        delivery = self.entry("delivery.png", "engine_delivery")
        return {
            "schema_version": 1,
            "job": {
                "id": "test-sprite-v1",
                "status": "validated",
                "contract_path": "contract.yaml",
            },
            "sources": [
                {
                    "path": "source.bin",
                    "role": "user_authored",
                    "sha256": sha256(self.root / "source.bin"),
                    "creator": "Test author",
                    "source_url": "",
                    "license": "user-owned",
                    "generation_provenance": "",
                }
            ],
            "outputs": [
                delivery,
                self.entry("manifest.json", "frame_manifest"),
                self.entry("preview.png", "preview"),
                self.entry("audit.json", "audit"),
            ],
            "implementation": {
                "tool": "create-2d-game-art.sprite-pipeline",
                "version": "1.0.0",
                "command_or_action": "deterministic test build",
                "processing_contract": {"frame_size_px": [16, 16]},
            },
            "evidence": {
                "artifact": [
                    {
                        "id": "audit",
                        "path": "audit.json",
                        "sha256": sha256(self.root / "audit.json"),
                        "description": "Structural audit",
                    }
                ],
                "visual_native_scale": [
                    {
                        "id": "preview",
                        "path": "preview.png",
                        "sha256": sha256(self.root / "preview.png"),
                        "description": "Native-scale visual inspection",
                    }
                ],
                "visual_gameplay_scale": [],
                "animation": [],
                "tileset_or_ui": [],
                "engine_import": [
                    {
                        "id": "unity-import",
                        "path": "engine-import.json",
                        "sha256": sha256(self.root / "engine-import.json"),
                        "description": "Authorized Unity import",
                        "engine_delivery_path": delivery["path"],
                        "engine_delivery_sha256": delivery["sha256"],
                        "project_revision": "0123456789abcdef",
                    }
                ],
            },
            "gates": [
                {
                    "id": "artifact.structural",
                    "required": True,
                    "result": "pass",
                    "evidence": ["artifact:audit"],
                    "reason": "",
                },
                {
                    "id": "engine.import",
                    "required": True,
                    "result": "pass",
                    "evidence": ["engine_import:unity-import"],
                    "reason": "",
                },
            ],
            "modifications": ["Normalized frames"],
            "limitations": [],
            "next_owner": "autota-technical-artist",
            "next_action": "Integrate delivery",
        }

    def run_validator(
        self, receipt: dict | None = None, *, raw: str | None = None
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        path = self.root / "receipt.yaml"
        path.write_text(
            raw if raw is not None else json.dumps(receipt, indent=2) + "\n",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["UV_NO_PROGRESS"] = "1"
        completed = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                str(VALIDATOR),
                str(path),
                "--provenance-root",
                str(self.root),
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        report = json.loads(completed.stdout) if completed.stdout else {}
        return completed, report

    def assert_problem(self, report: dict, code: str) -> None:
        self.assertIn(code, {problem["code"] for problem in report["problems"]})

    def test_pep_723_lock_and_committed_yaml_prototype(self) -> None:
        script = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn("# /// script", script)
        self.assertIn('"pyyaml>=6,<7"', script)
        self.assertTrue(VALIDATOR.with_suffix(".py.lock").is_file())
        environment = os.environ.copy()
        environment["UV_NO_PROGRESS"] = "1"
        completed = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                str(VALIDATOR),
                str(EXAMPLE_RECEIPT),
                "--provenance-root",
                str(EXAMPLE_ROOT),
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertEqual("pass", report["validation_verdict"])
        self.assertEqual("prototype", report["reduced_status"])

    def test_validated_json_binds_engine_delivery_and_revision(self) -> None:
        completed, report = self.run_validator(self.valid_receipt())
        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertEqual("pass", report["validation_verdict"])
        self.assertEqual("validated", report["reduced_status"])

    def test_failed_or_malformed_structural_audit_cannot_be_wrapped_as_validated(self) -> None:
        receipt = self.valid_receipt()
        self.write_audit({"verdict": "fail"})
        digest = sha256(self.root / "audit.json")
        next(output for output in receipt["outputs"] if output["role"] == "audit")["sha256"] = digest
        receipt["evidence"]["artifact"][0]["sha256"] = digest
        completed, report = self.run_validator(receipt)
        self.assertEqual(2, completed.returncode, msg=completed.stderr)
        self.assert_problem(report, "SCHEMA_KEYS_MISSING")

        receipt = self.valid_receipt()
        audit = self.audit_data()
        audit["checks"][0]["result"] = "fail"
        audit["verdict"] = "fail"
        self.write_audit(audit)
        digest = sha256(self.root / "audit.json")
        next(output for output in receipt["outputs"] if output["role"] == "audit")["sha256"] = digest
        receipt["evidence"]["artifact"][0]["sha256"] = digest
        completed, report = self.run_validator(receipt)
        self.assertEqual(2, completed.returncode, msg=completed.stderr)
        self.assert_problem(report, "AUDIT_VERDICT_NOT_PASS")

    def test_audit_hashes_bind_manifest_and_engine_delivery(self) -> None:
        for field, expected in (
            ("manifest_sha256", "AUDIT_MANIFEST_BINDING_MISMATCH"),
            ("png_sha256", "AUDIT_ENGINE_DELIVERY_BINDING_MISMATCH"),
        ):
            with self.subTest(field=field):
                receipt = self.valid_receipt()
                audit = self.audit_data()
                audit["artifact"][field] = "0" * 64
                self.write_audit(audit)
                digest = sha256(self.root / "audit.json")
                next(output for output in receipt["outputs"] if output["role"] == "audit")["sha256"] = digest
                receipt["evidence"]["artifact"][0]["sha256"] = digest
                completed, report = self.run_validator(receipt)
                self.assertEqual(2, completed.returncode, msg=completed.stderr)
                self.assert_problem(report, expected)

    def test_truncated_audit_check_inventory_is_rejected(self) -> None:
        receipt = self.valid_receipt()
        audit = self.audit_data()
        audit["checks"] = audit["checks"][:1]
        self.write_audit(audit)
        digest = sha256(self.root / "audit.json")
        next(output for output in receipt["outputs"] if output["role"] == "audit")["sha256"] = digest
        receipt["evidence"]["artifact"][0]["sha256"] = digest
        completed, report = self.run_validator(receipt)
        self.assertEqual(2, completed.returncode, msg=completed.stderr)
        self.assert_problem(report, "AUDIT_CHECK_INVENTORY_MISMATCH")

    def test_audit_hash_and_semantics_use_one_byte_snapshot(self) -> None:
        passing_audit = self.audit_data()
        failing_audit = json.loads(json.dumps(passing_audit))
        failing_audit["checks"][0]["result"] = "fail"
        failing_audit["verdict"] = "fail"
        self.write_audit(failing_audit)
        receipt = self.valid_receipt()
        receipt_path = self.root / "snapshot-receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        replacement_path = self.root / "replacement-audit.json"
        replacement_path.write_text(json.dumps(passing_audit), encoding="utf-8")
        harness = """
import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("receipt_validator_under_test", sys.argv[1])
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
original = module._verify_file_snapshot

def injected(*args, **kwargs):
    result = original(*args, **kwargs)
    label = args[4] if len(args) > 4 else kwargs.get("label")
    if label == "audit output" and result is not None:
        Path(sys.argv[4]).write_bytes(Path(sys.argv[3]).read_bytes())
    return result

module._verify_file_snapshot = injected
data = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
report = module._validate_receipt(data, Path(sys.argv[5]).resolve())
print(json.dumps(report, sort_keys=True))
"""
        completed = subprocess.run(
            [
                shutil.which("uv") or "uv",
                "run",
                "--with",
                "pyyaml>=6,<7",
                "python",
                "-c",
                harness,
                str(VALIDATOR),
                str(receipt_path),
                str(replacement_path),
                str(self.root / "audit.json"),
                str(self.root),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertEqual("fail", report["validation_verdict"])
        self.assert_problem(report, "AUDIT_CHECK_FAILED")
        self.assert_problem(report, "AUDIT_VERDICT_NOT_PASS")

    def test_source_and_output_file_aliases_are_rejected(self) -> None:
        receipt = self.valid_receipt()
        delivery = next(
            output for output in receipt["outputs"] if output["role"] == "engine_delivery"
        )
        delivery.update(path="source.bin", sha256=sha256(self.root / "source.bin"))
        receipt["evidence"]["engine_import"][0].update(
            engine_delivery_path=delivery["path"],
            engine_delivery_sha256=delivery["sha256"],
        )
        completed, report = self.run_validator(receipt)
        self.assertEqual(2, completed.returncode, msg=completed.stderr)
        self.assert_problem(report, "SOURCE_OUTPUT_PATH_ALIAS")
        self.assert_problem(report, "SOURCE_OUTPUT_FILE_ALIAS")

        hardlink = self.root / "delivery-hardlink.png"
        os.link(self.root / "source.bin", hardlink)
        receipt = self.valid_receipt()
        delivery = next(
            output for output in receipt["outputs"] if output["role"] == "engine_delivery"
        )
        delivery.update(path=hardlink.name, sha256=sha256(hardlink))
        receipt["evidence"]["engine_import"][0].update(
            engine_delivery_path=delivery["path"],
            engine_delivery_sha256=delivery["sha256"],
        )
        completed, report = self.run_validator(receipt)
        self.assertEqual(2, completed.returncode, msg=completed.stderr)
        self.assert_problem(report, "SOURCE_OUTPUT_FILE_ALIAS")

    def test_failed_and_blocked_receipts_can_be_honest(self) -> None:
        failed = self.valid_receipt()
        failed["job"]["status"] = "failed"
        failed["gates"][0]["result"] = "fail"
        failed["gates"][0]["reason"] = "Audit observed a mismatch"
        completed, report = self.run_validator(failed)
        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertEqual("failed", report["reduced_status"])

        blocked = self.valid_receipt()
        blocked["job"]["status"] = "blocked"
        blocked["evidence"]["engine_import"] = []
        blocked["gates"][1] = {
            "id": "blocker.engine_target",
            "required": True,
            "result": "not_tested",
            "evidence": [],
            "reason": "No authorized target project is available",
        }
        completed, report = self.run_validator(blocked)
        self.assertEqual(0, completed.returncode, msg=completed.stderr)
        self.assertEqual("blocked", report["reduced_status"])

    def test_gate_rules_and_status_reduction_fail_closed(self) -> None:
        cases: list[tuple[str, Callable[[dict], None], str]] = [
            (
                "illegal fifth status",
                lambda value: value["job"].update(
                    status="prototype_ready_for_engine_import"
                ),
                "STATUS_INVALID",
            ),
            (
                "required not applicable",
                lambda value: value["gates"][0].update(
                    result="not_applicable", evidence=[], reason="Not relevant"
                ),
                "REQUIRED_GATE_NOT_APPLICABLE",
            ),
            (
                "not tested needs reason",
                lambda value: value["gates"][0].update(
                    result="not_tested", evidence=[], reason=""
                ),
                "GATE_REASON_REQUIRED",
            ),
            (
                "pass needs evidence",
                lambda value: value["gates"][0].update(evidence=[]),
                "GATE_EVIDENCE_REQUIRED",
            ),
            (
                "reference must exist",
                lambda value: value["gates"][0].update(
                    evidence=["artifact:missing"]
                ),
                "GATE_EVIDENCE_UNKNOWN",
            ),
            (
                "any fail reduces failed",
                lambda value: value["gates"][0].update(result="fail"),
                "STATUS_REDUCTION_MISMATCH",
            ),
            (
                "no engine evidence is at most prototype",
                lambda value: value["evidence"].update(engine_import=[]),
                "STATUS_REDUCTION_MISMATCH",
            ),
            (
                "required engine pass gate",
                lambda value: value["gates"][1].update(
                    id="runtime.import", evidence=["engine_import:unity-import"]
                ),
                "STATUS_REDUCTION_MISMATCH",
            ),
        ]
        for name, mutation, expected in cases:
            with self.subTest(name=name):
                receipt = self.valid_receipt()
                mutation(receipt)
                completed, report = self.run_validator(receipt)
                self.assertEqual(2, completed.returncode, msg=completed.stderr)
                self.assert_problem(report, expected)

    def test_strict_schema_paths_hashes_outputs_and_binding(self) -> None:
        def remove_manifest(value: dict) -> None:
            value["outputs"] = [
                output
                for output in value["outputs"]
                if output["role"] != "frame_manifest"
            ]

        cases: list[tuple[str, Callable[[dict], None], str]] = [
            (
                "unknown field",
                lambda value: value["job"].update(extra="rejected"),
                "SCHEMA_KEYS_UNKNOWN",
            ),
            (
                "absolute path",
                lambda value: value["sources"][0].update(path="/tmp/source.bin"),
                "PATH_NOT_PORTABLE",
            ),
            (
                "windows path",
                lambda value: value["outputs"][0].update(
                    path=r"C:\\project\\delivery.png"
                ),
                "PATH_NOT_PORTABLE",
            ),
            (
                "parent traversal",
                lambda value: value["outputs"][0].update(path="../delivery.png"),
                "PATH_NOT_PORTABLE",
            ),
            (
                "uppercase hash",
                lambda value: value["outputs"][0].update(
                    sha256=value["outputs"][0]["sha256"].upper()
                ),
                "SHA256_INVALID",
            ),
            (
                "hash mismatch",
                lambda value: value["outputs"][0].update(sha256="0" * 64),
                "FILE_HASH_MISMATCH",
            ),
            ("manifest required", remove_manifest, "OUTPUT_ROLE_CARDINALITY_INVALID"),
            (
                "engine binding",
                lambda value: value["evidence"]["engine_import"][0].update(
                    engine_delivery_sha256="0" * 64
                ),
                "ENGINE_DELIVERY_BINDING_MISMATCH",
            ),
        ]
        for name, mutation, expected in cases:
            with self.subTest(name=name):
                receipt = self.valid_receipt()
                mutation(receipt)
                completed, report = self.run_validator(receipt)
                self.assertEqual(2, completed.returncode, msg=completed.stderr)
                self.assert_problem(report, expected)

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        completed, report = self.run_validator(
            raw="schema_version: 1\nschema_version: 1\n"
        )
        self.assertEqual(2, completed.returncode, msg=completed.stderr)
        self.assert_problem(report, "RECEIPT_PARSE_INVALID")


if __name__ == "__main__":
    unittest.main()
