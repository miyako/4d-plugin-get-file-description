"""Compile actual native sources plus the full unchanged SDK, not API mocks.

OWNERSHIP_SOURCE_ROOT selects an immutable git-archive baseline.
OWNERSHIP_ARTIFACTS keeps all synthetic fixtures/output outside the checkout.
"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("OWNERSHIP_SOURCE_ROOT", ROOT)).resolve()
CASES = (
    *(f"setter-{i}" for i in range(4)), "picture-setter",
    *(f"getter-{i}" for i in range(5)), "handoffs", "scalar-getters",
    "owned-mismatches", "failed-getters",
    *(f"stringify-{i}" for i in range(4)), "arrays", "array-rejected-output", "dispatcher",
)


@unittest.skipUnless(sys.platform == "darwin", "macOS Objective-C++ boundary harness")
class OwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(
            prefix="native-ownership-", dir=os.environ.get("OWNERSHIP_ARTIFACTS")
        )
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "ownership"
        command = [
            "xcrun", "clang++", "-x", "objective-c++", "-std=c++11",
            "-g", "-O1", "-fno-omit-frame-pointer", "-fsanitize=address,undefined",
            "-fno-sanitize-recover=all", "-Wno-deprecated-declarations",
            "-Wno-multichar", "-Wno-return-type-c-linkage", "-Wno-null-conversion",
            "-include", str(ROOT / ".github/tests/ownership_platform.h"),
            "-I" + str(SOURCE), "-I" + str(SOURCE / "4D Plugin API"),
            "-I" + str(SOURCE / "4D Plugin API/Classes"),
            "-I" + str(SOURCE / "support"),
            str(ROOT / ".github/tests/ownership.mm"),
            *(str(SOURCE / path) for path in (
                "4DPlugin-Get-file-description.cpp", "support/4DPlugin-JSON.cpp",
                "4D Plugin API/4DPluginAPI.c", "4D Plugin API/Classes/C_TEXT.cpp",
                "4D Plugin API/Classes/ARRAY_TEXT.cpp", "4D Plugin API/Classes/C_BLOB.cpp",
                "4D Plugin API/Classes/C_LONGINT.cpp",
            )),
            "-framework", "Cocoa", "-framework", "CoreServices",
            "-framework", "CoreGraphics", "-o", str(cls.binary),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def test_native_ownership(self):
        for case in CASES:
            for empty in ("allocated", "null"):
                with self.subTest(case=case, empty=empty):
                    result = subprocess.run(
                        [str(self.binary), case, empty],
                        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0",
                             "UBSAN_OPTIONS": "halt_on_error=1"},
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn(f"PASS {case} {empty}", result.stdout)


if __name__ == "__main__":
    unittest.main()
