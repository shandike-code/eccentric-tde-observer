"""Static cost inventory of pinned reuse source; no numerical kernel import or I/O.

Counts describe successful-path array expression results, not allocator calls,
peak RSS, memory traffic, timed kernel components, or guaranteed speedup.
"""
import ast
import hashlib
import json
from pathlib import Path
from handoff.audit_tools.audit_x20_86061_reuse import audit as expressions

PINS = {
 'operations/x20_85889_chord_scan.py': '9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643',
 'operations/x20_85889_chord_scan_reuse.py': 'a4b6b5b07eaaa457b5b5aa2cd726597f2476c78c7d2b3937810b6551fe0594a6',
 'handoff/audit_tools/audit_x20_86061_reuse.py': 'e78b7c8e56b7a429aca84e2b26ce717618f9c3bf451e7cef2cfe1ad3a625d0d7',
}


def classify(products, reconstruction):
    diagonal = [row for row in products if row['expression'][0] == row['expression'][1]]
    return dict(ordered_matrix_products=len(products), matrix_diagonal=len(diagonal),
                matrix_off_diagonal=len(products)-len(diagonal), reconstruction_squares=len(reconstruction),
                total_dot_calls=len(products)+len(reconstruction))


def audit(root):
    root = Path(root); trees = {}
    for name, pin in PINS.items():
        raw = (root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != pin: raise ValueError('source pin: '+name)
        trees[name] = ast.parse(raw)
    old = expressions(root/'operations/x20_85889_chord_scan.py')
    counts = classify(old['ordered_gram_products'], old['reconstruction'])
    dot = next(n for n in trees['operations/x20_85889_chord_scan.py'].body
               if isinstance(n, ast.FunctionDef) and n.name == 'dot')
    # The pinned dot has two sum reductions and one absolute-product expression.
    sums = [n for n in ast.walk(dot) if isinstance(n, ast.Call) and
            isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and
            n.func.value.id == 'np' and n.func.attr == 'sum']
    absolute = [n for n in ast.walk(dot) if isinstance(n, ast.Call) and
                isinstance(n.func, ast.Name) and n.func.id == 'abs']
    comparisons = [n for n in ast.walk(dot) if isinstance(n, ast.Compare)]
    conjunctions = [n for n in ast.walk(dot) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitAnd)]
    assert (len(sums),len(absolute),len(comparisons),len(conjunctions)) == (2,1,3,2)
    calls = counts['total_dot_calls']; n = 32*32*4096; ld_bytes=16
    counts.update(sum_reductions=calls*len(sums), product_arrays=calls,
                  absolute_product_arrays=calls*len(absolute),
                  underflow_boolean_expression_results=calls*(len(comparisons)+len(conjunctions)),
                  discarded_reconstruction_absolute_sums=counts['reconstruction_squares'])
    return dict(schema='x20-86191-static-cost-v1', source_pins=PINS, counts=counts,
        ordered_matrix_products=old['ordered_gram_products'], reconstruction=old['reconstruction'],
        school_slab=dict(elements=n, longdouble_itemsize_assumed=ld_bytes,
          one_longdouble_array_bytes=n*ld_bytes, one_boolean_array_bytes=n,
          cumulative_product_and_absolute_array_payload_bytes=2*calls*n*ld_bytes,
          cumulative_underflow_boolean_result_payload_bytes=counts['underflow_boolean_expression_results']*n),
        candidate_counts=dict(square_calls=counts['matrix_diagonal']+counts['reconstruction_squares'],
          first_stage_unused_absolute_reductions=counts['reconstruction_squares'],
          further_diagonal_absolute_reductions=counts['matrix_diagonal'],
          sum_reductions_if_both_square_changes_validated=2*calls-counts['matrix_diagonal']-counts['reconstruction_squares']),
        numeric_equivalence_tested=False, new_optimized_kernel_implemented=False,
        component_profile_measured=False, speedup_measured=False, full_scan_authorized=False,
        new_slurm_jobs=0, real_field_bytes_read=0,
        caveat='Expression-result payload totals are not simultaneous live memory, RSS, allocator counts, or memory/device traffic.')


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();result=audit(a.root)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result['counts'],sort_keys=True))
