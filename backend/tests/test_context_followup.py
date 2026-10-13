import json
import hashlib
import os
from pathlib import Path

import numpy as np
import pytest

from backend.ml.context_data import expanded, load_cases
from backend.ml.context_sentences import sentence_units
from backend.ml.train_context_calibrated import combined_rows, select_label
from backend.ml.train_context_review import LABELS, predict

DATA = Path('evaluation/context-followup-cases.json')
ROWS = load_cases(DATA)


def test_new_source_families_and_contrast_pairs_stay_in_one_split():
    rows = combined_rows([Path('evaluation/context-source-cases.json'), DATA])
    assert len(rows) == 816
    source = json.loads(DATA.read_text())
    sources = {s['id']:s for s in source['sources']}
    assert len(sources) == 7
    for r in ROWS:
        if r['origin'] == 'public-source-paraphrase':
            assert r['family'] == r['source_id']
            assert sources[r['source_id']]['split'] == r['split']
            assert sources[r['source_id']]['url'].startswith('https://')
    split_by_text = {}
    for r in expanded(rows):
        text = ''.join(c.casefold() for c in r['text'] if c.isalnum())
        assert split_by_text.setdefault(text,r['split']) == r['split']
    assert {r['variant'] for r in expanded(ROWS)} == {'clean','deletion','transposition','duplication','joined','spacing','casing'}


def test_sentence_units_preserve_coordination_offsets_and_bounds():
    text = '🧭 Responsibilities:\r\n- Write application code, test the changes, and release the completed feature.\r\nBenefits:\r\nFree coaching in public speaking.'
    units = sentence_units(text)
    assert len(units) == 1
    assert 'code, test' in units[0]['text'] and 'release' in units[0]['text']
    assert all(text[u['start']:u['end']] == u['text'] for u in units)
    long = 'Write application code for the website.\n' * 100 + 'Resolve customers concerns about their purchases.'
    units = sentence_units(long)
    assert len(units) == 48 and units[-1]['text'].startswith('Resolve')
    assert all(long[u['start']:u['end']] == u['text'] for u in units)
    assert sentence_units('We do not require programming, testing software or deploying releases.') == []
    assert sentence_units('Official title: Chief Wizard of Customer Happiness.') == []


def test_per_label_thresholds_and_empty_documents():
    vectors = np.ones((1,384))
    weights = np.zeros((384,len(LABELS)))
    bias = np.full(len(LABELS),.5)
    thresholds = np.ones(len(LABELS))
    thresholds[0] = .4
    assert predict(vectors,[(0,1),(1,1)],weights,bias,thresholds) == [[LABELS[0]],[]]
    assert len(predict(vectors,[(0,1)],weights,bias,.4)[0]) == 6
    assert predict(vectors,[(0,1)],weights,np.full(len(LABELS),100.),2.) == [[]]
    thresholds = np.full(len(LABELS),2.)
    thresholds[-1] = .4
    assert predict(vectors,[(0,1)],weights,np.full(len(LABELS),100.),thresholds) == [[LABELS[-1]]]


def test_calibration_needs_clean_support_not_copies_of_one_example():
    scores = np.full(30,.8)
    wanted = allowed = np.ones(30,dtype=bool)
    clean = np.zeros(30,dtype=bool)
    clean[0] = True
    _,_,summary = select_label(scores,wanted,allowed,clean)
    assert not summary['supported']
    clean[:3] = True
    _,_,summary = select_label(scores,wanted,allowed,clean)
    assert summary['supported']


def test_classifier_rejects_unknown_architecture_before_loading_files(tmp_path):
    from backend.ml.evaluate_context_transformer import load_model
    (tmp_path/'manifest.json').write_text(json.dumps({'architecture':'unknown'}))
    with pytest.raises(ValueError,match='Unsupported'):
        load_model(tmp_path)


@pytest.mark.skipif(os.getenv('RUN_FOLLOWUP_HEAD_TESTS') != '1',reason='Requires exported follow-up heads')
@pytest.mark.parametrize('root,report,extra',[
    ('context-head-sentences-v1','context-sentence-results.json',False),
    ('context-head-calibrated-v2','context-calibrated-results.json',True),
])
def test_followup_head_exports_reproduce_clean_predictions(root,report,extra):
    from backend.app.services.semantic_matcher import _load_model
    from backend.ml.train_context_review import embed_cases,metrics
    root=Path('.models')/root
    manifest=json.loads((root/'manifest.json').read_text())
    assert hashlib.sha256((root/'weights.npz').read_bytes()).hexdigest()==manifest['sha256']
    assert manifest['labels']==LABELS and manifest['unitizer']=='sentences-v1'
    paths=[Path('evaluation/context-source-cases.json')]+([DATA] if extra else [])
    rows=[r for r in expanded(combined_rows(paths)) if r['split']=='test' and r['variant']=='clean']
    vectors,ranges=embed_cases(rows,_load_model()[0],sentence_units)
    with np.load(root/'weights.npz',allow_pickle=False) as artifact:
        weights,bias=artifact['weights'],artifact['bias']
    assert weights.shape==(384,len(LABELS)) and bias.shape==(len(LABELS),)
    assert np.isfinite(weights).all() and np.isfinite(bias).all()
    actual=metrics(rows,predict(vectors,ranges,weights,bias,manifest['threshold']))
    recorded=json.loads((Path('evaluation')/report).read_text())
    assert actual==recorded['evaluations']['test-clean']['candidate']


@pytest.mark.skipif(os.getenv('RUN_DUTY_HEAD_TESTS') != '1',reason='Requires exported duty classifier')
def test_exported_classifier_is_batch_invariant_and_reproduces_clean_results():
    from backend.ml.evaluate_context_transformer import load_model,predict_rows
    from backend.ml.train_context_review import metrics
    manifest,tokenizer,session=load_model(Path('.models/context-transformer-v1'))
    rows=combined_rows([Path('evaluation/context-source-cases.json'),DATA])
    clean=[r for r in expanded(rows) if r['split']=='test' and r['variant']=='clean']
    actual=predict_rows(clean,manifest,tokenizer,session)
    recorded=json.loads(Path('evaluation/context-transformer-results.json').read_text())
    assert metrics(clean,actual)==recorded['evaluations']['test-clean']['candidate']
    probes=[{'text':'Write application code and implement software features.'},
            {'text':'Benefits:\nOptional programming workshops.'},
            {'text':'Respond calmly to customer complaints and resolve problems with their accounts.'}]
    together=predict_rows(probes,manifest,tokenizer,session)
    assert together==[predict_rows([r],manifest,tokenizer,session)[0] for r in probes]
    assert together[1]==[]
    assert predict_rows([],manifest,tokenizer,session)==[]


@pytest.mark.skipif(os.getenv('RUN_CONTEXT_STRESS_TESTS') != '1',reason='Requires local models')
@pytest.mark.parametrize('case',expanded([r for r in ROWS if r['split']=='test']),ids=lambda r:r['id'])
def test_followup_inputs_keep_review_separate_from_scoring(client,case):
    from backend.tests.test_context_source_data import test_new_source_inputs_through_preview
    test_new_source_inputs_through_preview(client,case)
