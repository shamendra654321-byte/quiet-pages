"""Disposable, bounded local audio cache. Never uses pickle or network storage."""
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
import numpy as np


class AudioCache:
    def __init__(self, folder, limit=2 * 1024**3):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.limit = limit

    def path(self, text, voice, speed):
        # Bump format/model identity when synthesis or alignment changes.
        key = json.dumps(['kokoro-v1.0-timing-v2', text, voice, float(speed)], ensure_ascii=False)
        return self.folder / (hashlib.sha256(key.encode()).hexdigest() + '.npz')

    def get(self, text, voice, speed):
        path = self.path(text, voice, speed)
        try:
            with np.load(path, allow_pickle=False) as entry:
                samples = entry['samples']
                rate = int(entry['rate'])
                words = json.loads(str(entry['words']))
            if samples.ndim != 1 or not len(samples) or not np.isfinite(samples).all() or not 8000 <= rate <= 192000:
                raise ValueError('Invalid cached audio')
            if not isinstance(words, list) or any(len(w) != 4 or not all(isinstance(v, (int, float)) for v in w) for w in words):
                raise ValueError('Invalid cached timing')
            path.touch()
            return samples, rate, words
        except (OSError, ValueError, KeyError, EOFError, TypeError, zipfile.BadZipFile):
            return None

    def put(self, text, voice, speed, samples, rate, words):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.folder, suffix='.tmp', delete=False) as file:
                temporary = Path(file.name)
                np.savez(file, samples=samples, rate=rate, words=json.dumps(words))
            os.replace(temporary, self.path(text, voice, speed))
            entries = sorted(self.folder.glob('*.npz'), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in entries)
            for entry in entries:
                if total <= self.limit:
                    break
                total -= entry.stat().st_size
                entry.unlink(missing_ok=True)
        except OSError:
            pass  # A full or read-only cache must never interrupt a book.
        finally:
            if temporary:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
