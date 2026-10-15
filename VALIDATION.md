# Prototype validation — 15 October 2026

## Preview 5: early playback, preparation ahead and word timing

- 34 automated tests passed, including playback starting before later synthesis finishes, preparation of the following chapter during current playback, one stream across chapters, sample preservation, pause/resume, stop/cancellation, worker failure propagation, source word offsets, number expansion, timing fallback, and delayed/cancelled UI highlights.
- Real Kokoro/Heart speech in a paced simulated stream produced 20.6 seconds across two chapters. First audio was ready in 0.64 seconds after engine loading, all 61 visible words received timestamps, and no buffering notices occurred. This is a single-machine measurement, not a performance guarantee; it does not include engine loading or model download time.
- The packaged self-test now checks two-chapter streaming and model-based word timestamps in addition to four narrator samples.
- Speaker playback, Bluetooth latency, subjective highlight accuracy and clean-machine compatibility still need hands-on testing. Weak CPUs may buffer. Unusual text can align imperfectly; missing/unreliable timing falls back to passage highlighting.

The following sections record earlier previews; their full-chapter preparation design was replaced in preview 5.

## Continuous chapters and in-app updates

- Automated checks cover preparing all chapter audio before the first stream opens, exact sample preservation across passage boundaries, cancellation during preparation/playback, chapter-only and continuous modes, saved positions, full-chapter highlighting and minimum window sizing.
- Updater checks cover numeric preview ordering, official download URL selection, SHA-256 and size validation, truncated and cancelled downloads, ZIP traversal and Windows path hazards, preserved original files, startup redirection, and rollback of the launch pointer if starting the update fails.
- UI checks verify that a background update notice does not interrupt reading and restarting waits until reading stops. Update process launches are mocked in automated tests; this is not a real upgrade test on a clean Windows machine.
- Synthesis is still bounded internally; a temporary audio file holds the whole chapter before playback. This removes generation stalls within a chapter but does not guarantee a particular voice's pronunciation or eliminate natural pauses. Each chapter has a preparation wait.

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
