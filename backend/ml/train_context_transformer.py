"""Fine-tune a local encoder for duty classification; export a review candidate.

By default the lower four transformer layers stay frozen. Upper layers and the classifier
learn from recruitment prose, task labels and typo variants. Test descriptions
are not used for epoch or threshold selection.
"""

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import random
import shutil
import time

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')

import numpy as np
import onnxruntime as ort
from safetensors.torch import load_file, save_file
import torch
from torch import nn
from transformers import AutoTokenizer, DistilBertModel

from backend.ml.context_data import expanded
from backend.ml.context_sentences import UNITIZERS
from backend.ml.train_context_calibrated import combined_rows
from backend.ml.train_context_review import LABELS, metrics, write_report

BASE_REVISION = '12040accade4e8a0f71eabdb258fecc2e7e948be'
BASE = Path('.models/hf-cache/models--distilbert--distilbert-base-uncased/snapshots') / BASE_REVISION


class DutyClassifier(nn.Module):
    def __init__(self, frozen_layers=4):
        super().__init__()
        self.encoder = DistilBertModel.from_pretrained(BASE, local_files_only=True, attn_implementation='eager')
        for p in self.encoder.embeddings.parameters():
            p.requires_grad = False
        for layer in self.encoder.transformer.layer[:frozen_layers]:
            for p in layer.parameters():
                p.requires_grad = False
        self.dropout = nn.Dropout(.2)
        self.classifier = nn.Linear(self.encoder.config.dim,len(LABELS))

    def forward(self,input_ids,attention_mask):
        hidden = self.encoder(input_ids=input_ids,attention_mask=attention_mask).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden*mask).sum(1) / mask.sum(1).clamp(min=1)
        return self.classifier(self.dropout(pooled))


def predictions(scores,threshold):
    return [[LABELS[j] for j in np.argsort(-row)[:6] if row[j]>=threshold] for row in scores]


