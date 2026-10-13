"""Compare duty classification with per-capability development calibration.

Frozen sentence embeddings feed 24 weighted ridge outputs. All model choices
use development descriptions. Earlier tests remain regression sets, and new
employer families are split before fitting. No model is installed by this file.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from backend.app.services.model_assets import MODEL_REVISION
from backend.app.services.semantic_matcher import _load_model
from backend.ml.context_data import expanded, load_cases
from backend.ml.context_sentences import sentence_units
from backend.ml.train_context_review import LABELS, baseline, balanced_weights, embed_cases, fit, metrics, predict, write_report


def select_label(scores, wanted, allowed, clean):
    """Choose a review threshold, requiring independent clean examples too.

    Spelling variants are correlated: three clean true positives are required
    for a supported operating point. Labels without enough evidence abstain.
    """
    best = None
    for threshold in np.arange(.25, .851, .025):
        selected = scores >= threshold
        true = int((selected & wanted).sum())
        extra = int((selected & ~allowed).sum())
        count = int(selected.sum())
        precision = (count - extra) / max(count, 1)
        clean_count = int((selected & clean).sum())
        clean_true = int((selected & wanted & clean).sum())
        clean_precision = int((selected & allowed & clean).sum()) / max(clean_count, 1)
        recall = true / max(int(wanted.sum()), 1)
        f = 1.25 * precision * recall / max(.25 * precision + recall, 1e-12)
        eligible = precision >= .9 and clean_precision >= .9 and clean_true >= 3
        rank = (eligible, f, precision, threshold)
        item = (rank, float(threshold), {"precision":precision,"coverage":recall,
            "clean_true_positives":clean_true,"clean_precision":clean_precision,"supported":eligible})
        if best is None or rank > best[0]:
            best = item
    return best


def combined_rows(paths):
    rows = [row for path in paths for row in load_cases(path)]
    ids, families, texts = set(), {}, {}
    for row in rows:
        if row["id"] in ids:
            raise ValueError("Duplicate training identifier")
        ids.add(row["id"])
        for mapping,key in ((families,row["family"]),(texts," ".join(row["text"].casefold().split()))):
            if mapping.setdefault(key,row["split"]) != row["split"]:
                raise ValueError("Related descriptions cross training splits")
    return rows


def run(paths, output, report_path):
    if output.exists():
        raise ValueError("Choose a fresh output directory")
    rows = combined_rows(paths)
    splits = {s:expanded([r for r in rows if r["split"] == s]) for s in ("train","dev","test")}
    encoder = _load_model()[0]
    train, dev = splits["train"], splits["dev"]
    x = np.asarray(list(encoder.embed([r["text"] for r in train], batch_size=32)), dtype=np.float64)
    targets = np.array([[float(label in r["expected"] + r["acceptable"]) for label in LABELS] for r in train])
    dv, dr = embed_cases(dev, encoder, sentence_units)
    wanted = np.array([[label in r["expected"] for label in LABELS] for r in dev])
    allowed = np.array([[label in r["expected"] + r["acceptable"] for label in LABELS] for r in dev])
    clean = np.array([r["variant"] == "clean" for r in dev])
    choices = [None] * len(LABELS)
    # Occupational tasks are useful, but differ from actual recruitment prose.
    # Select their influence using development data rather than test recall.
    for balance in (False, True):
        base = balanced_weights(targets) if balance else np.ones(len(train))
        for source_weight in (.1, .3, 1.):
            sw = base * np.array([source_weight if r["origin"] == "onet-activity-crosswalk" else 1. for r in train])
            sw /= sw.mean()
            for alpha in (.1, 1., 10.):
                weights, bias = fit(x, targets, alpha, sw)
                unit_scores = dv @ weights + bias
                scores = np.array([unit_scores[a:b].max(axis=0) if b>a else np.full(len(LABELS),-1.) for a,b in dr])
                for j in range(len(LABELS)):
                    rank, threshold, summary = select_label(scores[:,j], wanted[:,j], allowed[:,j], clean)
                    if choices[j] is None or rank > choices[j][0]:
                        choices[j] = (rank, weights[:,j], bias[j], threshold, {"label":LABELS[j],"regularization":alpha,
                            "balanced_labels":balance,"occupational_weight":source_weight, **summary})
    weights = np.stack([c[1] for c in choices],axis=1)
    bias = np.array([c[2] for c in choices])
    thresholds = np.array([c[3] if c[4]["supported"] else 2. for c in choices])
    output.mkdir(parents=True)
    np.savez_compressed(output/'weights.npz', weights=weights, bias=bias)
    manifest = {"labels":LABELS,"encoder_revision":MODEL_REVISION,
        "sha256":hashlib.sha256((output/'weights.npz').read_bytes()).hexdigest(),
        "data_sha256":{str(p):hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest() for p in paths},
        "unitizer":"sentences-v1","threshold":thresholds.tolist(),"training_rows":len(train),
        "status":"candidate; not loaded by the application","selection":[c[4] for c in choices]}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Selected development settings; evaluating fixed model', flush=True)
    groups = {"dev-all":dev,"test-all":splits['test'],"test-clean":[r for r in splits['test'] if r['variant']=='clean']}
    for origin in sorted({r['origin'] for r in splits['test']}):
        groups['test-origin-'+origin] = [r for r in splits['test'] if r['origin']==origin]
    for variant in sorted({r['variant'] for r in splits['test']}):
        groups['test-variant-'+variant] = [r for r in splits['test'] if r['variant']==variant]
    groups['new-employer-test'] = [r for r in expanded(load_cases(paths[-1])) if r['split']=='test' and r['origin']=='public-source-paraphrase']
    groups['new-authored-test'] = [r for r in expanded(load_cases(paths[-1])) if r['split']=='test' and r['origin']=='project-authored']
    groups['previous-regressions'] = sum([json.loads(Path(f'evaluation/{name}.json').read_text())['cases'] for name in ('context-cases','context-holdout')],[])
    groups['previous-test-regressions'] = expanded([r for r in load_cases(Path('evaluation/context-training-cases.json')) if r['split']=='test'])
    groups['additional-source-regressions'] = expanded(load_cases(Path('evaluation/context-final-check.json')))
    report = {"scope":"Project annotations with occupational weak labels. All choices use development data, with at least three clean positive examples per enabled label. Prior test sets are reused regressions, not fresh blind tests.",
        "manifest":manifest,"base_counts":dict(Counter(r['split'] for r in rows)),
        "expanded_counts":{s:len(v) for s,v in splits.items()},"evaluations":{}}
    for name, selected in groups.items():
        vectors, ranges = embed_cases(selected,encoder,sentence_units)
        report['evaluations'][name] = {'baseline':metrics(selected,baseline(selected)),
            'candidate':metrics(selected,predict(vectors,ranges,weights,bias,thresholds))}
        print(name, {m:{k:v for k,v in result.items() if k in ('precision','coverage','negative_errors')} for m,result in report['evaluations'][name].items()}, flush=True)
    gates = [k for k in groups if k != 'dev-all']
    failures = []
    for name in gates:
        a,b = (report['evaluations'][name][key] for key in ('candidate','baseline'))
        if not (a['precision'] >= max(.9,b['precision']) and a['coverage'] >= b['coverage'] and a['negative_errors'] <= b['negative_errors']):
            failures.append(name)
    report['promotion_gate'] = {'passed':not failures,'failed_sets':failures,'evaluated_sets':gates,
        'rule':'Precision >= max(90%, baseline), coverage >= baseline, negative errors <= baseline on every evaluated set. No automatic deployment.'}
    write_report(report_path,report)
    print(report['promotion_gate'],flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data',nargs='+',type=Path,default=[Path('evaluation/context-source-cases.json'),Path('evaluation/context-followup-cases.json')])
    p.add_argument('--output',type=Path,default=Path('.models/context-head-calibrated-v2'))
    p.add_argument('--report',type=Path,default=Path('evaluation/context-calibrated-results.json'))
    args=p.parse_args()
    run(args.data,args.output,args.report)
