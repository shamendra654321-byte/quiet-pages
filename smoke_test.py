"""Run manually: python smoke_test.py (downloads assets to QUIET_PAGES_DATA)."""
import tkinter as tk
import numpy as np
import wave
import queue
import threading
import time
import tempfile
from pathlib import Path
from audio_cache import AudioCache
from reader_core import load_document
from live_tempo import TempoControl
from chapter_audio import read_book
from app import Reader, DATA


def run():
    root = tk.Tk()
    root.withdraw()
    reader = Reader(root)
    root.update()
    engine = reader.get_engine()
    results = []
    from voice_catalog import BY_ID
    for voice in BY_ID:
        engine = reader.get_engine(voice)
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
    tempo = TempoControl()
    class RecordingStream:
        def __init__(self, samplerate, **kwargs):
            self.frames = 0
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
            self.frames += len(samples)
            tempo.set(1 if self.frames < 24000 else 1.7 if self.frames < 48000 else .8)
        def abort(self): raise AssertionError('Unexpected cancellation')
    read_book(engine, parts, 0, len(parts), [0, 1], 'af_heart', 1,
              threading.Event(), threading.Event(), q, RecordingStream, live_speed=tempo.get)
    words = [value[2] for kind, value in list(q.queue) if kind == 'at' and value[1] == 'word']
    assert len(words) == sum(len(part.split()) for part in parts), 'Missing word timestamps'
    assert [parts[i][left:right] for i, left, right in words] == ' '.join(parts).split()
    results.append(f'Streaming: first audio {first_audio[0]:.2f}s after engine load; {len(words)} timed words, two chapters, live tempo 1 / 1.7 / 0.8')
    with tempfile.TemporaryDirectory() as folder:
        cache = AudioCache(Path(folder) / 'cache')
        for attempt in range(2):
            def no_engine():
                raise AssertionError('Replay should not load the voice engine')
            read_book(engine if attempt == 0 else no_engine, ['The garden was quiet.'], 0, 1, [0],
                      'af_heart', 1, threading.Event(), threading.Event(), queue.Queue(),
                      RecordingStream, cache=cache)
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (1200, 1600), 'white')
        font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 40)
        ImageDraw.Draw(image).text((100, 200), 'The quiet garden was full of flowers.', font=font, fill='black')
        scan = Path(folder) / 'scan.pdf'
        image.save(scan, 'PDF')
        assert 'quiet garden' in ' '.join(load_document(scan).parts).lower()
    results.append('Persistent cache replay and offline scanned PDF recognition passed')
    root.destroy()
    (DATA / 'smoke-test.txt').write_text('\n'.join(results), encoding='utf-8')
    print('\n'.join(results))


if __name__ == '__main__':
    run()
