import ast
from pathlib import Path
import pytest
from handoff.audit_tools.audit_x20_86061_reuse import audit, expression

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_source_inventory():
    result = audit(ROOT / 'operations/x20_85889_chord_scan.py')
    c = result['counts']
    assert c['gram_dot_calls'] == 75
    assert c['reconstruction_dot_calls'] == 20
    assert c['unique_vector_expressions'] == 15
    # 同一个HF-AF分别出现在基底、PP映射差和FF输入差。
    assert any(x['occurrences'] == ['basis:0', 'AP_HP:2', 'AF_HF:0'] for x in result['vectors'])
    assert result['real_field_bytes_read'] == 0
    assert not result['numeric_equivalence_tested']


def test_reassociation_is_not_identity():
    env = dict(a='AP', b='AF', c='HP', d='HF')
    first = expression(ast.parse('(d-c)-(b-a)', mode='eval').body, env)
    second = expression(ast.parse('(d-b)-(c-a)', mode='eval').body, env)
    assert first != second


def test_source_change_is_rejected(tmp_path):
    source = tmp_path / 'changed.py'
    source.write_bytes((ROOT / 'operations/x20_85889_chord_scan.py').read_bytes() + b'\n')
    with pytest.raises(ValueError, match='SHA'):
        audit(source)


def test_unknown_syntax_is_rejected():
    with pytest.raises(ValueError, match='unsupported'):
        expression(ast.parse('a*b', mode='eval').body, dict(a='A', b='B'))
