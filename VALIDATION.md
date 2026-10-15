# Prototype validation — 15 October 2026

## Word and chapter update

- 13 automated checks passed: DOCX heading inheritance, outline levels, tables, hyperlinks and deleted text; EPUB spine order and fragment chapters; PDF bookmark chapters; text headings; DOC conversion guidance; continuous and chapter-limited playback; saved position; minimum window sizing.
- Playback-control tests use a simulated audio device. Real synthesis is checked separately by the packaged self-test.

- Windows x64 portable application built successfully with Python 3.12 and PyInstaller.
- Five import/chunk tests passed: text preservation, passage bounds, empty text, EPUB spine order, and scanned/blank PDF feedback.
- Heart, Bella, Emma and Michael each generated finite, non-silent audio from the same original sample passage.
- The packaged executable independently loaded its UI/runtime and generated all four audio samples, exiting successfully.
- Desktop screenshot inspection was unavailable because the desktop automation runtime could not start. Physical speaker output, interactive pause/resume, visual layout and a clean Windows machine have not yet been manually validated.
- Internet download was tested separately. The first-run download interface has not been exercised interactively.

Before calling this a stable public release, test opening representative EPUB/PDF/TXT books, first-run downloads, voice switching, pausing/resuming, stopping during generation, reopening a book and clean-machine operation.
