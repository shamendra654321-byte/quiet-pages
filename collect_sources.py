"""Bundle source archives for the GPL speech components with the portable app."""
import json
import urllib.request
from pathlib import Path

target = Path('dist/QuietPages/third-party-source')
target.mkdir(parents=True, exist_ok=True)
assets = {
    'espeak-ng-1.52.0.tar.gz': 'https://github.com/espeak-ng/espeak-ng/archive/refs/tags/1.52.0.tar.gz',
    'espeakng-loader-build.sh': 'https://raw.githubusercontent.com/thewh1teagle/espeakng-loader/main/build.sh',
}
with urllib.request.urlopen('https://pypi.org/pypi/phonemizer/3.4.0/json', timeout=30) as response:
    metadata = json.load(response)
for item in metadata['urls']:
    if item['packagetype'] == 'sdist':
        assets[item['filename']] = item['url']
for name, url in assets.items():
    with urllib.request.urlopen(url, timeout=60) as response:
        (target / name).write_bytes(response.read())
print('Speech component source archives included.')
