# Talevoxa: competitor research and free-product roadmap

Reviewed 16 October 2026. This is a review of public product pages and documentation, not a hands-on test of paid accounts. Features and limits vary by plan, model and device. Proposed features below are not release promises.

## Recommendation

Build an excellent free Windows book listener first: reliable long sessions, accurate document order, useful navigation and portable audiobooks. Keep speech generation on the user's computer so usage does not create a bill for us. Treat creator tools, study tools and mobile as later expansions. Do not advertise voice-quality parity without listening tests.

## NaturalReader: the product families

NaturalReader separates personal reading, commercial voice production and education. Its public homepage advertises multilingual voices, prompt-controlled delivery, cloning, mobile camera scanning, synchronized reading, MP3 export, browser access and an extension. Its AI study tools include podcasts, recaps, document chat, quizzes and screenshot analysis. [Official overview](https://www.naturalreaders.com/index.html)

The personal reader's documented feature inventory includes:

| Area | Advertised capabilities |
|---|---|
| Input | Documents, pasted text, webpage URLs, image OCR and manual OCR retry |
| Playback | Speed, volume, adjustable gaps, sentence repeat, alternating readers, timer, hotkeys |
| Voices | Favorites, pronunciation rules, cloning, styles |
| Navigation | Click-to-read, follow-scroll, return-to-current-text, resume, headings, thumbnails, bookmarks |
| Reading | Skip rules, highlights, notes, annotation export, reading queue |
| Files | Library, audio downloads, document sharing |
| Display | Word/sentence tracking, colors, dark mode, adjustable text settings |
| Study | Podcasts, recaps, chat, quizzes, flashcards, selected-region analysis |

Availability is not identical across devices or input types. Advanced capabilities require subscriptions. [Personal feature inventory](https://help.naturalreaders.com/en/articles/8823808-what-features-are-available-in-naturalreader-ai-text-to-speech-personal-version)

Personal paid plans currently start at USD 13.90/month or USD 79/year for Lite. The page lists one million monthly MP3 characters for Lite; higher tiers have their own voice and usage allocations. Personal subscriptions do not grant commercial audio use. [Plans and limits](https://help.naturalreaders.com/en/articles/8854700-plans-pricing-personal-version)

Commercial is a separate credit-based product; downloads require a paid plan and additional credits can be purchased. EDU adds organizational administration, shared material, accessibility support, device continuity and group/site licensing. [Commercial FAQ](https://www.naturalreaders.com/comm.html), [EDU](https://www.naturalreaders.com/edu.html)

## ElevenLabs: separate the reader from the production platform

Voice Library is a voice discovery and licensing platform, with thousands of voices, languages/accents, curated use cases and licensed iconic voices. It also promotes cloning, voice design, expressive narration and pronunciation dictionaries. A free sample is not a redistributable offline voice model. [Voice Library](https://elevenlabs.io/voice-library)

ElevenReader is the closer book-reading comparison: its official description covers file upload, pasted text, camera scanning, URLs and multilingual reading. It also includes a book catalog. That catalog and its commercial publishing relationships are separate from building a reader for files users already have. [ElevenReader](https://elevenlabs.io/docs/help-center/product/mobile-apps/eleven-reader/what-is-eleven-reader)

Studio's documented tools include editable narration, generation history, undo/redo, pauses, performance guidance from a recording, uploaded audio, music/SFX tracks, paragraph locking, video/captions, pronunciation dictionaries, metadata and normalization. Exports can cover one chapter or a whole project, as MP3/WAV or separate chapter files in a ZIP. Output quality and some export behavior depend on plan. [Studio documentation](https://elevenlabs.io/docs/eleven-creative/products/studio)

The broader platform includes speech recognition, dubbing, voice changing/isolation, music, sound effects, image/video tools, avatars and voice agents. Team collaboration and enterprise controls expand its scope well beyond book listening. Its Creative free plan lists 10,000 monthly credits and three Studio projects; commercial licensing starts on a paid tier. These are not unlimited free audiobook-generation resources. [Pricing and product families](https://elevenlabs.io/pricing), [Platform links](https://elevenlabs.io/voice-library)

## Our current baseline

The current code and README provide DOCX, EPUB, TXT and PDF reading; local scan OCR; conservative repeated-margin cleanup; chapter navigation; generation ahead into the next chapter; timestamp-based word highlighting; persistent audio caching; live 0.5–2x speed; seeking, rewind and a sleep timer; an installer and in-app updates. Nine English narrators are exposed. These are implemented features, not proof they work perfectly on every PC or book.

Current gaps include exact-position resume, reusable named bookmarks, a browsable bookshelf, pronunciation corrections, audio export, web import, richer accessibility controls, mobile and cross-device continuity. OCR and chapter detection still need real-book evaluation. The Windows publisher remains unverified.

## What we can build for free

These are engineering assessments, not claims made by competitors. “Free” means no mandatory subscription or per-book charge; local work still consumes device time, storage and electricity.

| Priority | Proposed work | Free implementation direction | Completion evidence |
|---|---|---|---|
| 1 | Long-session reliability | Keep one audio output stream; measure queue health and startup; protect cached audio | Two-hour book tests on ordinary Windows laptops, with no lost/repeated sentences |
| 1 | Exact resume and navigation | Save book identity, chapter, text offset and audio position; click-to-read; named bookmarks | Restart mid-sentence, reopen, and resume correctly across speed changes |
| 1 | Pronunciation dictionary | Per-book/global word replacements, preview and undo; version the cache key | Character names corrected without breaking original-text highlighting |
| 1 | Chapter audio export | Reuse saved speech; initially WAV, then MP3 and chaptered M4B after packaging/license review | Correct chapter order, tags and durations; resume a cancelled export without starting over |
| 1 | Better PDF/OCR control | Preview extracted text; edit reading order; optional header/footnote/citation skips | Compare against a manually checked set of scans, columns and illustrated books |
| 1 | Usable accessibility | Keyboard playback/navigation; font/spacing/contrast controls; screen-reader labels | Complete an import/play/seek/bookmark task using keyboard and screen reader |
| 1 | Installation confidence | Continue clean-machine testing and migration checks; arrange signing separately | Old app upgrades with bookmarks intact; new install/uninstall preserves user files |
| 2 | Bookshelf and queue | Local metadata database, cover thumbnails, search, finished/unread, multi-book queue | Thousands of entries remain responsive; moved/missing files recover gracefully |
| 2 | More inputs | Paste text, Markdown/HTML, image OCR and article extraction; extension later | Imported text excludes navigation/ads; original source is retained |
| 2 | More voices/languages | Optional voice packs, previews, language matching, favorites | Human reviews for every supported language plus speed/memory measurements |
| 2 | Personal reading aids | Notes/highlights export, sentence repeat, manual pause preferences | Reimport and source edits do not silently attach notes to wrong text |
| 3 | Mobile listening | First export files for phone players; native reader later | Offline listening, background audio and resume verified on target devices |
| 3 | Sync | User-selected storage or file export/import before hosted accounts | Conflicts and deletions are recoverable; private books are not public links |
| 3 | Study tools | Optional local language model for summaries/questions with source references | Output clearly separated from original text; quoted sources are verifiable |
| 3 | Character voices/studio | Manual speaker assignment and project export; automatic casting later | Dialogue remains correctly attributed and consistent across chapters |
| Research | Expressive/cloned voices | Optional local engine, consent-based recordings, separate downloads | Narration quality, stability, hardware load and voice/model licenses checked |
| Separate product | Dubbing, agents, music/video and school administration | Reconsider only after the reader is dependable | Independent scope, hosting budget, maintenance and rights requirements |

## Voice strategy

Keep Kokoro as the practical baseline. Its model card lists 82 million parameters, Apache-2.0 weights and a v1.0 release covering eight languages and 54 voices. Our nine-voice English UI does not expose that entire range; language front ends, packaging and quality checks are still required. [Kokoro model card](https://huggingface.co/hexgrad/Kokoro-82M)

Evaluate Chatterbox separately for richer narration and voice cloning. The upstream project is MIT-licensed and offers multilingual models. That makes it a research candidate, not proof it will outperform our current reader or run smoothly on low-end Windows machines. Check the exact model files and release requirements before bundling. [Chatterbox repository](https://github.com/resemble-ai/chatterbox)

Use a listening test set containing dialogue, long narration, unfamiliar names, numbers and mixed punctuation. Compare completeness, pronunciation, fatigue, startup time, speed of generation and peak memory. Choose a small set of pleasant, dependable voices before maximizing voice count. Do not extract competitors' voices or copy their proprietary assets.

## Suggested implementation order

1. Stabilize current playback and exact resume, including device changes and Bluetooth.
2. Add pronunciation fixes and export using the same cache/timing pipeline.
3. Improve document previews, manual corrections and accessibility.
4. Add a real bookshelf, queues, pasted text and article imports.
5. Expand verified language/voice packs.
6. Evaluate mobile, optional local study tools and richer narration.

Each release should announce only shipped behavior, give clear limitations and preserve existing files and reading positions. The roadmap is deliberately unpriced and undated until work is measured.

## Brand and Google search

The owner selected Talevoxa. Preliminary exact-name searches found no obvious competing product, but this is not a trademark, domain or app-store clearance. Keep the repository URL and updater asset names stable during the visible rename.

The GitHub homepage and sitemap already exist. Add Google ownership verification only using the owner's actual token. In Search Console, add the URL-prefix property https://shamendra654321-byte.github.io/quiet-pages/, choose HTML tag, publish the tag, then verify. Submit sitemap.xml and use URL Inspection to request homepage indexing. No token has been supplied yet, and no indexing request has been completed. [Google verification instructions](https://support.google.com/webmasters/answer/9008080?hl=en)

Google decides whether and when to index. Requests do not guarantee inclusion or ranking. Search-oriented titles, accurate visible descriptions and links from the public repository help discovery; structured data must describe real features, with no fabricated reviews or ratings. [Google recrawl guidance](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl)

The old chatgpt.site copy remains a separate site. A redirect or canonical update there is a follow-up migration task, not something completed by changing GitHub Pages.
