from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "skills/character-rig-animation-alignment/scripts/"
    "audit_unity_humanoid_meta.py"
)
SPEC = importlib.util.spec_from_file_location("autota_humanoid_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


class HumanoidAuditOutputBoundaryTests(unittest.TestCase):
    def test_output_requires_root_and_refuses_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            output = root / "audit.json"
            parser = AUDIT.build_argument_parser()
            base = ["--reference", "reference.meta", "--candidate", "candidate.meta"]
            missing_root = parser.parse_args([*base, "--output", str(output)])
            with self.assertRaisesRegex(ValueError, "provided together"):
                AUDIT._authorized_output(missing_root)

            output.write_text("preserve", encoding="utf-8")
            existing = parser.parse_args(
                [*base, "--output", str(output), "--output-root", str(root)]
            )
            with self.assertRaisesRegex(FileExistsError, "overwrite"):
                AUDIT._authorized_output(existing)
            self.assertEqual("preserve", output.read_text(encoding="utf-8"))

    def test_output_escape_is_rejected_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            root = parent / "reports"
            root.mkdir()
            parser = AUDIT.build_argument_parser()
            arguments = parser.parse_args(
                [
                    "--reference",
                    "reference.meta",
                    "--candidate",
                    "candidate.meta",
                    "--output",
                    str(parent / "outside.json"),
                    "--output-root",
                    str(root),
                ]
            )
            with self.assertRaisesRegex(ValueError, "escapes"):
                AUDIT._authorized_output(arguments)
            self.assertFalse((parent / "outside.json").exists())


if __name__ == "__main__":
    unittest.main()
