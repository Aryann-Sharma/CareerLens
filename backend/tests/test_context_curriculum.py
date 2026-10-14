import json
import os
from collections import Counter
from pathlib import Path

import pytest

from backend.ml.context_curriculum import DUTIES, build
from backend.ml.context_data import expanded, load_cases
from backend.ml.context_sentences import paragraph_units
from backend.ml.train_context_calibrated import combined_rows
from backend.ml.train_context_review import LABELS


def test_curriculum_rebuilds_and_keeps_components_in_one_split(tmp_path):
    target = tmp_path / 'cases.json'
    build(target)
    committed = Path('evaluation/context-curriculum-cases.json')
    assert json.loads(target.read_text()) == json.loads(committed.read_text())
    rows = combined_rows([Path('evaluation/context-source-cases.json'),
                          Path('evaluation/context-followup-cases.json'), committed])
    families = {r['family']: r['split'] for r in rows}
    curriculum = load_cases(committed)
    assert Counter(r['split'] for r in curriculum) == {'train': 1264, 'dev': 368}
    assert set(DUTIES) == set(LABELS)
    for row in curriculum:
        for component in row.get('component_families', []):
            assert families[component] == row['split']
    # Also catch duplicate typo variants crossing the boundary.
    assignments = {}
    for row in expanded(rows):
        normalized = ''.join(c.casefold() for c in row['text'] if c.isalnum())
        assert assignments.setdefault(normalized, row['split']) == row['split']


def test_promotion_check_is_held_out_and_has_source_provenance():
    path = Path('evaluation/context-promotion-check.json')
    check = json.loads(path.read_text())
    rows = load_cases(path)
    assert len(rows) == 32 and all(r['split'] == 'test' for r in rows)
    sources = {s['id']: s for s in check['sources']}
    training_paths = [Path('evaluation') / name for name in (
        'context-source-cases.json', 'context-followup-cases.json', 'context-curriculum-cases.json')]
    combined_rows(training_paths + [path])
    for row in rows:
        if row['origin'] == 'public-source-paraphrase':
            assert sources[row['source_id']]['url'].startswith('https://')


@pytest.mark.parametrize('text', [
    'An optional course says "Build software." This is a benefit, not a duty.',
    '🧭 Duties:\r\nWrite code without supervision. Test it before release.',
    'No programming is required. Instead, teach trainees how to operate machinery.',
    'Responsibilities:\nWrite code, verify changes, release the application.',
])
def test_passages_retain_scope_and_exact_original_offsets(text):
    units = paragraph_units(text)
    assert len(units) == 1
    assert units[0]['text'] == text
    assert text[units[0]['start']:units[0]['end']] == text


def test_passages_bound_work_and_cover_end_of_long_documents():
    text = '\n\n'.join(f'Paragraph {i} describes a different responsibility.' for i in range(100))
    units = paragraph_units(text)
    assert len(units) == 48 and '99' in units[-1]['text']
    assert all(text[u['start']:u['end']] == u['text'] for u in units)
    long = ' '.join(f'word{i}' for i in range(500))
    units = paragraph_units(long)
    assert len(units) == 5 and units[-1]['text'].endswith('word499')
    assert all(len(u['text'].split()) <= 140 for u in units)
    assert paragraph_units(' \n\t') == []


@pytest.mark.skipif(os.getenv('RUN_CONTEXT_STRESS_TESTS') != '1', reason='Requires local models')
@pytest.mark.parametrize('case', expanded(load_cases(Path('evaluation/context-promotion-check.json'))), ids=lambda r: r['id'])
def test_fresh_inputs_preserve_api_evidence_and_review_separation(client, case):
    from backend.tests.test_context_source_data import test_new_source_inputs_through_preview
    test_new_source_inputs_through_preview(client, case)


@pytest.mark.skipif(os.getenv('RUN_CURRICULUM_HEAD_TESTS') != '1', reason='Requires exported curriculum classifier')
def test_curriculum_export_reproduces_reports_and_is_batch_independent():
    import hashlib
    import numpy as np
    from backend.ml.evaluate_context_transformer import load_model, predict_rows, score_rows
    from backend.ml.train_context_review import metrics
    manifest, tokenizer, session = load_model(Path('.models/context-transformer-curriculum-v2b'))
    for name, digest in manifest['data_sha256'].items():
        assert hashlib.sha256(Path(name).read_text(encoding='utf-8').encode()).hexdigest() == digest
    report = json.loads(Path('evaluation/context-curriculum-results.json').read_text())
    regression = combined_rows([Path('evaluation/context-source-cases.json'), Path('evaluation/context-followup-cases.json')])
    for key, rows in [('test-clean', [r for r in expanded(regression) if r['split']=='test' and r['variant']=='clean']),
                      ('fresh-all', expanded(load_cases(Path('evaluation/context-promotion-check.json'))))]:
        assert metrics(rows, predict_rows(rows, manifest, tokenizer, session)) == report['evaluations'][key]['candidate']
    probes = [{'text':'Write application code and run automated regression tests.'},
              {'text':'We offer an optional course about writing code. It is a benefit, not an assigned duty.'},
              {'text':'Respond calmly to complaints and help subscribers regain access to their account.'}]
    together = score_rows(probes, manifest, tokenizer, session)
    separately = np.vstack([score_rows([row], manifest, tokenizer, session) for row in probes])
    np.testing.assert_allclose(together, separately, rtol=1e-4, atol=1e-5)
    assert predict_rows([{'text':''}], manifest, tokenizer, session) == [[]]
    assert score_rows([], manifest, tokenizer, session).shape == (0, len(LABELS))
