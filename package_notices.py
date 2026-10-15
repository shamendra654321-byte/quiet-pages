"""Preserve installed third-party notices and the application's source."""
from importlib.metadata import distributions
from pathlib import Path
import shutil

destination = Path('dist/QuietPages')
notices = destination / 'licenses'
for dist in distributions():
    name = dist.metadata.get('Name', 'unknown')
    for file in dist.files or []:
        if any(word in str(file).lower() for word in ('license', 'copying', 'notice')) and '.dist-info' in str(file):
            source = Path(dist.locate_file(file))
            if source.is_file():
                target = notices / name / Path(str(file)).name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
for name in ('README.md', 'THIRD_PARTY.md', 'LICENSE', 'COPYING', 'VALIDATION.md'):
    shutil.copy2(name, destination / name)
source_dir = destination / 'source'
source_dir.mkdir(exist_ok=True)
for pattern in ('*.py', '*.ps1', 'requirements.txt'):
    for source in Path('.').glob(pattern):
        shutil.copy2(source, source_dir / source.name)
