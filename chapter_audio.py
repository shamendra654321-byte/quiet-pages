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
from live_tempo import tempo_blocks

MAX_BUFFER_BYTES = 256 * 1024 * 1024


def read_book(engine, parts, start, end, chapter_starts, voice, speed, cancel,
              paused, events, stream_factory, preview=False, cache=None, start_seconds=0, buffer_seconds=0,
              live_speed=None):
    chapters = chapter_starts or [0]
    chapter_for = lambda index: max(0, bisect_right(chapters, index) - 1)
    condition = threading.Condition()
    state = {'chapter': chapter_for(start), 'bytes': 0, 'seconds': 0, 'finished': False, 'blocked': False}
    ready = queue.Queue()
    shutdown = threading.Event()
    lang = 'en-gb' if voice.startswith('b') else 'en-us'
    stopped = lambda: cancel.is_set() or shutdown.is_set()
    pronunciation_cache = {}
    with tempfile.TemporaryDirectory(prefix='quiet-pages-audio-') as folder:
        def produce():
            try:
                serial = 0
                for index in range(start, end):
                    chapter = chapter_for(index)
                    elapsed = 0
                    for offset, text in speech_sections(parts[index], first=True):
                        with condition:
                            while not stopped() and (chapter > state['chapter'] + 1 or state['bytes'] >= MAX_BUFFER_BYTES):
                                state['blocked'] = True
                                condition.notify_all()
                                condition.wait(0.05)
                            state['blocked'] = False
                        if stopped():
                            return
                        cached = cache.get(text, voice, speed) if cache and not preview else None
                        active_engine = engine() if cached is None and callable(engine) else engine
                        if cached is not None:
                            samples, rate, words = cached
                        elif getattr(active_engine, 'has_timings', False):
                            samples, rate, spoken = active_engine.create_timed(text, voice=voice, speed=speed, lang=lang)
                            # Resolve lazy engines only on a cache miss.
                            def active_phonemize(word):
                                if word not in pronunciation_cache:
                                    if len(pronunciation_cache) >= 4096:
                                        pronunciation_cache.clear()
                                    pronunciation_cache[word] = active_engine.tokenizer.phonemize(word, lang)
                                return pronunciation_cache[word]
                            words = word_timings(text, spoken, active_phonemize) if not preview else []
                        else:
                            samples, rate = active_engine.create(text, voice=voice, speed=speed, lang=lang)
                            words = []
                        if stopped():
                            return
                        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
                        if not len(samples) or not np.isfinite(samples).all():
                            raise ValueError('The voice could not read this section. Please try another voice.')
                        if cached is None and cache and not preview:
                            cache.put(text, voice, speed, samples, rate, words)
                        section_start = elapsed
                        elapsed += len(samples) / rate
                        skip = min(len(samples), max(0, round((start_seconds - section_start) * rate))) if index == start else 0
                        if skip == len(samples):
                            continue
                        samples = samples[skip:]
                        words = [(max(0, b - skip/rate), f - skip/rate, l, r) for b, f, l, r in words if f > skip/rate]
                        path = Path(folder) / f'{serial}.npy'
                        np.save(path, samples, allow_pickle=False)
                        size = samples.nbytes
                        with condition:
                            state['bytes'] += size
                            state['seconds'] += len(samples) / rate
                            condition.notify_all()
                        ready.put((path, rate, index, offset, words, size, section_start + skip/rate))
                        serial += 1
                    if not preview:
                        events.put(('duration', (index, elapsed)))
                    if index + 1 == end or chapter_for(index + 1) != chapter:
                        events.put(('prepared', chapter))
            except Exception as error:
                ready.put(error)
            finally:
                with condition:
                    state['finished'] = True
                    condition.notify_all()
                ready.put(None)

        worker = threading.Thread(target=produce, daemon=True)
        worker.start()
        if buffer_seconds:
            events.put(('status', 'Building a playback reserve for smoother listening…'))
            reserve = buffer_seconds * (live_speed() if live_speed else 1)
            with condition:
                while not stopped() and not state['finished'] and not state['blocked'] and state['seconds'] < reserve:
                    condition.wait(0.05)
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
                    path, sample_rate, index, text_offset, words, size, section_start = item
                    samples = np.load(path, allow_pickle=False)
                    path.unlink()
                    with condition:
                        state['bytes'] -= size
                        state['seconds'] -= len(samples) / sample_rate
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
                    blocks = tempo_blocks(samples, live_speed) if live_speed else (
                        (samples[o:o + 512], o, min(o + 512, len(samples))) for o in range(0, len(samples), 512))
                    block_number = 0
                    for block, offset, source_end in blocks:
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
                        if not preview and block_number % 8 == 0:
                            events.put(('at', (due, 'cursor', (index, section_start + offset / rate))))
                        if not preview and index != last_index:
                            events.put(('at', (due, 'position', index)))
                            last_index = index
                        while word_index < len(words) and words[word_index][0] * rate < source_end:
                            begin, finish, left, right = words[word_index]
                            if not preview:
                                ratio = (source_end - offset) / len(block)
                                events.put(('at', (due + max(0, begin - offset / rate) / ratio, 'word',
                                                   (index, text_offset + left, text_offset + right))))
                            word_index += 1
                        underflow = stream.write(block.reshape(-1, 1))
                        total_frames += len(block)
                        block_number += 1
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
