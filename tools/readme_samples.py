"""Regenerate the sample documents the README shows (#104).

The README shows John Smith's resume and cover letter (the fictional persona
in fixtures/personas/john_smith) as page images, so a visitor can see what
Jobforge produces before installing it. Images go stale silently, so each
one sits next to a text snapshot of the same document, and a test rebuilds
the documents on every run and fails when the text no longer matches. Then
run this again:

    python tools/readme_samples.py            # rebuild, write text and images
    python tools/readme_samples.py --check    # exit 1 if the snapshots are stale

Images are rendered the way a user opens the file: with Word on Windows
(Word to PDF, then Windows' own PDF renderer to PNG), or with LibreOffice
and pdftoppm on Linux. Nothing here runs in CI, and CI never commits (D-48).
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOHN = ROOT / "fixtures" / "personas" / "john_smith"
SAMPLES = ROOT / "docs" / "samples"
TODAY = _dt.date(2026, 11, 20)  # fixed, so the letter's date never changes
DOCS = {"resume": "John_Smith_Resume.docx", "cover_letter": "John_Smith_Cover_Letter.docx"}
WIDTH = 1100  # pixels; a US Letter page at about 130 dpi


def build(out: Path) -> dict[str, Path]:
    """John's Prairie Freight application, built the way a user builds one:
    a workspace, a captured posting, his plan, then `apply`."""
    from jobforge.apply import apply
    from jobforge.extract import from_text
    from jobforge.prepare import prepare
    from jobforge.workspace import init_workspace

    ws = init_workspace(out / "ws")
    shutil.copy(JOHN / "profile.toml", ws.profile_path)
    for f in (JOHN / "atoms").glob("*.toml"):
        shutil.copy(f, ws.atoms_dir / f.name)
    init_workspace(ws.root, refresh=True)
    job, _ = from_text((JOHN / "posting.txt").read_text(encoding="utf-8"),
                       company="Prairie Freight Co.", title="Operations Supervisor",
                       location="Springfield, IL",
                       url="https://example.com/jobs/ops-supervisor")
    folder, _ = prepare(ws, job, today=TODAY)
    plan = json.loads((JOHN / "plan.json").read_text(encoding="utf-8"))
    (folder / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    apply(ws, folder, today=TODAY)
    return {key: folder / name for key, name in DOCS.items()}


def snapshots(docs: dict[str, Path]) -> dict[str, str]:
    """What a parser reads from each document: the text the image shows."""
    from jobforge.docx import extract_text
    return {key: extract_text(path).replace("\r\n", "\n").rstrip("\n") + "\n"
            for key, path in docs.items()}


def stale(samples: Path = SAMPLES) -> list[str]:
    """The snapshots that no longer match freshly built documents."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh = snapshots(build(Path(tmp)))
    out = []
    for key, text in fresh.items():
        path = samples / f"{key}.txt"
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            out.append(key)
    return out


_WINDOWS_RENDER = r"""
param([string]$Docx, [string]$Pdf, [string]$Png, [int]$Width)
$ErrorActionPreference = "Stop"
$w = New-Object -ComObject Word.Application
$w.Visible = $false; $w.DisplayAlerts = 0
try {
  $d = $w.Documents.Open($Docx, $false, $true)
  $d.ExportAsFixedFormat($Pdf, 17)
  $d.Close(0)
} finally { $w.Quit() }
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$methods = [System.WindowsRuntimeSystemExtensions].GetMethods()
$asOp = ($methods | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asAct = ($methods | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
function Await($op, [Type]$t) { $task = $asOp.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait() | Out-Null; $task.Result }
function AwaitAction($op) { $task = $asAct.Invoke($null, @($op)); $task.Wait() | Out-Null }
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Pdf)) ([Windows.Storage.StorageFile])
$doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
if ($doc.PageCount -ne 1) { throw "expected one page, got $($doc.PageCount)" }
$folder = Await ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync([IO.Path]::GetDirectoryName($Png))) ([Windows.Storage.StorageFolder])
$out = Await ($folder.CreateFileAsync([IO.Path]::GetFileName($Png), [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
$stream = Await ($out.OpenAsync([Windows.Storage.FileAccessMode]::ReadWrite)) ([Windows.Storage.Streams.IRandomAccessStream])
$opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
$opts.DestinationWidth = $Width
AwaitAction ($doc.GetPage(0).RenderToStreamAsync($stream, $opts))
$stream.Dispose()
"""


def render(docx: Path, png: Path, tmp: Path) -> None:  # pragma: no cover (needs Word or LibreOffice)
    pdf = tmp / (docx.stem + ".pdf")
    if sys.platform == "win32":
        script = tmp / "render.ps1"
        script.write_text(_WINDOWS_RENDER, encoding="utf-8-sig")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(script), "-Docx", str(docx), "-Pdf", str(pdf),
                        "-Png", str(png.resolve()), "-Width", str(WIDTH)], check=True)
        return
    for tool in ("soffice", "pdftoppm"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not found: sudo apt install libreoffice poppler-utils")
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp),
                    str(docx)], check=True, capture_output=True)
    subprocess.run(["pdftoppm", "-png", "-singlefile", "-f", "1", "-scale-to-x", str(WIDTH),
                    "-scale-to-y", "-1", str(pdf), str(png.with_suffix(""))], check=True)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover (writes the repo)
    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        found = stale()
        for key in found:
            print(f"docs/samples/{key}.txt is stale. Run python tools/readme_samples.py, "
                  f"then commit the text and the image.")
        return 1 if found else 0
    SAMPLES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        docs = build(Path(tmp))
        for key, text in snapshots(docs).items():
            (SAMPLES / f"{key}.txt").write_text(text, encoding="utf-8", newline="\n")
        for key, path in docs.items():
            render(path, SAMPLES / f"{key}.png", Path(tmp))
            print(f"wrote docs/samples/{key}.txt and {key}.png")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
