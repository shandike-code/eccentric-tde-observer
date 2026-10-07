"""Standard-library review of the two pinned workspace-query receipts."""
import json
from pathlib import Path


def review(value, expected_platform):
    if value['schema'] != '86304-native-workspace-query-v1':
        raise ValueError('schema')
    if expected_platform not in ('Darwin', 'Linux') or value['platform'] != expected_platform:
        raise ValueError('platform')
    expected = ('arm64', 'dsyevd$NEWLAPACK$ILP64') if expected_platform == 'Darwin' else ('x86_64', 'scipy_dsyevd_64_')
    if (value['machine'], value['symbol']) != expected:
        raise ValueError('ABI')
    if type(value['fortran_integer_bytes']) is not int or value['fortran_integer_bytes'] != 8:
        raise ValueError('integer size')
    if type(value['eigensolves']) is not int or value['eigensolves'] != 0:
        raise ValueError('scope')
    for key in ('backend_private_workspace_bounded', 'production_metering_integrated', 'rss_bound_verified'):
        if value[key] is not False:
            raise ValueError('unsupported qualification')
    rows = value['rows']
    if len(rows) != 16:
        raise ValueError('missing degree')
    for n, row in enumerate(rows, 1):
        # 34n 是本次两后端观察值的固定审阅基准，不是通用 LAPACK 上界。
        expected_row = dict(degree=n, lwork=1 if n == 1 else 34*n, liwork=1,
                            info=0, matrix_and_internal_values_bytes=8*n*(n+1),
                            caller_workspace_bytes=8*((1 if n == 1 else 34*n)+1),
                            input_unchanged=True)
        if row.keys() != expected_row.keys():
            raise ValueError('row keys')
        for key, expected_value in expected_row.items():
            if type(row[key]) is not type(expected_value) or row[key] != expected_value:
                raise ValueError('query value or arithmetic')
    return dict(platform=expected_platform, cases=16, eigensolves=0,
                maximum_identified_wrapper_bytes=6536,
                backend_private_workspace_bounded=False,
                production_metering_integrated=False)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('receipt', type=Path)
    parser.add_argument('--platform', required=True, choices=['Darwin', 'Linux'])
    args = parser.parse_args()
    print(json.dumps(review(json.loads(args.receipt.read_text()), args.platform), indent=2))
