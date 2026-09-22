"""Install native skills without editing either provider's global configuration."""
from __future__ import annotations

import json
import sys
from importlib.resources import files
from pathlib import Path
from datetime import datetime, timezone

from . import __version__
from .schema import CouncilError
from .store import atomic_text


def install(target: str, project: Path | None = None, force: bool = False,
            home: Path | None = None) -> list[Path]:
    if target not in {'codex', 'claude', 'both'}:
        raise CouncilError('Unknown installation target')
    base = (project or home or Path.home()).expanduser().resolve()
    names = ['codex', 'claude'] if target == 'both' else [target]
    roots = [base / ('.agents' if name == 'codex' else '.claude') / 'skills' / 'council' for name in names]
    payload = {'SKILL.md': files('council').joinpath('skill.md').read_text(encoding='utf-8'),
               'protocol.md': files('council').joinpath('protocol.md').read_text(encoding='utf-8'),
               'runtime.json': json.dumps({'python': str(Path(sys.executable).resolve()), 'package': 'mani-council',
                                          'version': __version__}, indent=2) + '\n'}
    # Validate the entire installation plan before changing any existing files.
    for root in roots:
        if root.exists() and not root.is_dir():
            raise CouncilError(f'Installation destination is not a directory: {root}')
        for name, content in payload.items():
            path = root / name
            if path.exists() and (not path.is_file() or (path.read_text(encoding='utf-8') != content and not force)):
                raise CouncilError(f'Existing skill differs: {path}. Inspect it, then use --force to back up and replace Council-owned files.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        for name, content in payload.items():
            path = root / name
            if path.exists() and path.read_text(encoding='utf-8') != content:
                atomic_text(root / f'{name}.backup-{stamp}', path.read_text(encoding='utf-8'))
            atomic_text(path, content)
    return roots
