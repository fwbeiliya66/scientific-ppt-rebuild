import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('pwsh') or shutil.which('powershell')


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((REPO / 'install.py').is_file(), 'The Python installer is required')
        spec = importlib.util.spec_from_file_location('skill_installer', REPO / 'install.py')
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        self.target = self.root / 'target with spaces' / '\u793a\u4f8b'
        self.files = {
            'SKILL.md': b'# Synthetic skill\n',
            'runtime/main.py': b"print('synthetic')\n",
            'runtime/LICENSE': b'Synthetic license\n',
            'runtime/NOTICE': b'Synthetic notice\n',
            'scripts/check.ps1': b"Write-Output 'synthetic'\n",
            'agents/openai.yaml': b'name: synthetic\n',
            'references/schema.yml': b'version: 1\n',
            'references/readme.md': b'Synthetic instructions\n',
            'requirements.txt': b'example-package>=1\n',
        }
        for relative, content in self.files.items():
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def test_copy_preserves_reusable_source_bytes_and_excludes_local_data(self):
        excluded = [
            '__pycache__/cached.py', '.venv/local.py', '.git/hook.py',
            'generated/page.md', 'runs/page.py', 'run/page.txt', 'output/report.md',
            'outputs/report.txt', 'work/scratch.py', 'config/local.yaml',
            'input/notes.txt', 'inputs/source.md', 'data/measurements.txt',
            'artifacts/render.md', 'tmp/job.py', 'temp/job.txt',
            'runtime/config.yaml', 'runtime/config.yml', 'runtime/config.local.yaml',
            'local_config.yml', 'credentials.txt',
            '.env', 'auth.json', 'input.pptx', 'preview.png', 'font.ttf', 'python.exe',
        ]
        for relative in excluded:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'Synthetic excluded data')
        target, backup = self.installer.install_core(self.source, self.target)
        self.assertEqual(target, self.target.resolve())
        self.assertIsNone(backup)
        copied = {path.relative_to(target).as_posix() for path in target.rglob('*') if path.is_file()}
        self.assertEqual(copied, set(self.files))
        for relative, content in self.files.items():
            self.assertEqual((target / relative).read_bytes(), content)
            self.assertEqual((self.source / relative).read_bytes(), content)

    def test_repeat_install_refuses_existing_target_without_changes(self):
        self.installer.install_core(self.source, self.target)
        (self.target / 'personal.txt').write_bytes(b'Synthetic user change')
        with self.assertRaises(FileExistsError):
            self.installer.install_core(self.source, self.target)
        self.assertEqual((self.target / 'personal.txt').read_bytes(), b'Synthetic user change')
        self.assertEqual(list(self.target.parent.glob(self.target.name + '.backup-*')), [])

    def test_replace_preserves_existing_install_as_timestamp_sibling(self):
        self.installer.install_core(self.source, self.target)
        (self.target / 'personal.txt').write_bytes(b'Synthetic prior install')
        (self.source / 'SKILL.md').write_bytes(b'# Synthetic new version\n')
        target, backup = self.installer.install_core(self.source, self.target, replace=True)
        self.assertEqual(backup.parent, target.parent)
        self.assertRegex(backup.name, '^' + target.name + r'\.backup-\d{8}T\d{12}Z$')
        self.assertEqual((backup / 'personal.txt').read_bytes(), b'Synthetic prior install')
        self.assertEqual((backup / 'SKILL.md').read_bytes(), self.files['SKILL.md'])
        self.assertEqual((target / 'SKILL.md').read_bytes(), b'# Synthetic new version\n')
        self.assertFalse((target / 'personal.txt').exists())

    def test_source_overlap_and_filesystem_root_are_rejected_before_mutation(self):
        for target in (self.source, self.source / 'child', self.source.parent, Path(self.source.anchor)):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.installer.install_core(self.source, target, replace=True)
        self.assertEqual((self.source / 'SKILL.md').read_bytes(), self.files['SKILL.md'])

    def test_copy_failure_keeps_existing_install_and_cleans_only_its_stage(self):
        self.target.mkdir(parents=True)
        (self.target / 'personal.txt').write_bytes(b'Synthetic prior install')
        before = set(self.target.parent.iterdir())
        with mock.patch.object(self.installer.shutil, 'copytree', side_effect=OSError('Synthetic copy failure')):
            with self.assertRaises(OSError):
                self.installer.install_core(self.source, self.target, replace=True)
        self.assertEqual((self.target / 'personal.txt').read_bytes(), b'Synthetic prior install')
        self.assertEqual(set(self.target.parent.iterdir()), before)

    def test_publish_failure_restores_existing_install(self):
        self.target.mkdir(parents=True)
        (self.target / 'personal.txt').write_bytes(b'Synthetic prior install')
        real_rename = Path.rename

        def fail_staged_publish(path, destination):
            if Path(destination) == self.target and path.parent != self.target.parent:
                raise OSError('Synthetic publish failure')
            return real_rename(path, destination)

        with mock.patch.object(Path, 'rename', new=fail_staged_publish):
            with self.assertRaises(OSError):
                self.installer.install_core(self.source, self.target, replace=True)
        self.assertEqual((self.target / 'personal.txt').read_bytes(), b'Synthetic prior install')
        self.assertEqual(list(self.target.parent.glob(self.target.name + '.backup-*')), [])

    def test_symlink_target_cannot_redirect_replace(self):
        other = self.root / 'other'
        other.mkdir()
        link = self.root / 'alias'
        try:
            link.symlink_to(other, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks requires platform permission')
        with self.assertRaises(ValueError):
            self.installer.install_core(self.source, link, replace=True)
        self.assertTrue(link.is_symlink())
        self.assertTrue(other.is_dir())

    def test_default_target_uses_codex_home_or_user_home(self):
        with mock.patch.dict(os.environ, {'CODEX_HOME': str(self.root / 'codex home')}):
            self.assertEqual(self.installer.default_target(),
                             self.root / 'codex home/skills/scientific-ppt-rebuild')
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(Path, 'home', return_value=self.root):
            self.assertEqual(self.installer.default_target(), self.root / '.codex/skills/scientific-ppt-rebuild')

    def test_cli_installs_actual_core_under_temporary_codex_home(self):
        environment = dict(os.environ, CODEX_HOME=str(self.root / 'codex home \u793a\u4f8b'))
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(REPO / 'install.py')],
                                capture_output=True, text=True, encoding='utf-8', env=environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installed = self.root / 'codex home \u793a\u4f8b/skills/scientific-ppt-rebuild'
        for relative in ('SKILL.md', 'runtime/main.py', 'runtime/LICENSE', 'runtime/NOTICE',
                         'agents/openai.yaml', 'requirements.txt'):
            self.assertEqual((installed / relative).read_bytes(),
                             (REPO / 'skills/scientific-ppt-rebuild' / relative).read_bytes())
        self.assertIn(str(Path(sys.executable)), result.stdout)
        self.assertIn(str(installed / 'runtime/main.py'), result.stdout)
        self.assertFalse((installed / '.venv').exists())

    def test_dependency_commands_use_only_final_target_venv(self):
        output = io.StringIO()
        with mock.patch.object(self.installer, 'SOURCE', self.source), \
                mock.patch.object(self.installer.subprocess, 'run') as run, contextlib.redirect_stdout(output):
            code = self.installer.main(['--target', str(self.target), '--install-deps'])
        self.assertEqual(code, 0)
        python = self.target / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        self.assertEqual(run.call_args_list, [
            mock.call([sys.executable, '-m', 'venv', str(self.target / '.venv')], check=True),
            mock.call([str(python), '-m', 'pip', 'install', '-r', str(self.target / 'requirements.txt')], check=True),
        ])
        self.assertEqual((self.target / 'requirements.txt').read_bytes(), self.files['requirements.txt'])
        self.assertIn(str(python), output.getvalue())

    def test_dependency_failure_reports_repair_and_preserves_core_and_backup(self):
        self.target.mkdir(parents=True)
        (self.target / 'personal.txt').write_bytes(b'Synthetic prior install')
        output, error = io.StringIO(), io.StringIO()
        with mock.patch.object(self.installer, 'SOURCE', self.source), \
                mock.patch.object(self.installer.subprocess, 'run', side_effect=[
                    None, subprocess.CalledProcessError(1, ['synthetic-pip'])]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = self.installer.main(['--target', str(self.target), '--replace', '--install-deps'])
        self.assertEqual(code, 1)
        self.assertEqual((self.target / 'SKILL.md').read_bytes(), self.files['SKILL.md'])
        backups = list(self.target.parent.glob(self.target.name + '.backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'personal.txt').read_bytes(), b'Synthetic prior install')
        self.assertIn('Dependency setup failed', error.getvalue())
        self.assertIn(str(self.target / '.venv'), error.getvalue())
        self.assertIn(str(self.target / 'requirements.txt'), error.getvalue())
        self.assertIn('pip', error.getvalue())
        self.assertNotIn('Runtime Python:', output.getvalue())

    def test_python_below_311_is_rejected_without_installing(self):
        with mock.patch.object(self.installer.sys, 'version_info', (3, 10, 0)), \
                contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit) as raised:
            self.installer.main(['--target', str(self.target)])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn('Python 3.11', error.getvalue())
        self.assertFalse(self.target.exists())


@unittest.skipUnless(POWERSHELL, 'PowerShell is required for wrapper checks')
class WindowsWrapperTests(unittest.TestCase):
    def test_wrapper_forwards_target_replace_and_default_dependencies(self):
        self.run_wrapper(skip_dependencies=False)

    def test_wrapper_supports_offline_skip_dependencies(self):
        self.run_wrapper(skip_dependencies=True)

    def run_wrapper(self, skip_dependencies):
        self.assertTrue((REPO / 'Install.ps1').is_file(), 'The PowerShell installer wrapper is required')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            wrapper = root / 'Install.ps1'
            shutil.copyfile(REPO / 'Install.ps1', wrapper)
            (root / 'install.py').write_text(
                'import json, os, sys\nfrom pathlib import Path\n'
                'Path(os.environ["INSTALLER_TEST_RECORD"]).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")\n',
                encoding='utf-8')
            harness = root / 'harness.ps1'
            harness.write_text(r'''
param([string]$Wrapper, [string]$Target, [string]$Skip)
function Reject-OldPython { $global:LASTEXITCODE = 1 }
function Get-Command {
    [CmdletBinding()]
    param([string]$Name, [string]$CommandType)
    if ($Name -eq 'py') { [pscustomobject]@{ Source = 'Reject-OldPython' } }
    if ($Name -eq 'python') { [pscustomobject]@{ Source = $env:INSTALLER_TEST_PYTHON } }
}
$parameters = @{ Target = $Target; Replace = $true }
if ($Skip -eq 'yes') { $parameters.SkipDependencies = $true }
& $Wrapper @parameters
''', encoding='utf-8')
            record = root / 'arguments.json'
            target = root / 'spaced target' / '\u793a\u4f8b'
            environment = dict(os.environ, INSTALLER_TEST_RECORD=str(record), INSTALLER_TEST_PYTHON=sys.executable)
            result = subprocess.run(
                [POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                 '-File', str(harness), str(wrapper), str(target), 'yes' if skip_dependencies else 'no'],
                capture_output=True, text=True, encoding='utf-8', env=environment)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            arguments = json.loads(record.read_text(encoding='utf-8'))
            self.assertEqual(arguments[:2], ['--target', str(target)])
            self.assertIn('--replace', arguments)
            self.assertEqual('--install-deps' in arguments, not skip_dependencies)


if __name__ == '__main__':
    unittest.main()
