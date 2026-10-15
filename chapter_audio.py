"""Prepare a complete chapter on disk before opening the audio device."""
import tempfile
import time
import numpy as np


def read_chapter(engine, parts, start, end, voice, speed, cancel, paused,
                 events, stream_factory, preview=False):
    # Disk backing bounds memory even for an entire book with no chapter headings.
    with tempfile.TemporaryFile() as audio:
        boundaries = []
        rate = None
        total = 0
        for index in range(start, end):
            if cancel.is_set():
                return
            events.put(('status', f'Preparing chapter: {index - start + 1} / {end - start} · playback will be continuous'))
            samples, sample_rate = engine.create(parts[index], voice=voice, speed=speed,
                                                 lang='en-gb' if voice.startswith('b') else 'en-us')
            if cancel.is_set():
                return
            if rate is not None and sample_rate != rate:
                raise ValueError('The voice changed audio format during this chapter. Please try again.')
            rate = sample_rate
            samples = np.asarray(samples, dtype=np.float32).reshape(-1)
            if not len(samples) or not np.isfinite(samples).all():
                raise ValueError('The voice could not read this section. Please try another voice.')
            boundaries.append((total, index))
            audio.write(samples.tobytes())
            total += len(samples)
        if not total or cancel.is_set():
            return
        audio.seek(0)
        events.put(('status', 'Reading aloud · Chapter prepared'))
        position = 0
        boundary = 0
        # One stream for the whole chapter: no synthesis or device restart between passages.
        with stream_factory(samplerate=rate, channels=1, dtype='float32') as stream:
            while position < total:
                while paused.is_set() and not cancel.is_set():
                    time.sleep(0.05)
                if cancel.is_set():
                    stream.abort()
                    return
                while boundary < len(boundaries) and boundaries[boundary][0] <= position:
                    if not preview:
                        events.put(('position', boundaries[boundary][1]))
                    boundary += 1
                next_boundary = boundaries[boundary][0] if boundary < len(boundaries) else total
                count = min(1024, next_boundary - position)
                samples = np.frombuffer(audio.read(count * 4), dtype=np.float32)
                stream.write(samples.reshape(-1, 1))
                position += len(samples)
        if not preview and not cancel.is_set() and end < len(parts):
            events.put(('position', end))
