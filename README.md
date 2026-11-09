![version](https://img.shields.io/badge/version-16%2B-8331AE)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm%20|%20win-64&color=blue)
[![license](https://img.shields.io/github/license/miyako/4d-plugin-get-file-description)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/4d-plugin-get-file-description/total)

# 4d-plugin-get-file-description

Returns the operating system's human-readable file type description for a given file path or file name — the same string macOS Finder ("Get Info") or Windows Explorer ("Type of file") would show for that file. The plugin doesn't inspect the file's contents; it derives the description purely from the file's extension, so the path doesn't need to point to a file that actually exists on disk.

## Manual source versioning and Build

**Bump version** and **Build** are independent manual Actions. Use GitHub's built-in
ref selector; Build has no custom inputs. Bump accepts `patch`, `minor`, or `major`
and only accepts a branch whose current remote SHA still matches the selected
dispatch SHA. It creates one nonempty, source-only, direct-child commit with the
Copilot App co-author trailer and pushes that exact commit without force or
follow-tags. The executable pre-push guard checks the server-advertised old SHA
and exact ref, new SHA, HEAD and single parent, including rejecting zero-update
same-result races. Missing or nonexecutable guards fail both before editing and
immediately before pushing. If the branch moves, select its new ref and dispatch
again. Bump never creates tags/releases, builds, or dispatches another workflow.

The original Bump header, introduced at `8f3acb7` (including rename-follow
history), explicitly coordinates `MARKETING_VERSION`, `CURRENT_PROJECT_VERSION`
and the plist versions. That contract governs, not its buggy marketing-only
implementation. The six target/project assignments for Development, Deployment
and Default now validate and co-bump. The authority on intake remains **2.2.5**:
only the six stale source `CURRENT_PROJECT_VERSION = 2.2.0` assignments and the
two English source display occurrences of `2.2.0` were repaired to `2.2.5`.
There is no intake version increment.
The existing production `v2.2.5` tag/release is left untouched; Build on this
intake version intentionally fails its absence check. Bump source first when
preparing a future release.

`Info.plist`'s required short version remains `$(MARKETING_VERSION)`; optional
`CFBundleVersion` remains absent. Supported marketing/current references are
validated and preserved; present literal plist versions co-bump. The source
`English.lproj/InfoPlist.strings` also co-bumps. Validation rejects drift,
noncanonical versions, missing metadata and duplicate assignments before any
write, including same-line quoted/unquoted project duplicates. Rewrites preserve
encoding/BOM, each individual newline, modes and unrelated bytes. Prebuilt
bundles, Windows binaries, archives, dependencies, manifest/schema and 4D database
counters are not version authority and are never bumped.

**Build** checks out the selected immutable `github.sha`, derives `vX.Y.Z` from
source, and checks authenticated, paginated releases (including drafts) and the
exact remote tag before native work and again after all build/sign/notary/staple
gates. Build dispatches across refs share a constant non-cancelling concurrency
group. The original workflow has only macOS jobs despite its Windows-first
comment: this migration does not invent a Windows build. The existing committed
Windows64 payload stays in the cross-platform bundle. The unchanged vcxproj
still uses v140 and outputs x64 `.4DX` to
`test/plugins/Get file description.bundle/contents/windows64/`; it is not invoked
by Build.

The macOS target/configuration remain `Get file description` / `Default`, with
`arm64 x86_64`, `ONLY_ACTIVE_ARCH=NO`, and the original deployment override `11.0`
(the project itself remains `11.5`). Build explicitly resolves `BUILD_DIR` to
`test/Plugins`, matching the project's `CONFIGURATION_BUILD_DIR = $(BUILD_DIR)`
and its actual committed bundle destination. Cleanup removes only generated
executable/plist/localized version/signature/intermediates, never whole bundles,
resources, Windows payloads or sibling resources. Fresh output must contain the
exact required architecture tokens, selected-source plist and localized versions;
strict signature verification, successful submissions with JSON `Accepted` for
both ZIP and DMG, and successful stapling are mandatory. Existing framework,
resource phases, toolsets and signing/notary secret names are retained.

### Publication failures and manual recovery

Publication is create-only: POST a new `refs/tags/vX.Y.Z` at the selected SHA,
verify the advertised remote SHA, POST a **new** public nonprerelease release
with explicit tag/name/target, the original empty body and no generated notes,
then upload exactly the ZIP and stapled DMG separately to that returned new ID.
No existing release is reused or updated. Errors, including authentication,
404/network failures, malformed responses, later-page failures and concurrent
creation, stop without retry, clobber, rollback or deletion.

If publication partially succeeds, the created tag, release and any uploaded
assets are deliberately retained. The log reports verified tag/SHA and new
release ID when available; inspect GitHub and the failing API operation if a
response was lost. Record the selected SHA, tag, release ID and successful assets
before any manual intervention. Do not rerun Build expecting it to reuse or
repair that state: its absence checks will reject it. A maintainer must assess
the evidence and decide any manual recovery; normally make a new source bump
and manually Build that new version. These workflows never PATCH, DELETE,
overwrite or automatically clean up publication evidence.

Offline regression checks (no native tools, credentials or network publication):

```sh
actionlint
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .github/tests -v
```

The workflow/helper/hook/test patterns were reviewed at these exact reference
commits and adapted to this repository's authority, source serialization,
single-macOS-job topology, resource phases and output paths:

| Reference repository | Commit |
|---|---|
| `miyako/4d-plugin-native-encoding-detection` | `c42ca565857f674bde5ea6ed3435c87375eda4a7` |
| `miyako/4d-plugin-file-information` | `19848973601acfd3a2b5070230fa40cdc7e4edb2` |
| `miyako/4d-plugin-common-string-algorithm` | `2606a68201866ec9fcbb38b51462d79215f504ef` |
| `miyako/4d-plugin-window-button` | `3f14facb9aaaaff0e22eeb8e07531163680c3a8a` |
| `miyako/4d-plugin-raw-picture-data` | `8144537fdc8dcc3d0c053dfe97aff0a8c0c3a6f9` |
| `miyako/4d-plugin-PRNG` | `522f62e1e9f388be0f3f226c1d4c39362dad2491` |

| Command | Returns | Purpose |
|---|---|---|
| [Get file description](#get-file-description-1) | Text | Get the OS-localized file type description for a path/extension |

**Platforms:** Windows, macOS

---

## Requirements & platform notes

- Takes exactly one mandatory parameter — there's no optional form.
- **The result depends only on the file's extension**, not on file contents or even file existence. `Get file description("C:\\made\\up\\path\\sample.pdf")` and `Get file description("sample.pdf")` return the same thing.
- **Failure is silent, not a 4D error.** If the extension isn't recognized by the OS, the command returns an empty string rather than raising an error — always check for an empty result rather than wrapping the call in error-catching code.
- **On macOS**, the description comes from `NSWorkspace`/Uniform Type Identifiers, and is localized to the user's macOS system language.
- **On Windows**, the description comes from the Windows Shell (`SHGetFileInfo`), localized to the user's Windows display language.
- Because each platform pulls from its own OS type-registration database, **the exact wording of the description can differ between macOS and Windows for the same extension** (e.g. one might say "Text Document", the other "Plain Text File") — don't rely on an exact string match across platforms; compare by extension instead if you need cross-platform branching logic.
- Three extensions get special-cased on macOS — `.key`, `.pages`, `.numbers` (Keynote, Pages, Numbers) — so their descriptions are correct even on a Mac that doesn't have iWork installed, or with iCloud stub types the system's own database doesn't always resolve correctly on its own.

---

## Get file description

### Syntax

```
Get file description ( path ) -> Result
```

| Parameter | Type | Description |
|---|---|---|
| `path` | Text | A file path, or just a file name/extension. The file does not need to exist. |
| Result | Text | The OS's localized file type description, or an empty string if the extension isn't recognized. |

### Description

Pass any string ending in a file extension — a full path, a bare file name, or even just `".pdf"` — and the command returns the description the operating system associates with that extension.

**On Windows**, this is implemented via `SHGetFileInfo` with `SHGFI_USEFILEATTRIBUTES`, which explicitly tells Windows to derive the type from the name/extension alone and skip touching the file on disk — so it works identically for real files, files that don't exist yet, and paths on drives that aren't currently connected.

**On macOS**, this is implemented via Uniform Type Identifiers and `NSWorkspace`. Three iWork formats (`.key`, `.pages`, `.numbers`) are matched explicitly to their correct Apple-defined type identifiers before falling back to the system's general extension lookup, so those three always resolve correctly.

If the extension is one the OS doesn't recognize at all (a made-up or extremely obscure extension), the command returns an empty string. This is not a 4D error — check `$description=""` if you need to detect that case.

### Example

From the plugin's own test method (`TEST.4dm`):

```4d
$description:=Get file description ("sample.txt")
$description:=Get file description ("sample.key")
$description:=Get file description ("sample.pages")
$description:=Get file description ("sample.numbers")
```

A couple of realistic variations built on that same pattern:

```4d
 // Check before using the result, since an unrecognized extension returns an empty string
$description:=Get file description ("archive.zip")
If ($description#"")
	ALERT($description)
Else
	ALERT("Unknown file type")
End if
```

```4d
 // Works from a full path just as well as a bare file name
$path:=Get 4D folder(Current resources folder)+"logo.png"
$description:=Get file description ($path)
```

---

## Error handling & troubleshooting

- **Empty string means "unrecognized extension," not an error.** The command never raises a 4D error for a bad or unknown extension — it just returns `""`. Always test the result rather than wrapping the call in `ON ERR CALL`.
- **Don't compare descriptions across platforms.** macOS and Windows pull from different, independently maintained type databases, so wording for the same extension can legitimately differ between the two OSes even though both are "correct." If your code needs to branch on file type, branch on the extension itself, not on the text of the description.
- **The path doesn't need to exist.** If you're getting an unexpected empty result, double-check the extension itself (typos, missing extension, no extension at all) rather than the path's validity — existence isn't checked.
- **iWork files (macOS):** `.key`/`.pages`/`.numbers` are special-cased specifically because the system's own generic UTI lookup doesn't always resolve them correctly (particularly for iCloud-only/stub files) — this only applies on macOS; Windows has no special casing since it doesn't have a native concept of these formats.

---

## Quick reference

```4d
$description:=Get file description ("report.docx")
If ($description="")
	$description:="Unknown file type"
End if
```
