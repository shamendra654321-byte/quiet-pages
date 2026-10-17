"""Verified individual voice downloads, shared engine and legacy pack reuse."""
import hashlib
import threading
import urllib.request
from pathlib import Path
import numpy as np
from voice_catalog import BY_ID

MODEL_BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
VOICE_BASE = 'https://github.com/shamendra654321-byte/quiet-pages/releases/download/english-voices-v1/'


class VoiceStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, voice):
        if voice not in BY_ID:
            raise ValueError('Unknown voice')
        return self.folder / 'voices' / (voice + '.npy')

    def ready(self, voice):
        return self.path(voice).exists() or (self.folder / 'voices-v1.0.bin').exists()

    def download(self, url, target, cancel, report, digest=None):
        if target.exists():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix('.download')
        try:
            hasher = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=30) as response, partial.open('wb') as out:
                total = int(response.headers.get('Content-Length', 0))
                count = 0
                while True:
                    if cancel.is_set():
                        raise InterruptedError()
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    out.write(block)
                    hasher.update(block)
                    count += len(block)
                    report(f'Downloading {target.stem}: {count / 1048576:.1f}' + (f' / {total / 1048576:.1f} MB' if total else ' MB'))
            if (total and count != total) or not count:
                raise ValueError('Download was incomplete. Please retry.')
            if digest and hasher.hexdigest() != digest:
                raise ValueError('Voice download failed verification. Please retry.')
            if cancel.is_set():
                raise InterruptedError()
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)

    def ensure(self, voices, cancel, report):
        with self.lock:
            for voice in voices:
                if cancel.is_set():
                    raise InterruptedError()
                target = self.path(voice)
                if not target.exists():
                    legacy = self.folder / 'voices-v1.0.bin'
                    if legacy.exists():
                        with np.load(legacy, allow_pickle=False) as pack:
                            if voice in pack:
                                target.parent.mkdir(exist_ok=True)
                                temporary = target.with_suffix('.download')
                                with temporary.open('wb') as output:
                                    np.save(output, pack[voice], allow_pickle=False)
                                temporary.replace(target)
                    if not target.exists():
                        self.download(VOICE_BASE + target.name, target, cancel, report, BY_ID[voice]['sha256'])
                self.load(voice)
                report(f'{BY_ID[voice]["name"]} downloaded')
            self.download(MODEL_BASE + 'kokoro-v1.0.onnx', self.folder / 'kokoro-v1.0.onnx', cancel, report)

    def load(self, voice):
        target = self.path(voice)
        if hashlib.sha256(target.read_bytes()).hexdigest() != BY_ID[voice]['sha256']:
            target.unlink(missing_ok=True)
            raise ValueError('Saved voice is damaged. Download it again.')
        value = np.load(target, allow_pickle=False)
        if value.shape != (510, 1, 256) or not np.isfinite(value).all():
            raise ValueError('Invalid voice data')
        return value

    def engine_pack(self, voice):
        # Engine opens this once. Keep individual files as the authoritative cache.
        target = self.folder / 'selected-voice.npz'
        with target.open('wb') as output:
            np.savez(output, **{voice: self.load(voice)})
        return target
