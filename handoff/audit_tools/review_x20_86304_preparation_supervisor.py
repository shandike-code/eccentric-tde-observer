"""Independent standard-library receipt/prefix verification, no supervisor import."""
import hashlib
import json
import math
from pathlib import Path
import signal


def review(destination, *, expected_platform):
    if expected_platform not in ('darwin','linux'):raise ValueError('platform scope')
    root=Path(destination)
    summary=json.loads((root/'summary.json').read_text())
    if summary['synthetic'] is not True or any(summary[k] is not False for k in
            ('complete_native_context_verified','production_resource_stop_guards_integrated',
             'whole_lifecycle_guard_verified')):
        raise ValueError('qualification')
    expected={'normal':None,'rss':'child_exit','time':'child_exit','signal':'child_exit',
              'ignored':'outer_deadline','partial':'child_exit',
              'parent_signal':'parent_signal:'+str(30 if expected_platform=='darwin' else 10),'output':'output_limit'}
    if set(summary['cases'])!=set(expected):raise ValueError('case coverage')
    for name,reason in expected.items():
        row=summary['cases'][name]
        if row!=json.loads((root/name/'outcome.json').read_text()):raise ValueError('outcome')
        if (row['schema']!='86304-preparation-supervisor-v1' or
                row['reason']!=reason or type(row['returncode']) is not int or
                type(row['success']) is not bool or row['success']!=(name=='normal') or
                row['whole_lifecycle_guard_verified'] is not False or
                row['production_authorized'] is not False):raise ValueError('outcome fields')
        limit=row['outer_limit_s'];elapsed=row['elapsed_s']
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (limit,elapsed)):
            raise ValueError('time type')
        if limit!=(150 if name=='normal' else .5 if name=='ignored' else 3):raise ValueError('limit')
        if name=='normal' and (row['returncode']!=0 or elapsed>=150):raise ValueError('normal')
        if name in ('ignored','parent_signal') and (row['kill_sent'] is not True or row['returncode']!=-signal.SIGKILL):
            raise ValueError('kill outcome')
        if name=='ignored' and elapsed<limit:raise ValueError('early timeout')
        if reason=='child_exit' and row['returncode']==0:raise ValueError('failed child accepted')
        size=0
        for stream in ('stdout','stderr'):
            raw=(root/name/(stream+'.log')).read_bytes();fact=row['outputs'][stream]
            if type(fact['size_bytes']) is not int or fact['size_bytes']!=len(raw) or fact['sha256']!=hashlib.sha256(raw).hexdigest():
                raise ValueError('prefix identity')
            size+=len(raw)
        if type(row['output_limit_bytes']) is not int or row['output_limit_bytes']!=(257 if name=='output' else 8*1024**2) or size>row['output_limit_bytes']:
            raise ValueError('output budget')
        err=(root/name/'stderr.log').read_text()
        if name in ('rss','time','signal') and ('RSS limit' if name=='rss' else 'signal:') not in err:
            raise ValueError('internal stop evidence')
        if name=='partial' and (root/name/'stdout.log').read_text()!='partial\n':raise ValueError('partial prefix')
    return {'synthetic_receipts_verified':True,'case_count':len(expected),
            'production_resource_stop_guards_integrated':False,'whole_lifecycle_guard_verified':False}
