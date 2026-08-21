from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "generate-hosted-game-art"
CLIENT = SKILL / "scripts" / "hosted_art_client.py"

SPEC = importlib.util.spec_from_file_location("gamemaker_hosted_art_client", CLIENT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HostedArtSkillContractTests(unittest.TestCase):
    def test_skill_contract_markers(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for marker in (
            "meshy",
            "tencent-cloud",
            "Probe First (free, mandatory before first generation)",
            "--acknowledge-billable",
            "GENERATE_HOSTED_GAME_ART_NOT_LINKED",
            "CLAUDE_CONFIG_DIR",
            "CREDENTIALS_INVALID",
            "PROVIDER_UNSUPPORTED",
            "validation_status: prototype",
            "$auto-ta",
            "$character-rig-animation-alignment",
            "$create-2d-game-art",
            "$search-game-art",
            "Match user-facing explanations",
        ):
            self.assertIn(marker, text)
        # Blender stays downstream, hosted generation is the preferred base source.
        self.assertIn("downstream adaptation", text)

    def test_client_refuses_billable_without_acknowledgement(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(CLIENT),
                "submit",
                "--provider",
                "meshy",
                "--endpoint",
                "text-to-3d",
                "--credentials",
                "does-not-matter.txt",
                "--payload",
                "does-not-matter.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("BILLABLE_NOT_ACKNOWLEDGED", result.stderr)

    def test_client_requires_endpoint_or_action(self) -> None:
        for provider, missing in (("meshy", "MISSING_ENDPOINT"), ("tencent-cloud", "MISSING_ACTION")):
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLIENT),
                    "status",
                    "--provider",
                    provider,
                    "--credentials",
                    "does-not-matter.txt",
                    "--task-id",
                    "x",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            with self.subTest(provider=provider):
                self.assertEqual(2, result.returncode)
                self.assertIn(missing, result.stderr)

    def test_probe_whitelists_only_free_tencent_actions(self) -> None:
        source = CLIENT.read_text(encoding="utf-8")
        probe_section = source.split("def probe_tencent", 1)[1].split("def submit", 1)[0]
        self.assertNotIn("Submit", probe_section)
        for free_action in ("DescribeAccountBalance", "GetTokenCount", "QueryHunyuanTo3DJob"):
            self.assertIn(free_action, probe_section)

    def test_tc3_signature_is_deterministic_and_well_formed(self) -> None:
        kwargs = dict(
            sid="AKIDexample",
            skey="examplesecret",
            service="ai3d",
            action="QueryHunyuanTo3DJob",
            version="2025-05-13",
            body='{"JobId":"x"}',
            timestamp=1_755_000_000,
            region="ap-guangzhou",
        )
        first = MODULE.tc3_headers(**kwargs)
        second = MODULE.tc3_headers(**kwargs)
        self.assertEqual(first, second)
        auth = first["Authorization"]
        self.assertTrue(auth.startswith("TC3-HMAC-SHA256 Credential=AKIDexample/"))
        self.assertIn("/ai3d/tc3_request", auth)
        signature = auth.rsplit("Signature=", 1)[1]
        self.assertEqual(64, len(signature))
        int(signature, 16)  # hex
        changed = MODULE.tc3_headers(**{**kwargs, "body": '{"JobId":"y"}'})
        self.assertNotEqual(auth, changed["Authorization"])
        # secrets never leak into headers
        for value in first.values():
            self.assertNotIn("examplesecret", value)

    def test_credential_parsers_fail_closed(self) -> None:
        import tempfile

        (ROOT / "Temp").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="hosted-art-", dir=ROOT / "Temp") as raw:
            bad = Path(raw) / "bad.txt"
            bad.write_text("not-a-key\n", encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                MODULE.load_meshy_key(bad)
            self.assertEqual(2, ctx.exception.code)
            with self.assertRaises(SystemExit) as ctx2:
                MODULE.load_tencent_keys(bad)
            self.assertEqual(2, ctx2.exception.code)


if __name__ == "__main__":
    unittest.main()
