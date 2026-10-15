import hashlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import updates


def archive_bytes(entries=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, content in (entries or {'QuietPages/QuietPages.exe': b'test-executable',
                                          'QuietPages/_internal/library.dll': b'library'}).items():
            archive.writestr(name, content)
    return stream.getvalue()


def release(data, tag='preview-5-1'):
    return {'tag': tag, 'url': 'https://example.invalid/test', 'size': len(data),
            'digest': hashlib.sha256(data).hexdigest()}


class UpdateTests(unittest.TestCase):
    def test_numeric_versions_and_official_asset_only(self):
        def item(tag, **overrides):
            asset = {'name': updates.ASSET, 'size': 10, 'digest': 'sha256:' + 'a' * 64,
                     'browser_download_url': f'https://github.com/{updates.REPOSITORY}/releases/download/{tag}/{updates.ASSET}'}
            asset.update(overrides)
            return {'tag_name': tag, 'prerelease': True, 'assets': [asset]}
        releases = [item('preview-9-1'), item('preview-10-1'), item('preview-11-1', browser_download_url='https://evil.invalid/update.zip'), item('preview-12-1', digest=None)]
        self.assertEqual(updates.find_update(releases, 'preview-9-1')['tag'], 'preview-10-1')
        self.assertIsNone(updates.find_update(releases, 'preview-10-1'))
        self.assertGreater(updates.version_key('preview-4-2'), updates.version_key('preview-4-1'))

    def test_download_install_and_existing_shortcut_redirect(self):
        data = archive_bytes()
        with tempfile.TemporaryDirectory() as folder:
            with patch('updates.urllib.request.urlopen', return_value=io.BytesIO(data)):
                installed = updates.install_update(release(data), folder, threading.Event(), lambda text: None)
            executable = updates.installed_executable(folder, installed)
            self.assertEqual(executable.read_bytes(), b'test-executable')
            with patch('updates.subprocess.Popen') as launch:
                updates.activate_update(folder, installed)
                self.assertTrue(updates.redirect_to_installed(folder, 'preview-4-1'))
                self.assertEqual(launch.call_count, 2)
                self.assertFalse(updates.redirect_to_installed(folder, 'preview-5-1'))
            executable.write_bytes(b'changed')
            with patch('updates.subprocess.Popen') as launch:
                self.assertFalse(updates.redirect_to_installed(folder, 'preview-4-1'))
                launch.assert_not_called()

    def test_failed_launch_restores_previous_pointer(self):
        data = archive_bytes()
        with tempfile.TemporaryDirectory() as folder:
            pointer = Path(folder) / 'current-version.json'
            pointer.write_text('{"old": true}')
            with patch('updates.urllib.request.urlopen', return_value=io.BytesIO(data)):
                installed = updates.install_update(release(data), folder, threading.Event(), lambda text: None)
            with patch('updates.subprocess.Popen', side_effect=OSError('test failure')):
                with self.assertRaises(OSError):
                    updates.activate_update(folder, installed)
            self.assertEqual(json.loads(pointer.read_text()), {'old': True})

    def test_bad_digest_truncated_and_cancelled_downloads_clean_up(self):
        data = archive_bytes()
        for received, cancel in ((b'bad', False), (b'x' * len(data), False), (data, True)):
            with self.subTest(cancel=cancel, size=len(received)), tempfile.TemporaryDirectory() as folder:
                event = threading.Event()
                if cancel:
                    event.set()
                with patch('updates.urllib.request.urlopen', return_value=io.BytesIO(received)):
                    with self.assertRaises((ValueError, InterruptedError)):
                        updates.install_update(release(data), folder, event, lambda text: None)
                self.assertEqual(list((Path(folder) / 'updates').iterdir()), [])
                self.assertFalse((Path(folder) / 'current-version.json').exists())

    def test_reject_unsafe_windows_archive_paths(self):
        for name in ('../escape', '/absolute', 'QuietPages/../../escape', 'QuietPages/C:evil',
                     'QuietPages\\escape', 'QuietPages/NUL.txt', 'QuietPages/file.', 'Other/app.exe'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    data = archive_bytes({'QuietPages/QuietPages.exe': b'app', name: b'bad'})
                    # zipfile normalizes Windows separators when creating an archive.
                    if '\\' in name:
                        data = data.replace(name.replace('\\', '/').encode(), name.encode())
                    updates.extract_verified(io.BytesIO(data), folder)
                self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
