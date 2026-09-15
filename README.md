![version](https://img.shields.io/badge/version-16%2B-8331AE)
![platform](https://img.shields.io/static/v1?label=platform&message=mac-intel%20|%20mac-arm%20|%20win-64&color=blue)
[![license](https://img.shields.io/github/license/miyako/4d-plugin-get-file-description)](LICENSE)
![downloads](https://img.shields.io/github/downloads/miyako/4d-plugin-get-file-description/total)

# 4d-plugin-get-file-description

Returns the operating system's human-readable file type description for a given file path or file name — the same string macOS Finder ("Get Info") or Windows Explorer ("Type of file") would show for that file. The plugin doesn't inspect the file's contents; it derives the description purely from the file's extension, so the path doesn't need to point to a file that actually exists on disk.

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
