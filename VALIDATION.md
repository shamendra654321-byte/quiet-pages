# Prototype validation — 15 October 2026

## Saved audio, PDF OCR and installer update

- 41 automated tests passed locally: cache replay without an engine load, exact samples after seeking, cache invalidation/corruption/quota, short-chapter buffering without deadlock, rewind, sleep expiry, safe seek restart, margin cleanup preserving body text, offline image-only PDF recognition and cancellation, plus existing tests.
- Real synthesis passed for Heart, Bella, Emma and Michael. Two chapters matched all 21 visible words; opening audio took 0.38 seconds after engine load in this run. This excludes download/loading and is not a speed guarantee.
- The packaged self-test now checks cache replay and offline OCR. Publication is gated on installer setup, that self-test, and uninstall preserving books/model data on a disposable Windows runner.
- Outstanding: verified publisher signing (no certificate/account available), physical speakers/Bluetooth, diverse books and ordinary low-end Windows PCs.

### Ordinary Windows PC acceptance checks

Use Windows 10/11 x64 without Python: install Setup, launch from Start, download voices, disconnect internet, read DOCX/EPUB and scanned PDF, replay, seek/rewind while playing, pause/resume, expire a sleep timer, update inside the app and uninstall. Confirm books/data remain. Compare default playback and Extra buffering on a slower PC; record CPU/RAM, first-audio wait and audible gaps. Verify the unsigned publisher warning remains truthful.

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

## Live tempo update

46 automated tests passed locally. New checks measure unchanged 440 Hz pitch and expected duration at 0.5/1/1.5/2x, retention of final audio, source-position continuity during repeated speed changes, one output stream and one synthesis call during an active speed change, invalid input handling, and pause/cursor preservation. The packaged self-test now changes tempo during real speech and verifies all word highlights still appear. Physical speaker/Bluetooth latency and subjective artifacts still need hands-on listening checks.

## Voice browser and individual downloads (17 October 2026)

65 unit/integration tests passed locally, including individual/all download reuse, checksum failure, cancellation cleanup, legacy pack reuse, favourites persistence, preview selection and window fit. All 28 English voices generated finite, non-silent sample audio (7.2 to 12.5 seconds for the same passage), with streaming, cache and OCR smoke checks passing. This is a technical synthesis check, not a long-form human listening review. Upstream grades are training-data estimates; voice pleasantness remains subjective.