def run(output,report_path,epochs=12, *, curriculum=False, frozen_layers=4, unitizer='sentences-v1'):
    if output.exists():
        raise ValueError('Choose a fresh output directory')
    seed=20261013
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    paths=[Path('evaluation/context-source-cases.json'),Path('evaluation/context-followup-cases.json')]
    if curriculum:
        paths.append(Path('evaluation/context-curriculum-cases.json'))
    data_hashes={str(p):hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest() for p in paths}
    rows=combined_rows(paths)
    train=expanded([r for r in rows if r['split']=='train'])
    dev=expanded([r for r in rows if r['split']=='dev'])
    tokenizer=AutoTokenizer.from_pretrained(BASE,local_files_only=True)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model=DutyClassifier(frozen_layers).to(device)
    max_length = 256 if unitizer == 'paragraphs-v2' else 160
    optimizer=torch.optim.AdamW([
        {'params':[p for p in model.encoder.parameters() if p.requires_grad],'lr':2e-5},
        {'params':model.classifier.parameters(),'lr':1e-3}],weight_decay=.01)
    y=torch.tensor([[float(label in r['expected']+r['acceptable']) for label in LABELS] for r in train])
    positives=y.sum(0)
    criterion=nn.BCEWithLogitsLoss(pos_weight=((len(y)-positives)/positives.clamp(min=1)).sqrt().clamp(max=8).to(device))
    encoded=tokenizer([r['text'] for r in train],padding=True,truncation=True,max_length=max_length,return_tensors='pt')
    dev_texts, ranges=[],[]
    for row in dev:
        start=len(dev_texts)
        dev_texts.extend(u['text'] for u in UNITIZERS[unitizer](row['text']))
        ranges.append((start,len(dev_texts)))
    dv=tokenizer(dev_texts,padding=True,truncation=True,max_length=max_length,return_tensors='pt')
    output.mkdir(parents=True)
    report={'scope':'Project labels and occupational weak supervision. Unfrozen encoder layers and a 24-label classifier are fine-tuned. No test selection.',
        'seed':seed,'device':str(device),'gpu':torch.cuda.get_device_name(0) if device.type=='cuda' else None,
        'train_rows':len(train),'development_rows':len(dev),'epochs':[],
        'config':{'epochs':epochs,'batch_size':24,'max_length':max_length,'encoder_learning_rate':2e-5,
            'classifier_learning_rate':1e-3,'weight_decay':.01,'dropout':.2,'frozen_lower_layers':frozen_layers,'unitizer':unitizer},
        'versions':{name:version(name) for name in ('torch','transformers','tokenizers','onnxruntime','numpy')},
        'trained_parameters':sum(p.numel() for p in model.parameters() if p.requires_grad)}
    best=None
    for epoch in range(1,epochs+1):
        start=time.perf_counter()
        model.train()
        order=torch.randperm(len(train))
        losses=[]
        for batch in order.split(24):
            args={k:v[batch].to(device) for k,v in encoded.items()}
            optimizer.zero_grad(set_to_none=True)
            logits=model(**args)
            loss=criterion(logits,y[batch].to(device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            optimizer.step()
            losses.append(loss.item())
        model.eval()
        values=[]
        with torch.inference_mode():
            for a in range(0,len(dev_texts),48):
                values.append(torch.sigmoid(model(**{k:v[a:a+48].to(device) for k,v in dv.items()})).cpu().numpy())
        values=np.concatenate(values)
        scores=np.array([values[a:b].max(0) if b>a else np.zeros(len(LABELS)) for a,b in ranges])
        selected=None
        for threshold in np.arange(.3,.951,.025):
            predicted=predictions(scores,threshold)
            result=metrics(dev,predicted)
            rank=(result['precision']>=.9,result['f0_5'],result['precision'],threshold)
            if selected is None or rank>selected[0]:
                selected=(rank,float(threshold),{k:v for k,v in result.items() if k!='results'})
        rank,threshold,result=selected
        report['epochs'].append({'epoch':epoch,'loss':float(np.mean(losses)),'seconds':round(time.perf_counter()-start,2),'threshold':threshold,'development':result})
        if best is None or rank>best:
            best=rank
            report['selected_epoch']=epoch
            report['threshold']=threshold
            save_file({k:v.detach().cpu().contiguous() for k,v in model.state_dict().items()},output/'model.safetensors')
            np.savez_compressed(output/'development-scores.npz',scores=scores,ids=np.array([r['id'] for r in dev]))
        print(report['epochs'][-1],flush=True)
        write_report(report_path,report)
    model.load_state_dict(load_file(output/'model.safetensors'))
    model.cpu().eval()
    sample={k:v[:2,:32] for k,v in encoded.items()}
    torch.onnx.export(model,(sample['input_ids'],sample['attention_mask']),str(output/'model.onnx'),
        input_names=['input_ids','attention_mask'],output_names=['logits'],
        dynamic_axes={'input_ids':{0:'batch',1:'sequence'},'attention_mask':{0:'batch',1:'sequence'},'logits':{0:'batch'}},opset_version=17,dynamo=False)
    tokenizer.backend_tokenizer.save(str(output/'tokenizer.json'))
    license_path=BASE/'LICENSE'
    if not license_path.is_file():
        license_path=Path('.models/skillspan-distilbert/BASE-MODEL-LICENSE')
    if not license_path.is_file():
        raise ValueError('The cached base-model license is required for the export')
    shutil.copyfile(license_path,output/'BASE-MODEL-LICENSE')
    options=ort.SessionOptions()
    options.intra_op_num_threads=2
    session=ort.InferenceSession(str(output/'model.onnx'),options,providers=['CPUExecutionProvider'])
    with torch.inference_mode():
        expected=model(**sample).numpy()
    actual=session.run(None,{k:v.numpy() for k,v in sample.items()})[0]
    np.testing.assert_allclose(actual,expected,rtol=1e-3,atol=1e-4)
    report['export_max_absolute_error']=float(np.abs(actual-expected).max())
    if data_hashes!={str(p):hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest() for p in paths}:
        raise ValueError('Training data changed during the run; do not release this export')
    manifest={'architecture':'distilbert-duty-classifier','base_revision':BASE_REVISION,'labels':LABELS,'max_length':max_length,
        'unitizer':unitizer,'threshold':report['threshold'],'selected_epoch':report['selected_epoch'],
        'data_sha256':data_hashes,
        'sha256':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ('model.onnx','tokenizer.json')},
        'status':'candidate; not loaded by the application'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    report['manifest']=manifest
    write_report(report_path,report)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=Path('.models/context-transformer-v1'))
    p.add_argument('--report',type=Path,default=Path('evaluation/context-transformer-training.json'))
    p.add_argument('--epochs',type=int,default=12)
    p.add_argument('--curriculum',action='store_true')
    p.add_argument('--frozen-layers',type=int,choices=range(7),default=4)
    p.add_argument('--unitizer',choices=UNITIZERS,default='sentences-v1')
    args=p.parse_args()
    run(args.output,args.report,args.epochs,curriculum=args.curriculum,frozen_layers=args.frozen_layers,unitizer=args.unitizer)
