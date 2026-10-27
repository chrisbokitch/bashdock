"""Installation-scoped local signatures, staging and the real recovery transaction."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from bashdock import local_updates as local, update_helper
from bashdock.update_security import verify_signature
from scripts.stage_update import sign
from scripts.update_keys import openssl, modulus


class LocalUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.openssl = openssl()
        except ValueError:
            raise unittest.SkipTest('OpenSSL required for local signing tests')
        cls.keys = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.keys.cleanup)
        cls.private = Path(cls.keys.name) / 'local.pem'
        cls.public_file = Path(cls.keys.name) / 'local.pub'
        subprocess.run([cls.openssl, 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                        'rsa_keygen_bits:3072', '-out', str(cls.private)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([cls.openssl, 'rsa', '-in', str(cls.private), '-pubout', '-out', str(cls.public_file)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.public = dict(algorithm='RSA-PKCS1-SHA256', exponent=65537, modulus=modulus(cls.private))
        publisher_private = Path(cls.keys.name) / 'publisher.pem'
        cls.publisher_file = Path(cls.keys.name) / 'publisher.pub'
        subprocess.run([cls.openssl, 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                        'rsa_keygen_bits:3072', '-out', str(publisher_private)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run([cls.openssl, 'rsa', '-in', str(publisher_private), '-pubout',
                        '-out', str(cls.publisher_file)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.publisher_public = dict(algorithm='RSA-PKCS1-SHA256', exponent=65537,
                                    modulus=modulus(publisher_private))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'updates'
        self.patch = patch.object(local, 'cache_directory', return_value=self.cache)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.target = self.root / 'installed app'
        (self.target / '_internal').mkdir(parents=True)
        (self.target / 'bashdock.exe').write_bytes(b'old executable')
        (self.target / 'BUILD-INFO.json').write_text(json.dumps(dict(version='0.14.0', commit='a' * 40)))
        self.archive = self.root / 'package.zip'
        self.package()

    def package(self, version='0.14.0', commit='b' * 40):
        with zipfile.ZipFile(self.archive, 'w') as bundle:
            bundle.writestr('bashdock/bashdock.exe', b'new executable')
            bundle.writestr('bashdock/bashdock-updater.exe', b'new updater')
            bundle.writestr('bashdock/_internal/runtime.dll', b'runtime')
            bundle.writestr('bashdock/BUILD-INFO.json', json.dumps(dict(version=version, commit=commit)))

    def verify(self, raw, signature, key):
        if sys.platform == 'win32':
            return verify_signature(raw, signature, key)
        # Linux fixtures use OpenSSL with the selected test key. Windows
        # runs the real CNG implementation used by the compiled app/helper.
        if key == self.public:
            public_file = self.public_file
        elif key == self.publisher_public:
            public_file = self.publisher_file
        else:
            raise ValueError('Not a fixture signing key')
        if len(signature) != len(bytes.fromhex(key['modulus'])):
            raise ValueError('Invalid local signature length')
        with tempfile.TemporaryDirectory() as directory:
            message, signed = Path(directory) / 'data', Path(directory) / 'sig'
            message.write_bytes(raw)
            signed.write_bytes(signature)
            result = subprocess.run([self.openssl, 'dgst', '-sha256', '-verify', str(public_file),
                                     '-signature', str(signed), str(message)], capture_output=True)
            if result.returncode:
                raise ValueError('Invalid local signature')

    def stage(self, **kwargs):
        return local.stage_package(self.target, self.archive, self.public,
            lambda raw: sign(raw, self.private), expected_version=kwargs.get('version', '0.14.0'),
            expected_commit=kwargs.get('commit', 'b' * 40), verify=self.verify)

    def plan(self, ready):
        settings, backup = self.root / 'settings.json', self.root / 'before.json'
        settings.write_text('old settings')
        backup.write_text('old settings')
        return dict(install=str(self.target), pending=str(ready.directory), pid=1234,
                    token='a' * 64, settings=str(settings), settings_backup=str(backup),
                    channel=local.CHANNEL)

    def test_stage_registers_only_target_and_leaves_running_installation_untouched(self):
        self.assertIsNone(local.candidate(self.target))
        ready = self.stage()
        self.assertEqual(b'old executable', (self.target / 'bashdock.exe').read_bytes())
        self.assertEqual(ready.directory, local.candidate(self.target))
        found = local.discover_local(self.target, verify=self.verify)
        self.assertEqual('local-development', found.manifest['channel'])
        self.assertEqual('b' * 40, found.manifest['commit'])
        self.assertEqual(local.installation_id(self.target), found.manifest['installation'])
        self.assertIsNone(local.candidate(self.root / 'another installation'))
        self.assertFalse((self.target / 'trusted-key.json').exists())

    def test_tamper_rejected_before_waiting_or_touching_installation(self):
        ready = self.stage()
        plan = self.plan(ready)
        for filename in ('manifest.json', 'manifest.sig', 'package.zip'):
            with self.subTest(filename=filename):
                path = ready.directory / filename
                original = path.read_bytes()
                path.write_bytes(original + b'changed')
                wait = Mock()
                with self.assertRaises((ValueError, OSError)):
                    update_helper.install(plan, None, verify=self.verify, wait=wait)
                wait.assert_not_called()
                self.assertEqual(b'old executable', (self.target / 'bashdock.exe').read_bytes())
                path.write_bytes(original)

    def test_manifest_is_bound_to_the_target_even_when_signed_by_same_developer(self):
        ready = self.stage()
        other = self.root / 'another installation'
        shutil.copytree(self.target, other)
        root = local.inbox_root(other)
        root.mkdir(parents=True)
        (root / 'trusted-key.json').write_text(json.dumps(self.public))
        copy = root / 'pending-copy'
        shutil.copytree(ready.directory, copy)
        with self.assertRaisesRegex(ValueError, 'this installation'):
            local.verify_pending(other, copy, verify=self.verify)
        with self.assertRaisesRegex(ValueError, 'outside'):
            local.verify_pending(other, ready.directory, verify=self.verify)

    def test_public_handoff_never_falls_back_to_registered_local_key(self):
        ready = self.stage()
        plan = self.plan(ready)
        del plan['channel']
        wait = Mock()
        verify = Mock(side_effect=self.verify)
        with self.assertRaisesRegex(ValueError, 'signature'):
            update_helper.install(plan, self.publisher_public, verify=verify, wait=wait)
        verify.assert_called_once()
        self.assertEqual(self.publisher_public, verify.call_args.args[2])
        wait.assert_not_called()
        self.assertEqual(b'old executable', (self.target / 'bashdock.exe').read_bytes())

    def test_local_install_uses_normal_health_check_and_consumes_only_its_pointer(self):
        ready = self.stage()
        plan = self.plan(ready)
        healthy = Mock(return_value=True)
        result = update_helper.install(plan, None, verify=self.verify, wait=Mock(),
            other_processes=lambda target: [], launch=Mock(return_value=Mock()), healthy=healthy)
        self.assertTrue(result['ok'])
        healthy.assert_called_once()
        self.assertEqual(b'new executable', (self.target / 'bashdock.exe').read_bytes())
        self.assertIsNone(local.candidate(self.target))
        self.assertTrue((local.inbox_root(self.target) / 'trusted-key.json').is_file())
        self.assertIsNone(local.discover_local(self.target, ready.directory, verify=self.verify))

    def test_local_startup_failure_restores_application_and_settings(self):
        ready = self.stage()
        plan = self.plan(ready)
        process = Mock()
        process.poll.return_value = None
        def launch(*args):
            Path(plan['settings']).write_text('new settings')
            return process
        with self.assertRaisesRegex(OSError, 'did not start'):
            update_helper.install(plan, None, verify=self.verify, wait=Mock(),
                other_processes=lambda target: [], launch=launch, healthy=lambda *args: False)
        self.assertEqual(b'old executable', (self.target / 'bashdock.exe').read_bytes())
        self.assertEqual('old settings', Path(plan['settings']).read_text())
        self.assertEqual('a' * 40, local.installed_info(self.target)['commit'])
        process.terminate.assert_called_once()

    def test_newer_staging_survives_older_transaction_acknowledgement(self):
        first, second = self.stage(), self.stage()
        local.acknowledge(self.target, first.directory)
        self.assertEqual(second.directory, local.candidate(self.target))

    def test_failed_staging_does_not_publish_partial_data_or_replace_previous_offer(self):
        ready = self.stage()
        signer = Mock(side_effect=OSError('signing failed'))
        with self.assertRaises(OSError):
            local.stage_package(self.target, self.archive, self.public, signer,
                expected_version='0.14.0', expected_commit='b' * 40, verify=self.verify)
        self.assertEqual(ready.directory, local.candidate(self.target))
        self.assertEqual([ready.directory], list(local.inbox_root(self.target).glob('pending-*')))

    def test_different_local_key_cannot_silently_replace_enrollment(self):
        ready = self.stage()
        different = dict(self.public, modulus='f' * 768)
        with self.assertRaisesRegex(ValueError, 'different local key'):
            local.stage_package(self.target, self.archive, different, Mock(),
                expected_version='0.14.0', expected_commit='b' * 40, verify=self.verify)
        self.assertEqual(ready.directory, local.candidate(self.target))

    def test_disable_revokes_ready_package_and_rejects_helper_install(self):
        ready = self.stage()
        plan = self.plan(ready)
        local.disable(self.target)
        self.assertIsNone(local.candidate(self.target))
        wait = Mock()
        with self.assertRaises(OSError):
            update_helper.install(plan, None, verify=self.verify, wait=wait)
        wait.assert_not_called()

    def test_stale_downgrade_and_already_installed_builds_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.stage(commit='c' * 40)
        self.package(version='0.13.0')
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            self.stage(version='0.13.0')
        self.package(commit='a' * 40)
        with self.assertRaisesRegex(ValueError, 'already installed'):
            self.stage(commit='a' * 40)
        self.assertFalse(local.inbox_root(self.target).exists())

    def test_bootstrap_and_pointer_validation(self):
        info = self.target / 'BUILD-INFO.json'
        info.write_text(json.dumps(dict(version='0.13.0', commit='a' * 40)))
        with self.assertRaisesRegex(ValueError, 'once using copy.sh'):
            local.check_target(self.target)
        root = local.inbox_root(self.target)
        root.mkdir(parents=True)
        (root / 'trusted-key.json').write_text(json.dumps(self.public))
        local.atomic_json(root / 'ready.json', {'directory': '../outside'})
        with self.assertRaisesRegex(ValueError, 'pointer'):
            local.candidate(self.target)
