"""Remove only obsolete BashDock Actions build bundles, never release assets."""
import argparse
import json
import os
import re
import urllib.error
import urllib.request

REPOSITORY = 'chrisbokitch/bashdock'
BUNDLE = 'bashdock-windows-x64'


def github_api(method, path):
    if method == 'DELETE' and not re.fullmatch(r'/actions/artifacts/[1-9][0-9]*', path):
        raise ValueError('Cleanup may delete individual Actions artifacts only.')
    if method not in ('GET', 'DELETE'):
        raise ValueError('Unsupported cleanup operation.')
    request = urllib.request.Request('https://api.github.com/repos/' + REPOSITORY + path,
        method=method, headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                               'Accept': 'application/vnd.github+json',
                               'User-Agent': 'BashDock-artifact-cleanup',
                               'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response) if method == 'GET' else None


def cleanup(api, *, delete=False, emit=print):
    # Snapshot all pages before deleting, otherwise offset pagination can skip
    # entries as earlier pages shrink. Never delete workflow runs or logs.
    artifacts = []
    page = 1
    while True:
        batch = api('GET', f'/actions/artifacts?per_page=100&page={page}')['artifacts']
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    summary = dict(delete=delete, matched=0, deleted=0, deleted_bytes=0,
                   reclaimable_bytes=0, skipped_active=0, skipped_unidentified=0)
    for artifact in artifacts:
        if artifact['name'] != BUNDLE or artifact.get('expired'):
            continue
        artifact_id = artifact.get('id')
        run_id = (artifact.get('workflow_run') or {}).get('id')
        if type(artifact_id) is not int or artifact_id <= 0 or type(run_id) is not int or run_id <= 0:
            summary['skipped_unidentified'] += 1
            continue
        # A new request for each artifact also protects a run that was rerun
        # after inventory collection, including queued/waiting release jobs.
        if api('GET', f'/actions/runs/{run_id}')['status'] != 'completed':
            summary['skipped_active'] += 1
            continue
        summary['matched'] += 1
        summary['reclaimable_bytes'] += artifact['size_in_bytes']
        if delete:
            try:
                api('DELETE', f'/actions/artifacts/{artifact_id}')
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
                emit(json.dumps(dict(artifact=artifact_id, result='already absent')))
                continue
            summary['deleted'] += 1
            summary['deleted_bytes'] += artifact['size_in_bytes']
        emit(json.dumps(dict(artifact=artifact_id, run=run_id, bytes=artifact['size_in_bytes'],
                             result='deleted' if delete else 'would delete')))
    emit(json.dumps(summary, sort_keys=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete', action='store_true', help='Permanently delete eligible build bundles; default is preview only.')
    args = parser.parse_args()
    cleanup(github_api, delete=args.delete)


if __name__ == '__main__':
    main()
