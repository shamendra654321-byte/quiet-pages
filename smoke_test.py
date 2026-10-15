"""Run manually: python smoke_test.py (downloads assets to QUIET_PAGES_DATA)."""
import tkinter as tk
import numpy as np
import wave
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
    root.destroy()
    (DATA / 'smoke-test.txt').write_text('\n'.join(results), encoding='utf-8')
    print('\n'.join(results))


if __name__ == '__main__':
    run()
