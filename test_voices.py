import hashlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import test_playback
from voice_catalog import BY_ID, label
from voice_store import VoiceStore


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = VoiceStore(self.temp.name)
        self.cancel = threading.Event()
        data = io.BytesIO()
        np.save(data, np.ones((510, 1, 256), dtype=np.float32), allow_pickle=False)
        self.data = data.getvalue()
        self.digest = hashlib.sha256(self.data).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def response(self, url, **kwargs):
        response = io.BytesIO(b'model' if url.endswith('.onnx') else self.data)
        response.headers = {'Content-Length': str(len(response.getvalue()))}
        return response

    def test_individual_then_all_reuses_model_and_completed_voices(self):
        with patch.dict(BY_ID['af_heart'], sha256=self.digest), patch.dict(BY_ID['af_bella'], sha256=self.digest), patch('voice_store.urllib.request.urlopen', side_effect=self.response) as network:
            self.store.ensure(['af_heart'], self.cancel, lambda x: None)
            self.assertEqual(network.call_count, 2)
            self.assertFalse(self.store.path('af_bella').exists())
            self.store.ensure(['af_heart', 'af_bella'], self.cancel, lambda x: None)
            self.assertEqual(network.call_count, 3)
            network.side_effect = AssertionError('Offline replay must not download')
            self.store.ensure(['af_heart', 'af_bella'], self.cancel, lambda x: None)

    def test_bad_digest_and_cancel_do_not_leave_installed_or_partial_files(self):
        target = self.store.path('af_heart')
        with patch('voice_store.urllib.request.urlopen', side_effect=self.response):
            with self.assertRaises(ValueError):
                self.store.download('https://example.test/voice.npy', target, self.cancel, lambda x: None, '0' * 64)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix('.download').exists())
            self.cancel.set()
            with self.assertRaises(InterruptedError):
                self.store.download('https://example.test/voice.npy', target, self.cancel, lambda x: None, self.digest)
            self.assertFalse(target.exists())

    def test_legacy_pack_reused_without_network(self):
        with (self.store.folder / 'voices-v1.0.bin').open('wb') as f:
            np.savez(f, af_heart=np.ones((510, 1, 256), dtype=np.float32))
        (self.store.folder / 'kokoro-v1.0.onnx').write_bytes(b'model')
        with patch.dict(BY_ID['af_heart'], sha256=self.digest), patch('voice_store.urllib.request.urlopen', side_effect=AssertionError('Unnecessary download')):
            self.store.ensure(['af_heart'], self.cancel, lambda x: None)
            self.assertTrue(self.store.path('af_heart').exists())


class VoiceBrowserTests(unittest.TestCase):
    setUp = test_playback.PlaybackTests.setUp
    tearDown = test_playback.PlaybackTests.tearDown

    def test_favourite_filter_and_persistence(self):
        r = self.reader
        r.show_voices()
        self.assertEqual(len(r.voice_table.get_children()), 28)
        r.voice_table.selection_set('af_aoede')
        r.voice_action('favourite')
        self.assertIn(label(BY_ID['af_aoede']), r.voice['values'])
        import app
        self.assertIn('af_aoede', json.loads((app.DATA / 'preferences.json').read_text())['favourite_voices'])
        r.voice_filter.set('Favourites')
        r.refresh_voice_browser()
        self.assertEqual(len(r.voice_table.get_children()), 10)
        r.voice_table.selection_set('af_aoede')
        r.voice_action('favourite')
        self.assertEqual(len(r.voice_table.get_children()), 9)

    def test_preview_uses_selected_voice_without_losing_book_position(self):
        r = self.reader
        r.cursor = (0, 2.5)
        r.show_voices()
        r.voice_table.selection_set('am_puck')
        with patch.object(r, 'start') as start:
            r.voice_action('preview')
            start.assert_called_once_with(True)
        self.assertEqual(r.voice.get(), label(BY_ID['am_puck']))
        self.assertEqual(r.cursor, (0, 2.5))

    def test_browser_controls_fit_minimum_window(self):
        r = self.reader
        r.show_voices()
        r.voice_window.geometry('720x520')
        self.root.update()
        for widget in [r.voice_table, r.voice_progress, *r.voice_download_buttons]:
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), r.voice_window.winfo_rooty() + r.voice_window.winfo_height())
