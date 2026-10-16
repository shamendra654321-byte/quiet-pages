# Talevoxa

Previously called Quiet Pages. Existing users can update in the app. Download filenames, the repository address and the local data folder retain their original names for compatibility. Existing shortcuts still work; running the new installer adds Talevoxa to Start.

A free Windows desktop reader for listening to your books with local Kokoro voices.

**Download page, voice samples and updates:** https://shamendra654321-byte.github.io/quiet-pages/

## Windows download

Download `QuietPages-Setup-Windows-x64.exe` from Releases for a per-user installation with a Start menu shortcut and uninstaller. Alternatively, extract the entire `QuietPages-Windows-x64.zip` and open `QuietPages.exe`. No Python installation is needed. Both downloads are unsigned; Windows may show Unknown publisher.

The first Play or Preview downloads roughly 350 MB of model and voice data from the kokoro-onnx project's GitHub release. Keep an internet connection for this first step. Later listening works offline; book text is never uploaded. Files and reading positions are kept in `%LOCALAPPDATA%\QuietPages`.

## Features

- Open Word (.docx), DRM-free EPUB, text or scanned PDF and TXT books.
- Offline OCR, conservative repeated PDF margin/page-number cleanup and more spelled-out chapter numbers.
- Saved audio (2 GB cache), chapter seeking, 15-second rewind and a 15/30/60-minute sleep timer.
- Optional 12-second playback reserve for slower PCs.
- Choose a chapter, jump between chapters, and optionally stop after a chapter.
- Start after a short opening section, with the current and next chapter prepared in the background.
- Follow the full chapter with model-timed word highlighting and automatic scrolling.
- Get update notices inside the app, read release notes, download and restart without visiting a website.
- Nine American and British English male/female voices.
- Preview a narrator, adjust speed live from 0.5 to 2.0 without restarting, pause, resume and stop.
- Move between passages and resume at the last saved passage when reopening a book.
- CPU inference; no paid service or GPU required.

Start with Heart or Bella. Emma offers a British female alternative; Michael and George provide male options. Pleasantness is subjective: use Preview before starting a long book.

## Current limitations

This is an early prototype. Scanned pages are recognised locally. OCR can misread handwriting, poor scans and columns; English scans are the initial tested use case. Disable PDF margin cleanup in Help before reopening a file if necessary. DRM-protected books are unsupported. PDF columns, headers and unusual layouts may read imperfectly. English narration only in this version. Bookmarks resume at the start of a passage, not an exact audio timestamp. The first playback loads the voice engine, then prepares a short opening section. Later sections and the next chapter are prepared while playback continues; slower CPUs may still need to buffer. Word alignment can be imperfect on unusual text. Natural pauses and voice-model prosody remain. The portable build is unsigned. Windows ARM and clean-machine compatibility still need separate validation.

## Faster playback and word highlighting

Preview 5 uses a background worker to prepare audio ahead of playback, keeping one output stream open across chapters. It starts with a short sentence rather than waiting for the whole chapter. Preparation runs at most one chapter ahead, with a 256 MB pending-audio budget and temporary files removed as they are consumed. Pause allows preparation to continue; Stop cancels the queue and waits for the in-progress inference call before the voice engine is reused. Stop after this chapter never prepares or plays the following chapter.

Kokoro supplies phoneme timestamps. Talevoxa aligns those sounds to the original words, including expanded numbers, and schedules highlights using the audio timeline and device latency. It does not synthesize words separately or invent evenly spaced word timings. If timing is missing or cannot be matched reliably, passage highlighting remains available. Generated sections and timings are also saved in the local audio-cache folder, bounded to 2 GB with oldest-used entries evicted first. Voice, speed, text and synthesis version identify entries. Cached playback does not load the voice engine. Seeking within prepared passages uses audio time; unprepared passages start at their beginning. Rewind stays in the current chapter and falls back to the previous passage start if its duration is unknown. The sleep timer counts wall-clock time, including pauses.

## Updates inside the app

Starting with preview 4, Talevoxa checks the official public GitHub release list when it opens. An Update available button appears when a newer preview is ready. Choose it to read the announcement and download. Then choose Restart to update after stopping playback. Your voices and saved positions stay in the same data folder. This only contacts GitHub for release information and downloads; it never sends your book text.

Help → Check for updates checks manually. Help also lets you turn startup checks off. Being offline does not stop reading. GitHub rate limits can temporarily prevent checks.

Updates are checked against the SHA-256 digest supplied by GitHub and unpacked under `%LOCALAPPDATA%\QuietPages\updates`. The original portable folder stays intact. Its executable redirects to a newer installed copy, so existing shortcuts keep working. Keep that original folder. For recovery, run the original executable with `--skip-update` to bypass the newer copy. Old update folders are retained for now and can use disk space.

Preview 3 and earlier cannot update themselves: download this version once from the download page. Subsequent releases can be installed inside the app. Source-code runs do not self-install packaged updates.

## Word documents and chapters

Open .docx directly, with no Microsoft Word installation required. Ordinary paragraphs, hyperlink text and table cells are read in document order. Images, headers, footers and footnotes are not read. Older .doc files need to be saved as .docx in Word or LibreOffice first.

Use Heading 1 on chapter titles for best results. Inherited heading styles and explicit outline levels are recognized. EPUB chapters use contents links and reading order, including multiple chapters in one file. PDFs use top-level bookmarks at page boundaries. Standalone headings such as Chapter 1, Chapter Two, Prologue and Epilogue are a fallback for unstructured text. Documents without headings open as one section.

Stop playback to choose a different chapter. Leave “Stop after this chapter” unchecked for continuous reading; check it to finish the current chapter and wait at the next one. Chapter-aware importing changes passage boundaries, so some books opened in an older version may start from the beginning once after upgrading.

## Run from source

Use 64-bit Python 3.12 on Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## Test and build

```powershell
python -m unittest -v
.\build.ps1
```

Install NSIS before running build.ps1. The Windows workflow runs tests, builds the ZIP and installer, installs the app on its disposable runner, checks real voices/cache/OCR, then uninstalls and verifies book/data preservation before publishing a preview. See VALIDATION.md for the scope of validation; an automated build is not a clean-machine listening test.

## Credits

Kokoro model and voices by hexgrad: https://huggingface.co/hexgrad/Kokoro-82M

Voice descriptions and upstream quality estimates: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

Runtime and model download: https://github.com/thewh1teagle/kokoro-onnx

See THIRD_PARTY.md for dependency licensing. No books are included.

## Live speed adjustment

Speed changes apply to the audio currently playing, in small pitch-preserving WSOLA blocks. The normal-speed recording and its timestamps are reused at every tempo. Changing speed does not clear the prepared chapter, restart speech or leave pause mode. Already queued device audio introduces a short delay; Bluetooth may add more. Very fast/slow settings can introduce processing artifacts. Rewind uses 15 seconds at the current tempo. Invalid partial speed edits keep the last valid speed until a valid value is entered.
