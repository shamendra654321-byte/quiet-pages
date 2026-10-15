# Quiet Pages

A free Windows desktop reader for listening to your books with local Kokoro voices.

**Download page, voice samples and updates:** https://quiet-pages.abuzzlion9.chatgpt.site

## Windows download

Download `QuietPages-Windows-x64.zip` from this project's Releases, extract the entire folder, then open `QuietPages.exe`. No Python installation is needed. A release is not available until the maintainer uploads a tested build.

The first Play or Preview downloads roughly 350 MB of model and voice data from the kokoro-onnx project's GitHub release. Keep an internet connection for this first step. Later listening works offline; book text is never uploaded. Files and reading positions are kept in `%LOCALAPPDATA%\QuietPages`.

## Features

- Open Word (.docx), DRM-free EPUB, text-based PDF and TXT books.
- Choose a chapter, jump between chapters, and optionally stop after a chapter.
- Prepare a whole chapter before playback, avoiding speech-generation gaps between passages.
- Follow along with the full chapter and a highlighted current passage.
- Get update notices inside the app, read release notes, download and restart without visiting a website.
- Nine American and British English male/female voices.
- Preview a narrator, adjust speed from 0.5 to 2.0, pause, resume and stop.
- Move between passages and resume at the last saved passage when reopening a book.
- CPU inference; no paid service or GPU required.

Start with Heart or Bella. Emma offers a British female alternative; Michael and George provide male options. Pleasantness is subjective: use Preview before starting a long book.

## Current limitations

This is an early prototype. Scanned PDFs need OCR first. DRM-protected books are unsupported. PDF columns, headers and unusual layouts may read imperfectly. English narration only in this version. Bookmarks resume at the start of a passage, not an exact audio timestamp. A chapter is prepared on disk before it starts; large chapters can take time and temporary disk space. There is a preparation wait between chapters, and natural pauses or voice-model prosody remain. The portable build is unsigned. Windows ARM and clean-machine compatibility still need separate validation.

## Updates inside the app

Starting with preview 4, Quiet Pages checks the official public GitHub release list when it opens. An Update available button appears when a newer preview is ready. Choose it to read the announcement and download. Then choose Restart to update after stopping playback. Your voices and saved positions stay in the same data folder. This only contacts GitHub for release information and downloads; it never sends your book text.

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

The Windows workflow runs import tests, builds a portable ZIP and publishes a clearly marked preview release. See VALIDATION.md for the scope of validation; an automated build is not a clean-machine listening test.

## Credits

Kokoro model and voices by hexgrad: https://huggingface.co/hexgrad/Kokoro-82M

Voice descriptions and upstream quality estimates: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

Runtime and model download: https://github.com/thewh1teagle/kokoro-onnx

See THIRD_PARTY.md for dependency licensing. No books are included.
