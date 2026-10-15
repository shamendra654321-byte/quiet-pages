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
