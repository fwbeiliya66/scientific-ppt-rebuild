#!/usr/bin/env python3
"""Copy the reusable skill and optionally install dependencies in its own venv."""
import argparse
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SKILL_NAME = 'scientific-ppt-rebuild'
SOURCE = Path(__file__).resolve().parent / 'skills' / SKILL_NAME
SOURCE_SUFFIXES = {'.py', '.ps1', '.md', '.yaml', '.yml', '.txt'}
EXCLUDED_DIRS = {
    '__pycache__', '.venv', '.git', 'config', 'configs', 'generated',
    'run', 'runs', 'jobs', 'output', 'outputs', 'work', 'input', 'inputs',
    'data', 'artifacts', 'temp', 'tmp',
}
PRIVATE_DATA_STEMS = {'config', 'auth', 'credentials', 'secrets', 'token', 'tokens'}


def default_target():
    codex_home = Path(os.environ['CODEX_HOME']).expanduser() if os.environ.get('CODEX_HOME') else Path.home() / '.codex'
    return codex_home / 'skills' / SKILL_NAME


def is_alias(path):
    return path.is_symlink() or (path.exists() and
        bool(getattr(path.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def ignore_local_data(directory, names):
    ignored = []
    for name in names:
        path = Path(directory) / name
        if name.startswith('.') or is_alias(path) or (path.is_dir() and name.lower() in EXCLUDED_DIRS):
            ignored.append(name)
        elif path.is_file() and (
            (path.suffix.lower() not in SOURCE_SUFFIXES and name not in {'LICENSE', 'NOTICE'}) or
            (path.suffix.lower() in {'.yaml', '.yml', '.txt'} and
             PRIVATE_DATA_STEMS.intersection(path.stem.lower().replace('_', '.').replace('-', '.').split('.')))
        ):
            ignored.append(name)
    return ignored


def install_core(source, target, replace=False):
    source = Path(source).resolve()
    supplied_target = Path(target).expanduser()
    if is_alias(supplied_target):
        raise ValueError('Target must not be a symbolic link or junction.')
    target = supplied_target.resolve()
    if target == target.parent or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Target must be separate from the source tree and cannot be a filesystem root.')
    if not source.is_dir() or not (source / 'SKILL.md').is_file():
        raise FileNotFoundError(f'Core skill source is missing: {source}')
    if target.exists() and not replace:
        raise FileExistsError(f'Target already exists: {target}. Use --replace to preserve it as a backup.')
    if target.exists() and not target.is_dir():
        raise NotADirectoryError(f'Target is not a directory: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    # TemporaryDirectory cleans only this installer-created staging directory.
    with tempfile.TemporaryDirectory(prefix=f'.{target.name}.stage-', dir=target.parent) as temporary:
        stage = Path(temporary) / 'skill'
        shutil.copytree(source, stage, ignore=ignore_local_data)
        if target.exists():
            if not replace:
                raise FileExistsError(f'Target appeared during copying: {target}')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            backup = target.with_name(f'{target.name}.backup-{stamp}')
            if backup.exists():
                raise FileExistsError(f'Backup already exists: {backup}')
            target.rename(backup)
        try:
            stage.rename(target)
        except OSError:
            if backup is not None and not target.exists():
                backup.rename(target)
            raise
    return target, backup


def dependency_commands(target):
    venv = target / '.venv'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    return [
        [sys.executable, '-m', 'venv', str(venv)],
        [str(python), '-m', 'pip', 'install', '-r', str(target / 'requirements.txt')],
    ]


def command_text(parts):
    if os.name == 'nt':
        return '& ' + ' '.join("'" + str(part).replace("'", "''") + "'" for part in parts)
    return shlex.join(str(part) for part in parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=default_target(),
                        help='Exact final skill directory (default: CODEX_HOME/skills/scientific-ppt-rebuild or ~/.codex/skills/scientific-ppt-rebuild).')
    parser.add_argument('--replace', action='store_true', help='Preserve an existing target as a timestamped sibling backup.')
    parser.add_argument('--install-deps', action='store_true', help='Create target/.venv and install requirements there; requires network/package access.')
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error('Python 3.11 or newer is required.')
    try:
        target, backup = install_core(SOURCE, args.target, args.replace)
    except (OSError, ValueError) as error:
        print(f'Installation failed: {error}', file=sys.stderr)
        return 1
    print(f'Core copied to: {target}')
    if backup is not None:
        print(f'Previous installation preserved at: {backup}')
    python = Path(sys.executable)
    if args.install_deps:
        commands = dependency_commands(target)
        try:
            for command in commands:
                subprocess.run(command, check=True)
        except (OSError, subprocess.CalledProcessError) as error:
            print(f'Dependency setup failed: {error}\nCore remains at {target}; any previous backup is preserved.', file=sys.stderr)
            print('Repair dependency setup with:', file=sys.stderr)
            for command in commands:
                print(command_text(command), file=sys.stderr)
            return 1
        python = Path(commands[1][0])
    else:
        print('Dependencies were skipped; the runtime needs the packages in requirements.txt.')
    print(f'Runtime Python: {python}')
    print(command_text([python, target / 'runtime' / 'main.py', '--help']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
