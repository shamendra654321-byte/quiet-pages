# Reader research — 15 October 2026

Public documentation reviewed for Word support and chapter navigation. These are design and format references; no application source code was copied.

| Reference | Finding | Quiet Pages decision |
| --- | --- | --- |
| [calibre viewer](https://manual.calibre-ebook.com/viewer.html) | Clickable contents, saved location and read-aloud controls | Separate chapter navigation from passage navigation |
| [Thorium listening help](https://support.thoriumreader.com/hc/en-us/articles/26704637551260-Listening-Desktop) and [navigation shortcuts](https://github.com/edrlab/thorium-reader/wiki/Keyboard-shortcuts) | Structured navigation and current reading location | Show the current chapter and passage; sequential listening |
| [Balabolka official site](https://www.cross-plus-a.com/balabolka.htm) | Broad document import, including DOC and DOCX | Add DOCX directly and explain conversion for legacy DOC |
| [python-docx styles documentation](https://python-docx.readthedocs.io/en/stable/user/styles-using.html) | Word heading styles and their stored names | Read styles, inheritance and outline levels from WordprocessingML |
| [W3C EPUB 3.3](https://www.w3.org/TR/epub-33/) | Reading order and navigation contents are distinct | Respect spine order and EPUB 3 / EPUB 2 contents, including fragment destinations |

This compact importer is not a full Word layout engine. Body paragraphs and table text are supported; images, notes, headers and footers are not. PDF chapter boundaries use bookmark pages. Unstructured documents use conservative standalone heading detection, otherwise one section. No cloud upload, Word automation or proprietary source is needed.

## Speechify reference and continuous playback

[Speechify's official feature overview](https://speechify.com/) describes document imports including DOCX/PDF/EPUB/TXT, voice choice, speed controls and offline listening for Premium. Quiet Pages prioritizes these reading needs with local free voices, chapters, a highlighted passage and saved location. This is an independently implemented Windows reader, not a claim of feature parity or better voice quality. OCR, a polished library, additional languages, mobile sync, audio export and word-level timing are future work, not included features.

[sounddevice stream documentation](https://python-sounddevice.readthedocs.io/en/latest/api/streams.html) supports block-wise writes to one OutputStream. Quiet Pages now prepares a whole chapter in a temporary disk file before opening one stream, removing synthesis waits and stream restarts within that chapter. Natural voice-model pauses remain. Whole-chapter preparation trades startup latency and temporary disk space for predictable playback; slow computers may wait longer between chapters.

[GitHub release API documentation](https://docs.github.com/en/rest/releases/releases) exposes release assets and their SHA-256 digests. The updater reads the releases list because the latest-release endpoint excludes previews. It verifies size and digest, rejects unsafe ZIP paths, installs alongside the current app, and preserves a working original launch path.
