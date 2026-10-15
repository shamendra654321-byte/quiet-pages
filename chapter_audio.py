"""Start early and prepare the current and following chapter on a worker thread."""
import contextlib
import queue
import tempfile
import threading
import time
from bisect import bisect_right
from pathlib import Path
import numpy as np
from word_timing import speech_sections, word_timings

MAX_BUFFER_BYTES = 256 * 1024 * 1024


def read_book(engine, parts, start, end, chapter_starts, voice, speed, cancel,
              paused, events, stream_factory, preview=False):
    chapters = chapter_starts or [0]
    chapter_for = lambda index: max(0, bisect_right(chapters, index) - 1)
    condition = threading.Condition()
    state = {'chapter': chapter_for(start), 'bytes': 0}
    ready = queue.Queue()
    shutdown = threading.Event()
    lang = 'en-gb' if voice.startswith('b') else 'en-us'
    stopped = lambda: cancel.is_set() or shutdown.is_set()
    pronunciation_cache = {}
    def phonemize(word):
        if word not in pronunciation_cache:
            if len(pronunciation_cache) >= 4096:
                pronunciation_cache.clear()
            pronunciation_cache[word] = engine.tokenizer.phonemize(word, lang)
        return pronunciation_cache[word]

    with tempfile.TemporaryDirectory(prefix='quiet-pages-audio-') as folder:
        def produce():
            try:
                serial = 0
                for index in range(start, end):
                    chapter = chapter_for(index)
                    for offset, text in speech_sections(parts[index], first=index == start):
                        with condition:
                            while not stopped() and (chapter > state['chapter'] + 1 or state['bytes'] >= MAX_BUFFER_BYTES):
                                condition.wait(0.05)
                        if stopped():
                            return
                        if getattr(engine, 'has_timings', False):
                            samples, rate, spoken = engine.create_timed(text, voice=voice, speed=speed, lang=lang)
                            words = word_timings(text, spoken, phonemize) if not preview else []
                        else:
                            samples, rate = engine.create(text, voice=voice, speed=speed, lang=lang)
                            words = []
                        if stopped():
                            return
                        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
                        if not len(samples) or not np.isfinite(samples).all():
                            raise ValueError('The voice could not read this section. Please try another voice.')
                        path = Path(folder) / f'{serial}.npy'
                        np.save(path, samples, allow_pickle=False)
                        size = samples.nbytes
                        with condition:
                            state['bytes'] += size
                        ready.put((path, rate, index, offset, words, size))
                        serial += 1
                    if index + 1 == end or chapter_for(index + 1) != chapter:
                        events.put(('prepared', chapter))
            except Exception as error:
                ready.put(error)
            finally:
                ready.put(None)

        worker = threading.Thread(target=produce, daemon=True)
        worker.start()
        total_frames = 0
        base = None
        last_index = None
        try:
            with contextlib.ExitStack() as stack:
                stream = None
                rate = None
                while not stopped():
                    waiting = time.monotonic()
                    while True:
                        if stopped():
                            if stream is not None:
                                stream.abort()
                            return
                        try:
                            item = ready.get(timeout=0.05)
                            break
                        except queue.Empty:
                            if time.monotonic() - waiting > 0.25:
                                events.put(('status', 'Preparing the opening…' if stream is None else 'Buffering more speech…'))
                                waiting = time.monotonic()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item
                    path, sample_rate, index, text_offset, words, size = item
                    samples = np.load(path, allow_pickle=False)
                    path.unlink()
                    with condition:
                        state['bytes'] -= size
                        state['chapter'] = chapter_for(index)
                        condition.notify_all()
                    if stream is None:
                        rate = sample_rate
                        stream = stack.enter_context(stream_factory(samplerate=rate, channels=1, dtype='float32'))
                        base = time.monotonic() + float(getattr(stream, 'latency', 0))
                    if sample_rate != rate:
                        raise ValueError('The voice changed audio format. Please try again.')
                    latency = float(getattr(stream, 'latency', 0))
                    # If generation fell behind the device, restart the audio clock.
                    if time.monotonic() > base + total_frames / rate:
                        base = time.monotonic() + latency - total_frames / rate
                    events.put(('status', 'Reading aloud · Preparing ahead' if words else 'Reading aloud · Passage highlighting'))
                    word_index = 0
                    for offset in range(0, len(samples), 512):
                        if paused.is_set():
                            if hasattr(stream, 'stop'):
                                stream.stop()  # Let already-submitted sound and highlights finish.
                            while paused.is_set() and not stopped():
                                time.sleep(0.03)
                            if not stopped():
                                if hasattr(stream, 'start'):
                                    stream.start()
                                base = time.monotonic() + latency - total_frames / rate
                        if stopped():
                            stream.abort()
                            return
                        due = base + total_frames / rate
                        if not preview and index != last_index:
                            events.put(('at', (due, 'position', index)))
                            last_index = index
                        while word_index < len(words) and words[word_index][0] * rate < offset + 512:
                            begin, finish, left, right = words[word_index]
                            if not preview:
                                events.put(('at', (due + max(0, begin - offset / rate), 'word',
                                                   (index, text_offset + left, text_offset + right))))
                            word_index += 1
                        block = samples[offset:offset + 512]
                        underflow = stream.write(block.reshape(-1, 1))
                        total_frames += len(block)
                        if underflow:
                            base = time.monotonic() + latency - total_frames / rate
            if not preview and not cancel.is_set() and end < len(parts):
                events.put(('at', ((base + total_frames / rate) if rate else time.monotonic(), 'position', end)))
        finally:
            shutdown.set()
            with condition:
                condition.notify_all()
            worker.join()  # Never reuse the voice engine while inference is still finishing.


def read_chapter(engine, parts, start, end, voice, speed, cancel, paused,
                 events, stream_factory, preview=False):
    read_book(engine, parts, start, end, [start], voice, speed, cancel, paused,
              events, stream_factory, preview)
