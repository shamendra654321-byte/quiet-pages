# Third-party components

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
