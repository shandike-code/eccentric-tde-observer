"""Static expression inventory of the frozen scanner; never opens field data.

只枚举完全相同的有序表达式；不化简、不重结合、不宣称浮点或性能验证。
"""
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path

SOURCE_SHA = '9349c255b35c515fd37e7903a120ebed753e9c517c9381b402d4184d450a1643'


def expression(node, env):
    """Limited symbolic parser, with explicit binary64 subtraction nodes."""
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'fields':
        return env['fields'][expression(node.slice, env)]
    if isinstance(node, ast.BinOp):
        left, right = expression(node.left, env), expression(node.right, env)
        if isinstance(node.op, ast.Add) and type(left) is type(right) is int:
            return left + right
        if isinstance(node.op, ast.Sub):
            return ('subtract_binary64', left, right)
    raise ValueError('unsupported expression: ' + ast.dump(node))


def audit(source):
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('frozen source SHA mismatch')
    tree = ast.parse(raw)
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    slab = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'slab_statistics')
    assignments = {n.targets[0].id: n.value for n in ast.walk(slab)
                   if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    labels = constants['LABELS']
    env = dict(zip(('ap', 'af', 'am', 'hp', 'hf', 'hm'), labels), fields=labels)
    basis = [('cast_longdouble', expression(n, env))
             for n in assignments['basis'].generators[0].iter.elts]
    direct_names = [n.id for n in assignments['direct'].generators[0].iter.elts]
    matrices = [('basis', basis)]
    errors = []
    for index, (a, h) in enumerate(constants['COMBINATIONS']):
        local = dict(env, a=a, h=h)
        for name in ('d', 'ra', 'rh', 'e', 'mapped'):
            local[name] = expression(assignments[name], local)
        vectors = [('cast_longdouble', local[name]) for name in direct_names]
        label = labels[a] + '_' + labels[h]
        matrices.append((label, vectors))
        for j, (v, coefficients) in enumerate(zip(vectors, constants['COEFFICIENTS'][index])):
            # 保留零初始化及原始逐项加法顺序；即使代数结果为零也不简化。
            formed = ('zeros_like_longdouble', v)
            for c, b in zip(coefficients, basis):
                if c:
                    formed = ('add_longdouble', formed, ('multiply_integer_longdouble', c, b))
            errors.append((label + ':' + str(j), ('subtract_longdouble', v, formed)))
    vector_slots = defaultdict(list)
    moment_slots = defaultdict(list)
    error_slots = defaultdict(list)
    for label, vectors in matrices:
        for i, v in enumerate(vectors):
            vector_slots[v].append(label + ':' + str(i))
            for j in range(i, len(vectors)):
                # 有序(x,y)，不以交换乘法操作数再去重；两种归约结果一起复用。
                moment_slots[(v, vectors[j])].append(label + ':' + str(i) + ',' + str(j))
    for label, e in errors:
        error_slots[e].append(label)

    def inventory(slots):
        return [dict(expression=k, occurrences=v) for k, v in slots.items()]

    return dict(schema='x20-86061-static-reuse-audit-v1', source_sha256=SOURCE_SHA,
        counts=dict(vector_slots=25, unique_vector_expressions=len(vector_slots),
                    gram_dot_calls=sum(len(v) for v in moment_slots.values()),
                    unique_ordered_gram_products=len(moment_slots),
                    reconstruction_dot_calls=len(errors), unique_reconstruction_expressions=len(error_slots),
                    source_scale_evaluations=1, bound_evaluations=4),
        vectors=inventory(vector_slots), ordered_gram_products=inventory(moment_slots),
        reconstruction=inventory(error_slots),
        numeric_equivalence_tested=False, optimized_kernel_implemented=False,
        speedup_measured=False, new_slurm_jobs=0, real_field_bytes_read=0,
        full_scan_authorized=False, physical_validation=False)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    result = audit(args.source)
    with args.output.open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(result['counts'], sort_keys=True))
