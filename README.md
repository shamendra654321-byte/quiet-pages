# Quiet Pages

A free Windows desktop reader for listening to your books with local Kokoro voices.

## Windows download

Download `QuietPages-Windows-x64.zip` from this project's Releases, extract the entire folder, then open `QuietPages.exe`. No Python installation is needed. A release is not available until the maintainer uploads a tested build.

The first Play or Preview downloads roughly 350 MB of model and voice data from the kokoro-onnx project's GitHub release. Keep an internet connection for this first step. Later listening works offline; book text is never uploaded. Files and reading positions are kept in `%LOCALAPPDATA%\QuietPages`.

## Features

- Open DRM-free EPUB, text-based PDF and TXT books.
- Nine American and British English male/female voices.
- Preview a narrator, adjust speed from 0.5 to 2.0, pause, resume and stop.
- Move between passages and resume at the last saved passage when reopening a book.
- CPU inference; no paid service or GPU required.

Start with Heart or Bella. Emma offers a British female alternative; Michael and George provide male options. Pleasantness is subjective: use Preview before starting a long book.

## Current limitations

This is an early prototype. Scanned PDFs need OCR first. DRM-protected books are unsupported. PDF columns, headers and unusual layouts may read imperfectly. English narration only in this version. Bookmarks resume at the start of a passage, not an exact audio timestamp. Synthesis happens one passage at a time, so slower computers may pause between passages. The portable build is unsigned. Windows ARM and clean-machine compatibility still need separate validation.

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
