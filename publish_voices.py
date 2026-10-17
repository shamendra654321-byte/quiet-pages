"""CI: publish deterministic, verified voice files once for individual downloads."""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request
import numpy as np
from voice_catalog import BY_ID
from voice_store import MODEL_BASE


def main():
    tag = 'english-voices-v1'
    output = Path('dist/voice-assets')
    output.mkdir(parents=True, exist_ok=True)
    pack = output / 'source.bin'
    urllib.request.urlretrieve(MODEL_BASE + 'voices-v1.0.bin', pack)
    files = []
    with np.load(pack, allow_pickle=False) as source:
        for key, info in BY_ID.items():
            target = output / (key + '.npy')
            np.save(target, source[key], allow_pickle=False)
            if hashlib.sha256(target.read_bytes()).hexdigest() != info['sha256']:
                raise ValueError(f'Upstream voice changed: {key}')
            files.append(str(target))
    license_file = output / 'LICENSE.txt'
    urllib.request.urlretrieve('https://raw.githubusercontent.com/hexgrad/kokoro/main/LICENSE', license_file)
    files.append(str(license_file))
    notes = output / 'NOTES.md'
    notes.write_text('Kokoro v1.0 English voice styles, repackaged without changing their arrays from thewh1teagle/kokoro-onnx model-files-v1.1. Model and voices: hexgrad/Kokoro-82M, Apache-2.0. This is a voice data pack, not an app update.\n\nSources: https://huggingface.co/hexgrad/Kokoro-82M and https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1\n', encoding='utf-8')
    existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets'], capture_output=True, text=True)
    if existing.returncode == 0:
        names = {a['name'] for a in json.loads(existing.stdout)['assets']}
        missing = [f for f in files if Path(f).name not in names]
        if missing:
            subprocess.run(['gh', 'release', 'upload', tag, *missing], check=True)
    else:
        subprocess.run(['gh', 'release', 'create', tag, *files, '--title', 'English voice downloads', '--prerelease', '--latest=false', '--notes-file', str(notes)], check=True)


if __name__ == '__main__':
    main()
