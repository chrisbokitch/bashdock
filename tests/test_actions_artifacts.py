"""Storage cleanup must preserve release assets, diagnostics and active runs."""
import unittest
import urllib.error
from scripts.cleanup_actions_artifacts import BUNDLE, cleanup, github_api


def artifact(artifact_id, name=BUNDLE, run_id=10, size=100):
    return dict(id=artifact_id, name=name, workflow_run=dict(id=run_id), size_in_bytes=size, expired=False)


class ActionsArtifactTests(unittest.TestCase):
    def test_api_rejects_deleting_releases_runs_and_arbitrary_paths(self):
        for path in ('/releases/1', '/actions/runs/1', '/actions/artifacts', '/actions/artifacts/../1'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                github_api('DELETE', path)

    def test_permission_errors_abort_cleanup_instead_of_reporting_success(self):
        deleted = []
        def api(method, path):
            if path.startswith('/actions/artifacts?'):
                return dict(artifacts=[artifact(1), artifact(2)])
            if method == 'GET':
                return dict(status='completed')
            deleted.append(path)
            raise urllib.error.HTTPError('https://api.github.com', 403, 'Forbidden', {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            cleanup(api, delete=True, emit=lambda value: None)
        self.assertEqual(['/actions/artifacts/1'], deleted)

    def test_only_completed_bundles_deleted_and_each_run_status_is_refreshed(self):
        entries = [artifact(1), artifact(2), artifact(3, run_id=11),
                   artifact(4, name='windows-build-diagnostics'), artifact(5, run_id=None)]
        calls = []
        statuses = iter(['completed', 'in_progress', 'queued'])
        def api(method, path):
            calls.append((method, path))
            if path.startswith('/actions/artifacts?'):
                return dict(artifacts=entries)
            if method == 'GET':
                return dict(status=next(statuses))
        summary = cleanup(api, delete=True, emit=lambda value: None)
        self.assertEqual([('DELETE', '/actions/artifacts/1')], [c for c in calls if c[0] == 'DELETE'])
        self.assertEqual(2, summary['skipped_active'])
        self.assertEqual(1, summary['skipped_unidentified'])
        self.assertEqual(100, summary['deleted_bytes'])

    def test_preview_never_deletes_and_snapshots_all_pages_before_deletion(self):
        for delete in (False, True):
            calls = []
            def api(method, path):
                calls.append((method, path))
                if path.endswith('&page=1'):
                    return dict(artifacts=[artifact(i+1) for i in range(100)])
                if path.endswith('&page=2'):
                    return dict(artifacts=[artifact(101)])
                if method == 'GET':
                    return dict(status='completed')
            summary = cleanup(api, delete=delete, emit=lambda value: None)
            self.assertEqual(101, summary['matched'])
            self.assertEqual(101 if delete else 0, summary['deleted'])
            self.assertEqual([('GET', '/actions/artifacts?per_page=100&page=1'),
                              ('GET', '/actions/artifacts?per_page=100&page=2')], calls[:2])
            self.assertEqual(101 if delete else 0, sum(c[0] == 'DELETE' for c in calls))
