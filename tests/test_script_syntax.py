from __future__ import annotations

import ast
import os
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ScriptSyntaxTests(unittest.TestCase):
    def test_all_python_files_parse(self) -> None:
        for path in sorted(ROOT.rglob("*.py")):
            if ".git" in path.parts:
                continue
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_posix_scripts_parse(self) -> None:
        shell = shutil.which("bash") or shutil.which("sh")
        if not shell:
            self.skipTest("No POSIX shell is available")
        for path in sorted((ROOT / "scripts").glob("*.sh")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    [shell, "-n"],
                    cwd=ROOT,
                    input=path.read_bytes(),
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(
                    0,
                    result.returncode,
                    msg=result.stderr.decode("utf-8", errors="replace"),
                )

    def test_shell_files_are_lf_and_git_attributes_enforce_lf(self) -> None:
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertRegex(attributes, r"(?m)^\*\.sh\s+text\s+eol=lf\s*$")
        for path in sorted(ROOT.rglob("*.sh")):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(b"\r", path.read_bytes())
                result = subprocess.run(
                    ["git", "check-attr", "eol", "--", str(path.relative_to(ROOT))],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                self.assertEqual(0, result.returncode, msg=result.stderr)
                self.assertTrue(result.stdout.rstrip().endswith("eol: lf"), msg=result.stdout)

    @unittest.skipUnless(os.name == "nt", "PowerShell syntax is validated on Windows")
    def test_powershell_scripts_parse(self) -> None:
        pwsh = shutil.which("pwsh")
        if not pwsh:
            self.skipTest("pwsh is unavailable")
        command = (
            "$failed = $false; "
            "Get-ChildItem -Recurse -File -Filter '*.ps1' | ForEach-Object { "
            "$tokens = $null; $errors = $null; "
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            "$_.FullName, [ref]$tokens, [ref]$errors); "
            "if ($errors.Count -gt 0) { "
            "$failed = $true; $errors | ForEach-Object { Write-Error $_.Message } "
            "} }; if ($failed) { exit 1 }"
        )
        result = subprocess.run(
            [pwsh, "-NoLogo", "-NoProfile", "-Command", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)

if __name__ == "__main__":
    unittest.main()
