"""Independent standard-library review of synthetic boundary receipts only."""
import json
from pathlib import Path


def review(directory, platform):
    if platform not in ('linux', 'darwin'):
        raise ValueError('platform')
    result = json.loads((Path(directory)/'result.json').read_text())
    for flag in ('whole_lifecycle_environment_boundary_verified',
                 'actual_source_manifest_prepared', 'new_production_authorized'):
        if result[flag] is not False:
            raise ValueError('false production qualification')
    cases = result['cases']
    if [row['mode'] for row in cases] != ['normal','rss','signal-time','hard-time']:
        raise ValueError('missing or reordered cases')
    normal, rss, alarm, hard = cases
    for row in cases[:-1]:
        if type(row['returncode']) is not int or row['returncode'] != 0 or row['external_timeout'] is not False or row['stderr']:
            raise ValueError('child failed')
    if hard['returncode'] != -9 or hard['external_timeout'] is not True:
        raise ValueError('external kill absent')
    if json.loads(rss['stdout'])['rejected'] != 'RSS limit':
        raise ValueError('RSS refusal absent')
    if json.loads(alarm['stdout'])['rejected'] != 'signal:14':
        raise ValueError('alarm refusal absent')
    value = json.loads(normal['stdout'])
    expected = {name+':'+operation for name in ('synthetic.dat','alias.bin','hard.bin','absent.dat')
                for operation in ('open','stat','lstat','readlink','libc-open')}
    expected.update(('listdir','import-time-stat','unknown-import','fork','exec'))
    denied = value['denied']
    unproven = value['unproven']
    keys = denied + [row['operation'] for row in unproven]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('incomplete access probes')
    if value['all_path_probes_denied'] is not (not unproven):
        raise ValueError('false guard verdict')
    if platform == 'linux' and (unproven or value['backend'] != 'linux-seccomp-tsync-allowlist-v1'):
        raise ValueError('Linux seal did not reject every probe')
    for flag in ('environment_preload_protected','native_adapter_integrated'):
        if value[flag] is not False:
            raise ValueError('unverified integration claim')
    if value['memory_imports'] != ['sealed_good'] or value['synthetic_only'] is not True:
        raise ValueError('import scope')
    if (type(value['consumer_returned_bytes']) is not int or
            value['consumer_returned_bytes'] != 358 or value['synthetic_npz_bytes'] != 352 or
            value['array_sha256'] != '3cdb84857b942fe6dfa5d5b90444935652a4a319bab777539926f4b43fe579fa'):
        raise ValueError('synthetic decode changed')
    return {'synthetic_receipts_reviewed': True, 'platform': platform,
            'denied_probes': len(denied), 'unproven_probes': unproven,
            'post_environment_seal_probes_passed': not unproven,
            'whole_lifecycle_guard_verified': False, 'native_adapter_integrated': False,
            'production_authorized': False}
