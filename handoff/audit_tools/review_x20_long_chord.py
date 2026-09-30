"""Independent receipt, lineage and small-statistic audit of Slurm 81647.

No full fields are downloaded or recomputed; native identity is a batch receipt.
"""
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path
import numpy as np
from handoff.audit_tools.review_x20_operator import old, cw, read, arrays, slab_coverage
from handoff.audit_tools.review_x20_histories import source_archive

ROOT = Path('outputs/review-20260925')
OUT = ROOT / 'x20-long-chord-81647-received'
BASE = 'complete-1790723120419269285'


def gram_review(rows, saved):
    slab_coverage(rows)
    matrices = np.asarray([r['gram'] for r in rows])
    minima = np.asarray([r['minima'] for r in rows])
    assert matrices.shape == (301, 5, 5) and minima.shape == (301, 8)
    assert np.isfinite(matrices).all() and np.isfinite(minima).all() and np.all(minima >= 0)
    assert np.array_equal(matrices, matrices.transpose(0, 2, 1))
    subnormal = []
    for row, matrix in zip(rows, matrices):
        scale = float(np.max(abs(matrix)))
        if not scale:
            continue
        bound = max(1e-12, 2.5 * (float(np.nextafter(0., 1.)) / scale))
        eigen = float(np.linalg.eigvalsh(matrix / scale).min())
        assert eigen >= -bound
        if bound > 1e-12:
            subnormal.append(dict(first_group=row['first_group'], minimum_eigenvalue=eigen, bound=bound))
    gram = np.array([[math.fsum(matrices[:, i, j]) for j in range(5)] for i in range(5)])
    np.testing.assert_array_equal(gram, saved)
    with localcontext() as ctx:
        ctx.prec = 70
        h = [[Decimal.from_float(float(v)) / Decimal.from_float(float(gram[0, 0])) for v in row[1:]] for row in gram[1:]]
        pivots = []
        for n in range(4):
            pivot = h[n][n]
            assert pivot > 0
            pivots.append(str(pivot))
            for i in range(n + 1, 4):
                for j in range(n + 1, 4):
                    h[i][j] -= h[i][n] * h[n][j] / pivot
    eig = np.linalg.eigvalsh(gram[1:, 1:] / gram[0, 0])
    return dict(gram=gram.tolist(), positive_hessian_ldl_pivots=pivots,
                hessian_eigenvalues=eig.tolist(), hessian_condition=float(eig[-1] / eig[0]),
                subnormal_slab_roundoff=subnormal, all_groups=9632, all_slabs=301)


