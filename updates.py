"""Official GitHub previews, verified downloads, and side-by-side Windows updates.

Old application files are never overwritten. A small local pointer lets existing
shortcuts open the newest installed version, while --skip-update permits recovery.
"""
import hashlib
import json
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = 'shamendra654321-byte/quiet-pages'
API = f'https://api.github.com/repos/{REPOSITORY}/releases?per_page=30'
ASSET = 'QuietPages-Windows-x64.zip'
MAX_DOWNLOAD = 300 * 1024 * 1024
MAX_EXTRACTED = 1500 * 1024 * 1024


def version_key(tag):
    match = re.fullmatch(r'preview-(\d+)-(\d+)', tag)
    return tuple(map(int, match.groups())) if match else (0, 0)


def find_update(releases, current):
    candidates = []
    for release in releases:
        tag = release.get('tag_name', '')
        if release.get('draft') or version_key(tag) <= version_key(current):
            continue
        for asset in release.get('assets', []):
            expected_url = f'https://github.com/{REPOSITORY}/releases/download/{tag}/{ASSET}'
            digest = asset.get('digest') or ''
            if (asset.get('name') == ASSET and asset.get('browser_download_url') == expected_url
                    and re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest)
                    and isinstance(asset.get('size'), int) and 0 < asset['size'] <= MAX_DOWNLOAD):
                candidates.append(dict(tag=tag, name=release.get('name') or tag,
                                       notes=(release.get('body') or '')[:12000],
                                       url=expected_url, digest=digest[7:].lower(), size=asset['size']))
                break
    return max(candidates, key=lambda item: version_key(item['tag']), default=None)


def check_update(current):
    request = urllib.request.Request(API, headers={'User-Agent': 'QuietPages-Updater',
                                                  'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('The update response was too large. Please try again later.')
    releases = json.loads(raw)
    if not isinstance(releases, list):
        raise ValueError('Could not read the update list. Please try again later.')
    return find_update(releases, current)


def extract_verified(archive, destination):
    """Validate every path before extracting, including Windows-specific hazards."""
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > 20000 or sum(item.file_size for item in entries) > MAX_EXTRACTED:
            raise ValueError('The update archive is too large.')
        if not any(item.filename == 'QuietPages/QuietPages.exe' and item.file_size > 0 for item in entries):
            raise ValueError('The update is missing QuietPages.exe.')
        seen = set()
        for item in entries:
            path = PurePosixPath(item.filename)
            parts = path.parts
            if (not parts or parts[0] != 'QuietPages' or '\\' in item.orig_filename or '\x00' in item.orig_filename
                    or any(part in ('.', '..') or ':' in part or part.endswith((' ', '.'))
                           or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', part)
                           for part in parts)
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('The update contains an unsafe file path.')
            target = destination.joinpath(*parts).resolve()
            if not target.is_relative_to(destination) or str(target).lower() in seen:
                raise ValueError('The update contains conflicting file paths.')
            seen.add(str(target).lower())
        for item in entries:
            target = destination.joinpath(*PurePosixPath(item.filename).parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as reader, target.open('xb') as writer:
                    shutil.copyfileobj(reader, writer)
    executable = destination / 'QuietPages' / 'QuietPages.exe'
    if not executable.is_file() or executable.stat().st_size == 0:
        raise ValueError('The update is missing QuietPages.exe.')
    return executable


def file_digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def install_update(release, data, cancel, progress):
    updates = Path(data) / 'updates'
    updates.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=release['tag'] + '-', dir=updates))
    archive = folder / 'download.zip'
    try:
        request = urllib.request.Request(release['url'], headers={'User-Agent': 'QuietPages-Updater'})
        digest = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(request, timeout=30) as response, archive.open('xb') as output:
            while True:
                if cancel.is_set():
                    raise InterruptedError()
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                count += len(chunk)
                if count > release['size'] or count > MAX_DOWNLOAD:
                    raise ValueError('The update download was larger than expected.')
                digest.update(chunk)
                output.write(chunk)
                progress(f'Downloading update: {count * 100 // release["size"]}%')
        if count != release['size'] or digest.hexdigest() != release['digest']:
            raise ValueError('The update did not pass its download check. Your current app is unchanged. Please retry.')
        if cancel.is_set():
            raise InterruptedError()
        progress('Checking and unpacking update…')
        executable = extract_verified(archive, folder)
        archive.unlink()
        return {'tag': release['tag'], 'folder': folder.name, 'sha256': file_digest(executable)}
    except BaseException:
        # Only this newly-created temporary directory belongs to this operation.
        shutil.rmtree(folder, ignore_errors=True)
        raise


def installed_executable(data, installation):
    folder = installation.get('folder', '')
    if not folder or Path(folder).name != folder or '/' in folder or '\\' in folder or ':' in folder:
        raise ValueError('Invalid update location.')
    base = (Path(data) / 'updates').resolve()
    executable = (base / folder / 'QuietPages' / 'QuietPages.exe').resolve()
    if not executable.is_relative_to(base) or file_digest(executable) != installation.get('sha256'):
        raise ValueError('The installed update failed its file check.')
    return executable


def activate_update(data, installation):
    executable = installed_executable(data, installation)
    pointer = Path(data) / 'current-version.json'
    temporary = pointer.with_suffix('.tmp')
    # Write the pointer before launching; restore it if Windows cannot launch.
    previous = pointer.read_bytes() if pointer.exists() else None
    temporary.write_text(json.dumps(installation), encoding='utf-8')
    temporary.replace(pointer)
    try:
        subprocess.Popen([str(executable), '--updated-start'], cwd=str(executable.parent))
    except OSError:
        if previous is None:
            pointer.unlink(missing_ok=True)
        else:
            temporary.write_bytes(previous)
            temporary.replace(pointer)
        raise


def redirect_to_installed(data, current):
    try:
        installation = json.loads((Path(data) / 'current-version.json').read_text(encoding='utf-8'))
        if version_key(installation['tag']) <= version_key(current):
            return False
        executable = installed_executable(data, installation)
        subprocess.Popen([str(executable), '--updated-start'], cwd=str(executable.parent))
        return True
    except (OSError, ValueError, KeyError, TypeError):
        # A broken update must never prevent the original application opening.
        return False
