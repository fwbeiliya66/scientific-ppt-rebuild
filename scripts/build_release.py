#!/usr/bin/env python3
"""Build verified, deterministic source and installable-skill ZIPs."""
import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

from check_release import ROOT, SKILL, check_repo, public_files


def write_zip(destination, files):
    entries = sorted(((Path(source), PurePosixPath(member)) for source, member in files),
                     key=lambda entry: str(entry[1]))
    for source, member in entries:
        if (member.is_absolute() or '..' in member.parts or '\\' in str(member)
                or ':' in str(member) or '\x00' in str(member) or str(member) == '.'):
            raise ValueError(f'Unsafe ZIP member: {member}')
    if Path(destination).exists():
        raise FileExistsError(f'Refusing to overwrite release archive: {destination}')
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, member in entries:
            info = zipfile.ZipInfo(str(member), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist', help='New/empty archive output directory.')
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise SystemExit('Archive output directory must be new or empty; existing files are preserved.')
    errors = check_repo()
    if errors:
        raise SystemExit('Release checks failed:\n' + '\n'.join(errors))
    version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise SystemExit('VERSION must be a semantic release number.')
    output.mkdir(parents=True, exist_ok=True)
    files = public_files()
    stem = f'scientific-ppt-rebuild-v{version}'
    source_zip, skill_zip = output / f'{stem}-source.zip', output / f'{stem}-skill.zip'
    write_zip(source_zip, [(path, f'scientific-ppt-rebuild/{path.relative_to(ROOT).as_posix()}') for path in files])
    write_zip(skill_zip, [(path, f'scientific-ppt-rebuild/{path.relative_to(ROOT / SKILL).as_posix()}')
                         for path in files if path.is_relative_to(ROOT / SKILL)])
    sums = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in (source_zip, skill_zip))
    (output / 'SHA256SUMS.txt').write_text(sums, encoding='ascii')
    print(sums, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