def main():
    inventory = cw.receive(ROOT / (BASE + '.tar.gz'), ROOT / (BASE + '-receipt.json'), OUT)
    assert inventory == read(ROOT / (BASE + '.json'))
    history_source = ROOT / 'x20-history-80554-received'
    prior = ROOT / 'x20-capped-80925-received'
    spectral = ROOT / 'x20-spectral-81453-received'
    for folder, evidence in [(history_source, '20260929-x20-history-review.json'),
                             (prior, '20260929-x20-capped-review.json'),
                             (spectral, '20260929-x20-spectral-review.json')]:
        source_archive(folder, evidence, ROOT)
    d, s, state = [read(OUT / p) for p in ('declaration.json', 'summary.json', 'chord/state.json')]
    terminal = read(Path('handoff/evidence/20260930-x20-long-chord-81647-terminal.json'))
    assert terminal['job_id'] == 81647 and terminal['state'] == 'COMPLETED' and 'ExitCode=0:0' in terminal['scontrol']
    scheduler = d['environment']['scheduler']
    assert scheduler['SLURM_JOB_ID'] == '81647' and scheduler['SLURM_CPUS_PER_TASK'] == '32'
    assert scheduler['SLURM_MEM_PER_NODE'] == '131072' and scheduler['SLURM_JOB_QOS'] == 'qos_stu_cpu_long'
    assert not d['environment']['tracked_worktree_dirty']
    assert d['maximum_maps'] == s['new_maps'] == 4 and d['maximum_field_scans'] == 1
    assert d['maximum_feedback_pairs'] == s['new_feedback_pairs'] == s['new_material_steps'] == 0
    assert s['accepted_outer_steps'] == d['accepted_outer_steps'] == 20 and d['coefficient_l1_cap'] == 17
    assert s['status'] == read(OUT / 'status.json')['status'] == 'expanded_basis_collected_requires_review'
    assert not any(d[k] for k in ('baseline_replaced', 'candidate_written', 'original_acceptance_gates_changed'))
    assert not s['baseline_replaced'] and not s['candidate_written'] and s['coefficient_dimension'] == 4
    assert s['parent_peak_rss_bytes'] < 6 * 1024**3
    for c in d['code']:
        old.verify_claim(c, Path(c['path']))
    basis = d['original_basis']
    assert basis == read(prior / 'declaration.json')['basis'] and d['seed'] == basis[2]
    assert d['source_jobs'] == [80554, 80925, 81453]
    source_prefixes = {
        'outputs/hpc/x20-long-chord-20260930/': OUT,
        'outputs/hpc/x20-radiation-history-calibration-20260929/': history_source,
        'outputs/hpc/x20-capped-subspace-20260929/': prior,
    }
    # Historical physical inputs are bound transitively to the previously audited declaration.
    historical_claims = read(history_source / 'declaration.json')['claims']
    verified = 0
    external = []
    for c in d['claims']:
        if c['path'].endswith('.dat'):
            assert c in basis or c in read(history_source / 'declaration.json').get('claims', [])
            external.append(c)
            continue
        path = Path(c['path'])
        for prefix, folder in source_prefixes.items():
            if c['path'].startswith(prefix):
                path = folder / c['path'][len(prefix):]
                break
        if '/archives/' in c['path']:
            path = ROOT / Path(c['path']).name
        if path.is_file():
            old.verify_claim(c, path)
            verified += 1
        else:
            assert c in historical_claims, c['path']
            external.append(c)
    for c in d['cases']['control'].values():
        old.verify_claim(c, OUT / 'source-preflight/inputs' / Path(c['path']).name)
    trial = OUT / 'chord/trial_material.npz'
    assert old.digest(trial) == old.digest(OUT / 'source-preflight/inputs/trial_material.npz') == old.digest(history_source / 'late/trial_material.npz')
    t = arrays(trial)
    assert int(t['phase_index']) == 1367 and float(t['step_duration_s']) == 889.419892762322
    native = read(OUT / 'chord/native_trial_audit.json')
    old.verify_claim(native['trial_source'], trial)
    assert native['native_mirrored_material_exact'] and native['physical_phase_and_dt_exact']
    identity = read(OUT / 'chord/initialized_identity.json')
    assert identity['native'] == native and identity['passed'] and identity['trial'] == native['trial_source']
    cfg = read(OUT / 'chord/config.json')
    assert cfg['warm_seed'] == d['seed'] and cfg['workers'] == 16 and cfg['maximum_maps'] == 4
    assert cfg['shape'] == [9632, 32, 4096] and cfg['radiation_threshold'] == 1e-4 and cfg['boundary_threshold'] == 1e-3
    maps, peaks = old.audit_maps(OUT, 'chord', max_maps=4)
    assert len(maps) == 4 and len(peaks) == 304 and state['history'][0]['input_sha256'] == d['seed']['sha256']
    retained = read(OUT / 'chord/endpoints-map04/manifest.json')
    expanded = read(OUT / 'expanded-basis.json')
    assert retained['history_rows'] == state['history'][-2:] and retained['new_map_count'] == 4
    assert not retained['feedback_evaluated'] and not retained['material_accepted']
    assert expanded['new_history'] == state['history'] and expanded['original_basis'] == basis
    assert expanded['source_map'] == state['history'][-1]
    assert expanded['new_pair'] == [retained['endpoints'][k] for k in ('final', 'mapped_final')]
    assert [c['sha256'] for c in expanded['new_pair']] == [state['history'][-1][k] for k in ('input_sha256', 'output_sha256')]
    collection = read(OUT / 'collection.json')
    z = arrays(OUT / 'expanded-system.npz')
    result = gram_review(collection['slabs'], z['gram'])
    np.testing.assert_array_equal(z['gram'], collection['gram'])
    np.testing.assert_allclose(z['gram'][:4, :4], read(prior / 'prediction.json')['gram'], rtol=2e-12, atol=0)
    spectra = z['spectra']
    assert spectra.shape == (8, 9632) and np.isfinite(spectra).all() and np.all(spectra >= 0)
    np.testing.assert_array_equal(spectra[:6], arrays(spectral / 'boundary-spectra.npz')['spectra'])
    geometry = arrays(OUT / 'source-preflight/boundary_geometry.npz')
    previous_geometry = arrays(spectral / 'source-preflight/boundary_geometry.npz')
    assert set(geometry) == {'mu', 'weight', 'width'}
    for key in geometry:
        np.testing.assert_array_equal(geometry[key], previous_geometry[key])
        assert np.isfinite(geometry[key]).all()
    assert geometry['width'].shape == (9632,) and geometry['mu'].shape == geometry['weight'].shape == (32,)
    assert np.all(geometry['width'] > 0) and np.all(geometry['weight'] > 0)
    np.testing.assert_allclose(math.fsum(geometry['weight']), 2., rtol=1e-14)
    fin, fout = spectra[-2:]
    den = max(math.fsum(fin), math.fsum(fout))
    boundary = dict(boundary_l1=math.fsum(abs(fout - fin)) / den,
                    boundary_bolometric=abs(math.fsum(fout) - math.fsum(fin)) / den)
    for key, value in boundary.items():
        np.testing.assert_allclose(value, state['history'][-1][key], rtol=2e-8, atol=0)
    result.update(job_id=81647, archive=read(ROOT / (BASE + '-receipt.json')),
                  verified_files=len(inventory['files']), verified_code_claims=len(d['code']),
                  verified_source_claims=verified, external_claims_bound_to_prior_audit=external,
                  maps=maps, map_process_receipts=len(peaks), maximum_proc_kib=max(peaks),
                  parent_peak_rss_bytes=s['parent_peak_rss_bytes'], wall_s=s['wall_s'],
                  new_maps=4, new_feedback_pairs=0, new_material_steps=0, accepted_outer_steps=20,
                  baseline_replaced=False, independent_small_statistic_reduction=True,
                  large_fields_recomputed_on_mac=False, native_identity_independently_recomputed=False,
                  native_identity_batch_receipt_verified=True, strict_physical_error_bound=False,
                  original_basis=basis, new_pair=expanded['new_pair'], new_pair_boundary=boundary,
                  scientific_independent_audit_completed=True)
    Path('handoff/evidence/20260930-x20-long-chord-review.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('gram', 'external_claims_bound_to_prior_audit', 'original_basis')}, indent=2))


if __name__ == '__main__':
    main()
