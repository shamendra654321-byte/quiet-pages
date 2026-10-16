import queue
import threading
import unittest
import numpy as np
from live_tempo import TempoControl, tempo_blocks
from chapter_audio import read_book


class LiveTempoTests(unittest.TestCase):
    def tone(self, seconds=2):
        return np.sin(2 * np.pi * 440 * np.arange(int(24000 * seconds)) / 24000).astype(np.float32)

    def test_pitch_duration_and_tail_at_each_speed(self):
        samples = self.tone()
        for speed in (.5, 1, 1.5, 2):
            blocks = list(tempo_blocks(samples, lambda: speed))
            result = np.concatenate([b[0] for b in blocks])
            self.assertAlmostEqual(len(result), len(samples) / speed, delta=2)
            spectrum = np.abs(np.fft.rfft(result[2400:-2400]))
            pitch = np.argmax(spectrum) * 24000 / len(result[2400:-2400])
            self.assertAlmostEqual(pitch, 440, delta=3)
            self.assertGreater(np.max(np.abs(result[-256:])), .5)
            self.assertEqual(blocks[0][1], 0)
            self.assertEqual(blocks[-1][2], len(samples))

    def test_live_change_affects_next_block_without_resetting_source(self):
        control = TempoControl()
        blocks = tempo_blocks(self.tone(), control.get)
        previous = next(blocks)
        for speed in (2, .5, 1.8, 1):
            control.set(speed)
            current = next(blocks)
            self.assertEqual(previous[2], current[1])
            self.assertAlmostEqual((current[2] - current[1]) / len(current[0]), speed, delta=.002)
            previous = current

    def test_single_stream_no_regeneration_during_live_change(self):
        control = TempoControl()
        calls, frames, opens = [], [], []
        samples = self.tone()
        class Engine:
            def create(self, text, **kwargs):
                calls.append(kwargs['speed'])
                return samples, 24000
        class Stream:
            def __init__(self, **kwargs): opens.append(kwargs['samplerate'])
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def write(self, data):
                frames.append(len(data))
                if len(frames) == 5:
                    control.set(2)
        events = queue.Queue()
        read_book(Engine(), ['Hello'], 0, 1, [0], 'af_heart', 1,
                  threading.Event(), threading.Event(), events, Stream, live_speed=control.get)
        self.assertEqual(opens, [24000])
        self.assertEqual(calls, [1])
        self.assertEqual(sum(frames), 5 * 512 + (len(samples) - 5 * 512) // 2)
        cursors = [v[2][1] for k, v in list(events.queue) if k == 'at' and v[1] == 'cursor']
        self.assertEqual(cursors, sorted(cursors))

    def test_invalid_speed_keeps_last_valid_value(self):
        control = TempoControl(1.5)
        for invalid in ('', '.', 'abc', float('nan'), float('inf'), .1, 10):
            self.assertFalse(control.set(invalid))
            self.assertEqual(control.get(), 1.5)
