"""Evaluate a fixed exported duty classifier against frozen regression sets."""

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from backend.ml.context_data import expanded, load_cases
from backend.ml.context_sentences import sentence_units
from backend.ml.train_context_calibrated import combined_rows
from backend.ml.train_context_review import LABELS, baseline, metrics, write_report


def load_model(root):
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest['architecture']!='distilbert-duty-classifier' or manifest['labels']!=LABELS or manifest['unitizer']!='sentences-v1':
        raise ValueError('Unsupported duty classifier')
    if not .0 < manifest['threshold'] <= 1 or manifest['max_length']!=160:
        raise ValueError('Invalid classifier settings')
    for name in ('model.onnx','tokenizer.json'):
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=manifest['sha256'][name]:
            raise ValueError('Duty classifier checksum mismatch')
    tokenizer=Tokenizer.from_file(str(root/'tokenizer.json'))
    tokenizer.enable_truncation(max_length=manifest['max_length'])
    tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
    options=ort.SessionOptions()
    options.intra_op_num_threads=2
    session=ort.InferenceSession(str(root/'model.onnx'),options,providers=['CPUExecutionProvider'])
    return manifest,tokenizer,session


def predict_rows(rows,manifest,tokenizer,session):
    texts,ranges=[],[]
    for row in rows:
        start=len(texts)
        texts.extend(u['text'] for u in sentence_units(row['text']))
        ranges.append((start,len(texts)))
    values=[]
    for start in range(0,len(texts),16):
        encoded=tokenizer.encode_batch(texts[start:start+16])
        logits=session.run(None,{'input_ids':np.array([v.ids for v in encoded],dtype=np.int64),
            'attention_mask':np.array([v.attention_mask for v in encoded],dtype=np.int64)})[0]
        if logits.shape!=(len(encoded),len(LABELS)) or not np.isfinite(logits).all():
            raise ValueError('Invalid duty classifier output')
        values.extend(1/(1+np.exp(-np.clip(logits,-60,60))))
    values=np.asarray(values)
    results=[]
    for start,end in ranges:
        scores=values[start:end].max(0) if end>start else np.zeros(len(LABELS))
        results.append([LABELS[j] for j in np.argsort(-scores)[:6] if scores[j]>=manifest['threshold']])
    return results


def run(root,report_path):
    manifest,tokenizer,session=load_model(root)
    for name,digest in manifest['data_sha256'].items():
        if hashlib.sha256(Path(name).read_text(encoding='utf-8').encode()).hexdigest()!=digest:
            raise ValueError('Training corpus changed since the classifier was exported')
    rows=combined_rows([Path('evaluation/context-source-cases.json'),Path('evaluation/context-followup-cases.json')])
    test=expanded([r for r in rows if r['split']=='test'])
    groups={'test-all':test,'test-clean':[r for r in test if r['variant']=='clean']}
    for origin in sorted({r['origin'] for r in test}):
        groups['test-origin-'+origin]=[r for r in test if r['origin']==origin]
    for variant in sorted({r['variant'] for r in test}):
        groups['test-variant-'+variant]=[r for r in test if r['variant']==variant]
    followup=expanded([r for r in load_cases(Path('evaluation/context-followup-cases.json')) if r['split']=='test'])
    groups['new-employer-test']=[r for r in followup if r['origin']=='public-source-paraphrase']
    groups['new-authored-test']=[r for r in followup if r['origin']=='project-authored']
    groups['previous-regressions']=sum([json.loads(Path(f'evaluation/{name}.json').read_text())['cases'] for name in ('context-cases','context-holdout')],[])
    groups['previous-test-regressions']=expanded([r for r in load_cases(Path('evaluation/context-training-cases.json')) if r['split']=='test'])
    groups['additional-source-regressions']=expanded(load_cases(Path('evaluation/context-final-check.json')))
    old=json.loads(Path('evaluation/context-calibrated-results.json').read_text())['evaluations']
    report={'scope':'Fixed encoder candidate evaluated on project-labelled regression descriptions. Source labels may be incomplete. Scope guard compared with pre-change baseline. Test variants are correlated.',
        'manifest':manifest,'evaluations':{}}
    all_rows={r['id']:r for selected in groups.values() for r in selected}
    rows=list(all_rows.values())
    started=time.perf_counter()
    all_predictions=predict_rows(rows,manifest,tokenizer,session)
    report['cpu_seconds']=round(time.perf_counter()-started,3)
    report['unique_cases']=len(rows)
    lookup=dict(zip(all_rows,all_predictions,strict=True))
    current=dict(zip(all_rows,baseline(rows),strict=True))
    for name,selected in groups.items():
        if [r['id'] for r in selected]!=[r['id'] for r in old[name]['baseline']['results']]:
            raise ValueError('Frozen baseline does not match evaluation cases')
        report['evaluations'][name]={'baseline':old[name]['baseline'],
            'scope-guard':metrics(selected,[current[r['id']] for r in selected]),
            'candidate':metrics(selected,[lookup[r['id']] for r in selected])}
        print(name,{m:{k:v for k,v in result.items() if k in ('precision','coverage','negative_errors')} for m,result in report['evaluations'][name].items()},flush=True)
    failures=[]
    for name,results in report['evaluations'].items():
        a,b=results['candidate'],results['baseline']
        if not(a['precision']>=max(.9,b['precision']) and a['coverage']>=b['coverage'] and a['negative_errors']<=b['negative_errors']):
            failures.append(name)
    report['promotion_gate']={'passed':not failures,'failed_sets':failures,
        'rule':'Precision >= max(90%, baseline), coverage >= baseline, negative errors <= baseline on every evaluated set. No automatic deployment.'}
    write_report(report_path,report)
    print(report['promotion_gate'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--model',type=Path,default=Path('.models/context-transformer-v1'))
    p.add_argument('--report',type=Path,default=Path('evaluation/context-transformer-results.json'))
    args=p.parse_args()
    run(args.model,args.report)
