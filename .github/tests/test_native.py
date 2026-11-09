"""Execute actual workflow shell with a closed PATH and native-only stubs."""

import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/release.yml").read_text()
PRODUCT = "Get file description"
SOURCE_PATHS = (f"{PRODUCT}.xcodeproj/project.pbxproj", "Info.plist",
                "English.lproj/InfoPlist.strings")
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location(
    "native_source_version", ROOT / ".github/scripts/source_version.py"
)
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def step(name):
    matches = re.findall(
        rf"^      - name: {re.escape(name)}\n"
        r"(?:(?!      - ).*\n)*?        run: \|\n"
        r"((?:          .*(?:\n|$)|[ \t]*\n)+)",
        WORKFLOW, re.MULTILINE,
    )
    if len(matches) != 1:
        raise AssertionError(f"Expected one actual shell block for {name!r}")
    return textwrap.dedent(matches[0])


STUB = r'''
import json
import os
from pathlib import Path
import plistlib
import sys

tool = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(json.dumps([tool, *args]) + "\n")
product = "Get file description"
bundle = Path(os.environ["BUNDLE_PATH"])
contents = bundle / "Contents"
mode = os.environ.get("BUILD_MODE", "complete")
if tool == "xcodebuild":
    for path in (
        contents / ("MacOS/" + product), contents / "Info.plist",
        contents / "Resources/English.lproj/InfoPlist.strings",
        contents / "_CodeSignature", bundle.parent / "Default",
        bundle.parent / (product + ".build"), Path("build") / (product + ".build"),
    ):
        assert not path.exists(), "stale output survived: " + str(path)
    if mode == "failed":
        sys.exit(70)
    if mode != "missing-binary":
        (contents / "MacOS").mkdir(parents=True, exist_ok=True)
        (contents / "MacOS" / product).write_bytes(b"fresh universal binary")
    if mode != "missing-plist":
        data = plistlib.loads(Path("Info.plist").read_bytes())
        for key in ("CFBundleShortVersionString", "CFBundleVersion"):
            if key in data:
                data[key] = data[key].replace("$(MARKETING_VERSION)", os.environ["VERSION"])
                data[key] = data[key].replace("$(CURRENT_PROJECT_VERSION)", os.environ["VERSION"])
        if mode == "stale-plist":
            data["CFBundleShortVersionString"] = os.environ["STALE"]
        if mode == "stale-build":
            data["CFBundleVersion"] = os.environ["STALE"]
        (contents / "Info.plist").write_bytes(plistlib.dumps(data))
    if mode != "missing-localized":
        data = Path("English.lproj/InfoPlist.strings").read_bytes()
        if mode == "stale-localized":
            data = data.replace(os.environ["VERSION"].encode(), os.environ["STALE"].encode())
        path = contents / "Resources/English.lproj/InfoPlist.strings"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
elif tool == "lipo":
    assert args == ["-info", str(bundle / "Contents/MacOS" / product)]
    assert Path(args[-1]).is_file()
    if os.environ.get("LIPO_FAIL"):
        sys.exit(75)
    print("Architectures in the fat file: " + os.environ.get("ARCHS", "arm64 x86_64"))
elif tool == "python3":
    assert args == [".github/scripts/source_version.py", "--verify-bundle", str(bundle)] or (
        len(args) == 2 and args[0] == "-c" and args[1].startswith("import json,sys;")
    )
    os.execv(os.environ["REAL_PYTHON"], [os.environ["REAL_PYTHON"], *args])
elif tool == "base64":
    assert args == ["--decode", "-o", os.environ["RUNNER_TEMP"] + "/certificate.p12"]
    assert sys.stdin.read() == "fixture-certificate"
    if os.environ.get("IMPORT_FAIL") == "base64":
        sys.exit(78)
    Path(args[-1]).write_bytes(b"fixture certificate, not a real key")
elif tool == "security":
    keychain = os.environ["KEYCHAIN_PATH"]
    expected = {
        "create-keychain": ["-p", "fixture-keychain", keychain],
        "set-keychain-settings": ["-lut", "21600", keychain],
        "unlock-keychain": ["-p", "fixture-keychain", keychain],
        "import": [os.environ["RUNNER_TEMP"] + "/certificate.p12", "-P", "fixture-password",
                   "-A", "-t", "cert", "-f", "pkcs12", "-k", keychain],
        "list-keychain": ["-d", "user", "-s", keychain, "login.keychain"],
        "set-key-partition-list": ["-S", "apple-tool:,apple:,codesign:", "-s", "-k",
                                   "fixture-keychain", keychain],
        "find-identity": ["-v", "-p", "codesigning", keychain],
    }
    assert args[1:] == expected[args[0]]
    if os.environ.get("IMPORT_FAIL") == args[0]:
        sys.exit(78)
    if args[0] == "find-identity":
        if os.environ.get("SIGN_MODE") == "identity-error":
            sys.exit(78)
        if os.environ.get("SIGN_MODE") != "missing-identity":
            print('1) FAKE "Developer ID Application: Fixture (TEST)"')
elif tool == "codesign":
    verify = args[0] == "--verify"
    expected = ["--verify", "--deep", "--strict", "--verbose=2", str(bundle)] if verify else [
        "--verbose", "--deep", "--timestamp", "--force", "--options=runtime",
        "--sign", "Developer ID Application: Fixture (TEST)", str(bundle)
    ]
    assert args == expected
    if os.environ.get("SIGN_MODE") == ("verify" if verify else "sign"):
        sys.exit(76)
elif tool in ("ditto", "hdiutil"):
    assert bundle.is_dir()
    expected = ["-c", "-k", "--keepParent", str(bundle)] if tool == "ditto" else [
        "create", "-format", "UDBZ", "-volname", product, "-srcfolder", str(bundle)
    ]
    assert args[:-1] == expected
    assert args[-1] == product + "-" + os.environ["VERSION"] + (
        ".zip" if tool == "ditto" else ".dmg"
    )
    if os.environ.get("PACKAGE_FAIL") == tool:
        sys.exit(77)
    Path(args[-1]).write_bytes(b"fixture archive")
elif tool == "xcrun":
    scenario = os.environ.get("NOTARY_MODE", "accepted")
    if args[:2] == ["notarytool", "store-credentials"]:
        assert args[2:] == ["notarytool-profile", "--apple-id", "fixture@example.invalid",
                            "--team-id", "FIXTURE", "--password", "fixture-app-password",
                            "--keychain", os.environ["KEYCHAIN_PATH"]]
        if os.environ.get("CREDENTIAL_FAIL"):
            sys.exit(71)
    elif args[:2] == ["notarytool", "submit"]:
        assert args[3:] == ["--keychain-profile", "notarytool-profile", "--keychain",
                            os.environ["KEYCHAIN_PATH"], "--wait", "--output-format", "json"]
        assert Path(args[2]).is_file()
        second = args[2].endswith(".dmg")
        active = not scenario.startswith("second-") or second
        scenario = scenario.removeprefix("second-") if active else "accepted"
        if scenario in ("transport", "accepted-nonzero"):
            if scenario == "accepted-nonzero":
                print('{"status": "Accepted"}')
            sys.exit(71)
        if scenario == "malformed":
            print("not JSON")
        elif scenario == "missing-status":
            print('{"id": "fixture"}')
        else:
            status = {"invalid": "Invalid", "pending": "In Progress",
                      "wrong-case": "accepted", "null": None}.get(scenario, "Accepted")
            print(json.dumps({"id": "fixture", "status": status}))
    elif args[:2] == ["stapler", "staple"]:
        assert args == ["stapler", "staple", product + "-" + os.environ["VERSION"] + ".dmg"]
        if scenario == "staple":
            sys.exit(73)
    else:
        raise AssertionError(args)
else:
    raise AssertionError("Unexpected native command: " + tool)
'''


class NativeShellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".native-tests-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in (*SOURCE_PATHS, ".github/scripts/source_version.py"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.version = source.read(self.root)
        major, minor, patch = map(int, self.version.split("."))
        self.stale = f"{major}.{minor}.{patch + 1}"
        self.relative_bundle = f"test/Plugins/{PRODUCT}.bundle"
        self.bundle = self.root / self.relative_bundle
        self.contents = self.bundle / "Contents"
        self.log = self.root / "calls.jsonl"
        self.env_file = self.root / "github-env"
        self.env_file.touch()
        self.bin = self.root / "stub-bin"
        self.bin.mkdir()
        for name in ("xcodebuild", "lipo", "python3", "base64", "security", "codesign",
                     "ditto", "hdiutil", "xcrun"):
            path = self.bin / name
            path.write_text(f"#!{sys.executable}\n" + textwrap.dedent(STUB))
            path.chmod(0o755)
        # Only inert shell utilities may resolve outside the native stub directory.
        for name in ("rm", "grep", "head", "sed"):
            executable = shutil.which(name)
            self.assertIsNotNone(executable)
            (self.bin / name).symlink_to(executable)
        runner_temp = self.root / "runner-work"
        runner_temp.mkdir()
        self.env = {
            "PATH": str(self.bin), "CALL_LOG": str(self.log),
            "REAL_PYTHON": sys.executable, "PYTHONDONTWRITEBYTECODE": "1",
            "VERSION": self.version, "STALE": self.stale,
            "BUNDLE_PATH": self.relative_bundle, "GITHUB_ENV": str(self.env_file),
            "KEYCHAIN_PATH": str(runner_temp / "build.keychain-db"),
            "RUNNER_TEMP": str(runner_temp), "CERT_BASE64": "fixture-certificate",
            "CERT_PASSWORD": "fixture-password", "KEYCHAIN_PASSWORD": "fixture-keychain",
            "APPLE_ID": "fixture@example.invalid", "TEAM_ID": "FIXTURE",
            "APP_PASSWORD": "fixture-app-password",
        }
        self.preserved = {}
        original_contents = ROOT / self.relative_bundle / "Contents"
        generated = {"Info.plist", f"MacOS/{PRODUCT}",
                     "Resources/English.lproj/InfoPlist.strings"}
        for path in original_contents.rglob("*"):
            relative = path.relative_to(original_contents).as_posix()
            if path.is_file() and relative not in generated and not relative.startswith("_CodeSignature/"):
                self.write(relative, path.read_bytes())
                self.preserved[relative] = path.read_bytes()
        for relative in ("MacOS/Dependency.dylib", "Resources/Documentation/keep.txt",
                         "Frameworks/Dependency.framework/Versions/A/Dependency",
                         "Resources/Other.bundle/Contents/resource"):
            self.write(relative, b"preserved sibling")
            self.preserved[relative] = b"preserved sibling"
        (self.contents / "Frameworks/Dependency.framework/Versions/Current").symlink_to("A")
        for relative in (*generated, "_CodeSignature/CodeResources"):
            self.write(relative, b"stale build output")
        for relative in ("test/Plugins/Default/stale",
                         f"test/Plugins/{PRODUCT}.build/stale", f"build/{PRODUCT}.build/stale"):
            path = self.root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"stale intermediate")
        self.sibling = self.root / "test/Plugins/Other.bundle/Contents/keep"
        self.sibling.parent.mkdir(parents=True)
        self.sibling.write_bytes(b"committed unrelated plugin")

    def write(self, relative, data):
        path = self.contents / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def run_step(self, name, prefix="", **env):
        script = step(name)
        values = {"env.PRODUCT_NAME": PRODUCT, "env.XCODE_PROJECT": PRODUCT + ".xcodeproj",
                  "env.MACOS_DEPLOYMENT_TARGET": "11.0",
                  "needs.version.outputs.version": self.version}
        for key, value in values.items():
            script = script.replace("${{ " + key + " }}", value)
        self.assertNotIn("${{", script)
        return subprocess.run(
            ["/bin/bash", "-c", prefix + "\n" + script], cwd=self.root,
            env={**self.env, **env}, text=True, capture_output=True, timeout=30,
        )

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def calls(self, tool):
        return [call[1:] for line in self.log.read_text().splitlines()
                if (call := json.loads(line))[0] == tool] if self.log.exists() else []

    def build(self, **env):
        self.assert_ok(self.run_step("build macOS plugin (universal)", **env))

    def test_fresh_build_preserves_committed_resources_and_siblings(self):
        self.build()
        for relative, data in self.preserved.items():
            self.assertEqual((self.contents / relative).read_bytes(), data, relative)
        link = self.contents / "Frameworks/Dependency.framework/Versions/Current"
        self.assertEqual(link.readlink(), Path("A"))
        self.assertEqual(self.sibling.read_bytes(), b"committed unrelated plugin")
        self.assertEqual((self.contents / f"MacOS/{PRODUCT}").read_bytes(), b"fresh universal binary")
        self.assert_ok(self.run_step("verify universal binary"))
        self.assertEqual(self.calls("xcodebuild"), [[
            "-project", PRODUCT + ".xcodeproj", "-target", PRODUCT,
            "-configuration", "Default", "ARCHS=arm64 x86_64", "ONLY_ACTIVE_ARCH=NO",
            "MACOSX_DEPLOYMENT_TARGET=11.0", f"BUILD_DIR={self.root}/test/Plugins", "build",
        ]])

    def test_certificate_import_and_each_failure_are_fatal(self):
        self.assert_ok(self.run_step("import Developer ID certificate"))
        sequence = ["create-keychain", "set-keychain-settings", "unlock-keychain",
                    "import", "list-keychain", "set-key-partition-list"]
        self.assertEqual([call[0] for call in self.calls("security")], sequence)
        self.assertEqual(self.env_file.read_text(),
                         f'KEYCHAIN_PATH={self.env["KEYCHAIN_PATH"]}\n')
        for mode in ("base64", *sequence):
            with self.subTest(mode=mode):
                self.log.unlink()
                self.env_file.write_text("")
                self.assertNotEqual(self.run_step("import Developer ID certificate",
                                                 IMPORT_FAIL=mode).returncode, 0)
                self.assertEqual(self.env_file.read_text(), "")
                self.assertEqual(self.calls("xcodebuild"), [])
                if mode != "base64":
                    self.assertEqual([call[0] for call in self.calls("security")],
                                     sequence[:sequence.index(mode) + 1])

    def test_notary_credential_failure_is_fatal(self):
        self.assert_ok(self.run_step("store notarytool credentials"))
        self.assertNotEqual(self.run_step("store notarytool credentials",
                                         CREDENTIAL_FAIL="1").returncode, 0)
        self.assertEqual(self.calls("xcodebuild"), [])

    def test_cleanup_error_blocks_build(self):
        result = self.run_step("build macOS plugin (universal)",
                               prefix="rm() { echo 'fixture cleanup failure' >&2; return 79; }")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fixture cleanup failure", result.stderr)
        self.assertEqual(self.calls("xcodebuild"), [])

    def test_each_cleanup_error_is_fatal(self):
        for failing in range(1, 8):
            with self.subTest(cleanup=failing):
                result = self.run_step(
                    "build macOS plugin (universal)",
                    prefix=f'n=0; rm() {{ n=$((n + 1)); [ "$n" -ne {failing} ]; }}',
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls("xcodebuild"), [])

    def test_build_failure_is_fatal(self):
        self.assertNotEqual(self.run_step("build macOS plugin (universal)",
                                         BUILD_MODE="failed").returncode, 0)

    def test_missing_and_stale_outputs_cannot_pass_verification(self):
        for mode in ("missing-binary", "missing-plist", "missing-localized",
                     "stale-plist", "stale-build", "stale-localized"):
            with self.subTest(mode=mode):
                self.env_file.write_text("")
                self.build(BUILD_MODE=mode)
                self.assertNotEqual(self.run_step("verify universal binary").returncode, 0)
                self.assertEqual(self.env_file.read_text(), "")

    def test_lipo_failure_and_each_exact_architecture_are_required(self):
        self.build()
        for architectures in ("arm64", "x86_64", "arm64e x86_64", "arm64 x86_64h",
                              "notarm64 x86_64", "arm64 x86_64_extra"):
            with self.subTest(architectures=architectures):
                self.assertNotEqual(self.run_step("verify universal binary",
                                                 ARCHS=architectures).returncode, 0)
        self.assertNotEqual(self.run_step("verify universal binary", LIPO_FAIL="1").returncode, 0)
        self.assertEqual(self.calls("python3"), [])
        self.assert_ok(self.run_step("verify universal binary", ARCHS="arm64 x86_64 i386 extra"))

    def test_xml_binary_and_utf16_metadata_match_selected_source(self):
        self.build()
        original = (self.root / "English.lproj/InfoPlist.strings").read_text()
        values = dict(re.findall(r'(?m)^(\w+)\s*=\s*"([^"]*)";', original))
        plist = plistlib.loads((self.contents / "Info.plist").read_bytes())
        self.assertNotIn("CFBundleVersion", plist)
        for fmt in (plistlib.FMT_XML, plistlib.FMT_BINARY):
            self.write("Info.plist", plistlib.dumps(plist, fmt=fmt))
            self.write("Resources/English.lproj/InfoPlist.strings", plistlib.dumps(values, fmt=fmt))
            self.assert_ok(self.run_step("verify universal binary"))
            for key in ("CFBundleShortVersionString", "CFBundleGetInfoString"):
                stale = {**values, key: values[key].replace(self.version, self.stale)}
                self.write("Resources/English.lproj/InfoPlist.strings",
                           plistlib.dumps(stale, fmt=fmt))
                self.assertNotEqual(self.run_step("verify universal binary").returncode, 0)
        for encoding, prefix in (("utf-16", b""), ("utf-16-be", b"\xfe\xff")):
            for stale in (False, True):
                text = original.replace(self.version, self.stale) if stale else original
                self.write("Resources/English.lproj/InfoPlist.strings", prefix + text.encode(encoding))
                result = self.run_step("verify universal binary")
                if stale:
                    self.assertNotEqual(result.returncode, 0)
                else:
                    self.assert_ok(result)

    def test_signing_requires_identity_successful_sign_and_strict_verify(self):
        self.assert_ok(self.run_step("codesign"))
        self.assertEqual(len(self.calls("codesign")), 2)
        for mode, count in (("missing-identity", 0), ("identity-error", 0), ("sign", 1), ("verify", 2)):
            self.log.unlink()
            self.assertNotEqual(self.run_step("codesign", SIGN_MODE=mode).returncode, 0)
            self.assertEqual(len(self.calls("codesign")), count)
            self.assertEqual(self.calls("ditto"), [])

    def test_both_accepted_submissions_precede_staple_and_output_export(self):
        self.assert_ok(self.run_step("package, notarize & staple"))
        calls = self.calls("xcrun")
        self.assertEqual([call[:2] for call in calls],
                         [["notarytool", "submit"], ["notarytool", "submit"], ["stapler", "staple"]])
        self.assertEqual([call[2] for call in calls],
                         [f"{PRODUCT}-{self.version}.zip", f"{PRODUCT}-{self.version}.dmg",
                          f"{PRODUCT}-{self.version}.dmg"])
        self.assertEqual(self.env_file.read_text().splitlines(),
                         [f"ZIP_PATH={PRODUCT}-{self.version}.zip",
                          f"DMG_PATH={PRODUCT}-{self.version}.dmg"])

    def test_both_notary_commands_require_zero_exit_and_accepted_json(self):
        for stage in ("", "second-"):
            for mode in ("invalid", "transport", "accepted-nonzero", "malformed",
                         "missing-status", "pending", "wrong-case", "null"):
                with self.subTest(stage=stage, mode=mode):
                    self.log.unlink(missing_ok=True)
                    result = self.run_step("package, notarize & staple", NOTARY_MODE=stage + mode)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(len(self.calls("xcrun")), 2 if stage else 1)
                    self.assertFalse(any(c[:2] == ["stapler", "staple"] for c in self.calls("xcrun")))
                    self.assertEqual(self.env_file.read_text(), "")

    def test_staple_failure_prevents_output_export(self):
        self.assertNotEqual(self.run_step("package, notarize & staple",
                                         NOTARY_MODE="staple").returncode, 0)
        self.assertEqual(len(self.calls("xcrun")), 3)
        self.assertEqual(self.env_file.read_text(), "")

    def test_packaging_failure_blocks_notarization(self):
        for tool in ("ditto", "hdiutil"):
            self.log.unlink(missing_ok=True)
            self.assertNotEqual(self.run_step("package, notarize & staple",
                                             PACKAGE_FAIL=tool).returncode, 0)
            self.assertEqual(self.calls("xcrun"), [])
            self.assertEqual(self.env_file.read_text(), "")


if __name__ == "__main__":
    unittest.main()
