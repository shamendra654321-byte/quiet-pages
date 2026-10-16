# Third-party components

Live pitch-preserving tempo changes use audiotsm 0.1.2 (MIT), https://github.com/Muges/audiotsm . Its license is included with installed dependency notices.

Offline scan recognition uses RapidOCR 1.4.4 (Apache-2.0) with its bundled PaddleOCR PP-OCRv4 models, OpenCV (Apache-2.0), Pillow, PyClipper, Shapely and PyYAML. PDF rendering uses pypdfium2 (Apache-2.0/BSD-3-Clause) and PDFium with its bundled dependency notices. Installer generation uses NSIS (zlib/libpng and component licenses). RapidOCR upstream: https://github.com/RapidAI/RapidOCR/tree/v1.4.4 ; model upstream: https://github.com/PaddlePaddle/PaddleOCR ; PDF rendering: https://github.com/pypdfium2-team/pypdfium2 ; installer: https://nsis.sourceforge.io/License .

Quiet Pages uses Kokoro-82M model/voice data (Apache-2.0), downloaded separately on first use, and kokoro-onnx (MIT).

The packaged application also includes espeak-ng via espeakng-loader. eSpeak NG is GPL-3.0-or-later. For a conservative distribution choice, Quiet Pages application source is offered under GPL-3.0-or-later. Preserve dependency notices and provide corresponding source when distributing compiled packages.

Other dependencies include Python (PSF), Tcl/Tk (Tcl/Tk licenses), ONNX Runtime (MIT), NumPy (BSD-3-Clause), phonemizer (GPL-3.0-or-later), sounddevice (MIT) and PortAudio (MIT), pypdf (BSD-3-Clause), Beautiful Soup (MIT), and their dependencies. The licenses folder in a distribution contains notices copied from installed packages. Review the complete source and license obligations before a public stable release.

Upstream source:
- https://github.com/hexgrad/kokoro
- https://github.com/thewh1teagle/kokoro-onnx
- https://github.com/thewh1teagle/espeakng-loader
- https://github.com/espeak-ng/espeak-ng
- https://github.com/bootphon/phonemizer
- https://github.com/spatialaudio/python-sounddevice
- https://github.com/PortAudio/portaudio
- https://github.com/py-pdf/pypdf
- https://git.launchpad.net/beautifulsoup
- https://github.com/microsoft/onnxruntime
- https://github.com/numpy/numpy
- https://github.com/python/cpython

Model assets: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1
