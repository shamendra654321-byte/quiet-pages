"""Small pitch-preserving playback blocks with a live, thread-safe tempo."""
import math
import threading
import numpy as np


class TempoControl:
    def __init__(self, value=1):
        self._lock = threading.Lock()
        self._value = value

    def set(self, value):
        try:
            value = float(value)
        except (ValueError, TypeError):
            return False
        if not math.isfinite(value) or not .5 <= value <= 2:
            return False
        with self._lock:
            self._value = value
        return True

    def get(self):
        with self._lock:
            return self._value


def tempo_blocks(samples, get_speed):
    """Yield (audio, source_start, source_end) at most 512 output frames at a time.

    Source offsets remain in the original recording for seeking/highlighting.
    Padding lets WSOLA process the final speech frame; it is not played as an
    extra silence. Speed is sampled again after each yielded output block.
    """
    from audiotsm import wsola
    from audiotsm.io.array import ArrayReader, FixedArrayWriter
    frame, hop = 1024, 512
    processor = wsola(1, frame_length=frame, synthesis_hop=hop, tolerance=256)
    reader = ArrayReader(np.pad(samples, (0, frame * 4)).reshape(1, -1))
    position = 0.0
    while position < len(samples):
        requested = float(get_speed())
        speed = int(hop * max(.5, min(2, requested))) / hop
        processor.set_speed(speed)
        output = np.empty((1, hop), dtype=np.float32)
        writer = FixedArrayWriter(output)
        processor.read_from(reader)
        count, _ = processor.write_to(writer)
        if not count:
            if reader.empty:
                raise ValueError('The audio tempo processor ran out of speech unexpectedly.')
            continue
        count = min(count, math.ceil((len(samples) - position) / speed))
        finish = min(float(len(samples)), position + count * speed)
        yield output[0, :count], position, finish
        position = finish
