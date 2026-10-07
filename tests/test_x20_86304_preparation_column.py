"""Small new column tests; never load scientific files or run old suites."""
import ast
from pathlib import Path
import unittest
import numpy as np
from operations.x20_86304_preparation_column import full_column, native_configuration
from operations.x20_86304_preparation_inflate import PayloadLedger


def fixture():
    mass = np.array([1.0 + (i % 4) / 4 for i in range(128)])
    rho = np.array([[1.0] * 128, [2.0] * 128, [4.0] * 128])
    return dict(cell_mass_g_cm2=mass, density_g_cm3=rho,
                temperature_k=np.full((3, 128), 8192.),
                hydrogen_fraction=np.tile([.75, .25], (3, 128, 1)),
                helium_fraction=np.tile([.5, .25, .25], (3, 128, 1)))


class ColumnTests(unittest.TestCase):
    def test_original_tree_results(self):
        # Only the frozen single function is compiled as a test oracle; no imports of its module.
        source = Path('scripts/phase7b5x_full_depth_block_probe.py').read_text()
        fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_full_column')
        namespace = {'np': np}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<frozen-column-test>', 'exec'), namespace)
        for transform in (lambda a: a, np.asfortranarray, lambda a: a[:, ::-1] if a.ndim > 1 else a[::-1]):
            material = {k: transform(v) for k, v in fixture().items()}
            before = {k: v.tobytes() for k, v in material.items()}
            observed = full_column(material, PayloadLedger(), lambda: None)
            expected = namespace['_full_column'](material)
            self.assertEqual(list(observed), list(expected))
            for key in expected:
                self.assertEqual(observed[key].tobytes(), expected[key].tobytes())
            self.assertEqual(before, {k: v.tobytes() for k, v in material.items()})

    def test_independent_geometry(self):
        material = fixture(); ledger = PayloadLedger()
        result = full_column(material, ledger, lambda: None)
        for p in range(3):
            widths = [(1 + (i % 4) / 4) / (2 ** p) for i in range(128)]
            expected = [-sum(widths)]
            for width in widths + widths[::-1]: expected.append(expected[-1] + width)
            self.assertEqual(result['edge_cm'][p].tolist(), expected)
        self.assertEqual(ledger.budget.used, sum(size for _, size in ledger.entries))
        self.assertEqual(len(ledger.entries), 30)

    def test_stop_before_every_reservation(self):
        complete = PayloadLedger(); full_column(fixture(), complete, lambda: None)
        class Stop(Exception): pass
        for target in range(len(complete.entries)):
            ledger = PayloadLedger()
            def check():
                if len(ledger.entries) == target: raise Stop()
            with self.assertRaises(Stop): full_column(fixture(), ledger, check)
            self.assertEqual(ledger.entries, complete.entries[:target])

    def test_strict_budget_before_result(self):
        ledger = PayloadLedger(128)
        with self.assertRaises(ValueError): full_column(fixture(), ledger, lambda: None)
        self.assertEqual(ledger.entries, [])

    def test_bad_inputs(self):
        for key, value in [('density_g_cm3', 0.), ('temperature_k', np.nan),
                           ('hydrogen_fraction', -1.), ('helium_fraction', 2.)]:
            m = fixture(); m[key].flat[0] = value
            with self.assertRaises(ValueError): full_column(m, PayloadLedger(), lambda: None)

    def test_shape_and_dtype(self):
        for value in (np.ones((1, 128)), np.ones((3, 127)), np.ones((3, 128), dtype='f4')):
            m = fixture(); m['density_g_cm3'] = value
            with self.assertRaises(ValueError): full_column(m, PayloadLedger(), lambda: None)

    def test_overflow_rejected(self):
        m = fixture(); m['density_g_cm3'][:] = np.nextafter(0., 1.)
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            with self.assertRaises(ValueError): full_column(m, PayloadLedger(), lambda: None)

    def test_production_closed(self):
        with self.assertRaises(RuntimeError): native_configuration(synthetic=True)


if __name__ == '__main__': unittest.main()
