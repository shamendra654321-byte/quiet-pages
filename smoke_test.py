"""Run manually: python smoke_test.py (downloads assets to QUIET_PAGES_DATA)."""
import tkinter as tk
import numpy as np
import wave
import queue
import threading
import time
from chapter_audio import read_book
from app import Reader, DATA


def run():
    root = tk.Tk()
    root.withdraw()
    reader = Reader(root)
    root.update()
    engine = reader.get_engine()
    results = []
    for voice in ('af_heart', 'af_bella', 'bf_emma', 'am_michael'):
        samples, rate = engine.create('The evening light fell softly across the room. She opened her book, settled into a comfortable chair, and let the story carry her away.', voice=voice, speed=0.95, lang='en-gb' if voice.startswith('b') else 'en-us')
        assert len(samples) > rate and np.isfinite(samples).all()
        assert np.max(np.abs(samples)) > 0.01
        with wave.open(str(DATA / f'{voice}.wav'), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
        results.append(f'{voice}: {len(samples)/rate:.1f} seconds')
    parts = ['Nora opened the letter. She read the date: October 15, 2026.',
             'The next chapter was ready. She settled back and listened.']
    q = queue.Queue()
    first_audio = []
    started = time.monotonic()
    class RecordingStream:
        def __init__(self, samplerate, **kwargs):
            self.output = wave.open(str(DATA / 'streaming-smoke.wav'), 'wb')
            self.output.setnchannels(1)
            self.output.setsampwidth(2)
            self.output.setframerate(samplerate)
        def __enter__(self): return self
        def __exit__(self, *args): self.output.close()
        def write(self, samples):
            if not first_audio:
                first_audio.append(time.monotonic() - started)
            self.output.writeframes((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
        def abort(self): raise AssertionError('Unexpected cancellation')
    read_book(engine, parts, 0, len(parts), [0, 1], 'af_heart', 1,
              threading.Event(), threading.Event(), q, RecordingStream)
    words = [value[2] for kind, value in list(q.queue) if kind == 'at' and value[1] == 'word']
    assert len(words) == sum(len(part.split()) for part in parts), 'Missing word timestamps'
    assert [parts[i][left:right] for i, left, right in words] == ' '.join(parts).split()
    results.append(f'Streaming: first audio {first_audio[0]:.2f}s after engine load; {len(words)} timed words, two chapters')
    root.destroy()
    (DATA / 'smoke-test.txt').write_text('\n'.join(results), encoding='utf-8')
    print('\n'.join(results))


if __name__ == '__main__':
    run()
