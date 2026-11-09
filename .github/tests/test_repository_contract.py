"""Preservation and wiring evidence against this repository's original commit."""

import importlib.util
from pathlib import Path
import re
import stat
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
BASE = "4fdadc52719f77bd41b396c226ee5ca488d8a61c"
PRODUCT = "Get file description"
PROJECT = f"{PRODUCT}.xcodeproj/project.pbxproj"
SOURCE_PATHS = (PROJECT, "Info.plist", "English.lproj/InfoPlist.strings")
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "contract_source_version", ROOT / ".github/scripts/source_version.py"
)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def original(path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{BASE}:{path}"])


class RepositoryContractTests(unittest.TestCase):
    def test_only_version_tokens_change_in_authoritative_sources(self):
        version = source.read(ROOT).encode()
        for path in SOURCE_PATHS:
            before = original(path)
            if path == PROJECT:
                expected = re.sub(
                    rb"((?:MARKETING_VERSION|CURRENT_PROJECT_VERSION) = )[^;]+;",
                    lambda match: match[1] + version + b";", before,
                )
            elif path.endswith(".strings"):
                self.assertIn(b"\r", before)
                self.assertNotIn(b"\n", before)
                expected = before.replace(b"2.2.0", version)
            else:
                expected = before
            self.assertEqual((ROOT / path).read_bytes(), expected, path)
            mode = int(subprocess.check_output(
                ["git", "-C", str(ROOT), "ls-tree", BASE, "--", path], text=True,
            ).split()[0], 8) & 0o777
            self.assertEqual(stat.S_IMODE((ROOT / path).stat().st_mode), mode)
        self.assertNotIn(b"<key>CFBundleVersion</key>", (ROOT / "Info.plist").read_bytes())

    def test_original_native_files_resources_and_dependencies_are_preserved(self):
        paths = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", BASE], text=True,
        ).splitlines()
        allowed = {*SOURCE_PATHS, "README.md", ".github/workflows/bump-version.yml",
                   ".github/workflows/release.yml"}
        for path in paths:
            if path not in allowed:
                self.assertEqual((ROOT / path).read_bytes(), original(path), path)

    def test_native_configuration_and_secrets_remain_original(self):
        before = original(".github/workflows/release.yml").decode()
        after = (ROOT / ".github/workflows/release.yml").read_text()

        def block(workflow, name):
            return workflow.split(f"      - name: {name}\n", 1)[1].split(
                "\n      - name:", 1
            )[0].rstrip()

        for name in ("import Developer ID certificate", "store notarytool credentials", "codesign"):
            self.assertEqual(block(before, name), block(after, name))
        secrets = r"\$\{\{ secrets\.([A-Z_]+) \}\}"
        self.assertEqual(re.findall(secrets, before), re.findall(secrets, after))
        for token in ("runs-on: macos-latest", "-configuration Default",
                      'ARCHS="arm64 x86_64"', "ONLY_ACTIVE_ARCH=NO",
                      "MACOS_DEPLOYMENT_TARGET: '11.0'",
                      'MACOSX_DEPLOYMENT_TARGET="${{ env.MACOS_DEPLOYMENT_TARGET }}"',
                      'ditto -c -k --keepParent "$BUNDLE_PATH" "$ZIP_PATH"',
                      'hdiutil create -format UDBZ -volname "${{ env.PRODUCT_NAME }}" -srcfolder "$BUNDLE_PATH" "$DMG_PATH"',
                      'xcrun stapler staple "$DMG_PATH"'):
            self.assertIn(token, before)
            self.assertIn(token, after)
        for forbidden in ("windows-latest", "msbuild", "shell: pwsh", "PlatformToolset=",
                          "CODE_SIGNING_ALLOWED=", 'CONFIGURATION_BUILD_DIR="'):
            self.assertNotIn(forbidden, after)
        project = (ROOT / PROJECT).read_text()
        self.assertIn('CONFIGURATION_BUILD_DIR = "$(BUILD_DIR)";', project)
        self.assertIn('SYMROOT = "$(SRCROOT)/test/Plugins";', project)
        self.assertIn('BUILD_DIR="$PWD/$PLUGINS_DIR"', after)
        # Windows is committed input, not a newly invented workflow build.
        ns = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
        tree = ET.parse(ROOT / f"{PRODUCT}.vcxproj")
        condition = "'$(Configuration)|$(Platform)'=='Release|x64'"
        outdir = [node.text for node in tree.findall(".//m:OutDir", ns)
                  if node.get("Condition") == condition]
        self.assertEqual(outdir, [r"$(ProjectDir)test\plugins\$(ProjectName).bundle\contents\windows64" + "\\"])
        self.assertEqual({n.text for n in tree.findall(".//m:PlatformToolset", ns)}, {"v140"})

    def test_manual_immutable_serial_create_only_wiring(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text()
        self.assertRegex(workflow, r"(?m)^name: Build$")
        self.assertEqual(workflow.split("\non:\n", 1)[1].split("\npermissions:", 1)[0].strip(),
                         "workflow_dispatch:")
        self.assertIn("group: release-publication\n  cancel-in-progress: false", workflow)
        jobs = re.findall(r"^  ([a-z][a-z-]+):\n", workflow.split("\njobs:\n", 1)[1], re.M)
        self.assertEqual(jobs, ["version", "build-macos"])
        checkouts = re.findall(r"uses: actions/checkout@[^\n]+\n        with:\n          ref: ([^\n]+)", workflow)
        self.assertEqual(checkouts, ["${{ github.sha }}", "${{ github.sha }}"])
        self.assertIn("needs: [version]", workflow)
        self.assertIn("tag: ${{ steps.set.outputs.tag }}", workflow)
        self.assertIn("version: ${{ steps.set.outputs.version }}", workflow)
        self.assertEqual(workflow.count('release.py check --sha "$SELECTED_SHA"'), 2)
        self.assertEqual(workflow.count("GH_TOKEN: ${{ github.token }}"), 3)
        self.assertEqual(workflow.count("SELECTED_SHA: ${{ github.sha }}"), 3)
        ordered = ["VERSION=$(python3 .github/scripts/source_version.py)",
                   'echo "version=$VERSION" >> "$GITHUB_OUTPUT"',
                   'echo "tag=v$VERSION" >> "$GITHUB_OUTPUT"',
                   'release.py check --sha "$SELECTED_SHA"',
                   "- name: build macOS plugin (universal)", "- name: verify universal binary",
                   "--verify-bundle", "- name: codesign", "- name: package, notarize & staple",
                   "- name: final source and publication availability check",
                   'release.py check --sha "$SELECTED_SHA"', "- name: create GitHub Release",
                   'release.py publish --sha "$SELECTED_SHA" "$ZIP_PATH" "$DMG_PATH"']
        cursor = 0
        for token in ordered:
            cursor = workflow.index(token, cursor) + len(token)
        for forbidden in ("softprops/", "continue-on-error:", "always()", "inputs.", "github.ref"):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    unittest.main()
