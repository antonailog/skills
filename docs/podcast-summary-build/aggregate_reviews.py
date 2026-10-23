"""Combine independent blind judgments with deterministic formatting checks."""
import json
from pathlib import Path
import statistics
import subprocess

BASE=Path(__file__).resolve().parent
key=json.loads((BASE/'runs/blind-key.json').read_text())
judges=[json.loads((BASE/f'runs/blind/judge-{n}.json').read_text()) for n in [1,2,3]]
objective=json.loads((BASE/'objective-results.json').read_text())
results={'with':[],'without':[]}
details=[]
for case,labels in key.items():
    for label,condition in labels.items():
        samples=[next(r for r in j['reviews'] if r['case']==case and r['label']==label) for j in judges]
        scores={criterion:statistics.median(s['scores'][criterion] for s in samples) for criterion in ['R1','R2','R3','R4','R5','R8']}
        obj=next(r for r in objective if r['case']==case and r['label']==label)
        scores.update(R6=obj['R6'],R7=obj['R7'])
        results[condition].append({'query_id':case,'run':1,'scores':scores})
        details.append({'case':case,'condition':condition,'anonymous_label':label,'scores':scores,
                        'total':sum(scores.values()),'normalized_100':round(sum(scores.values())/65*100,2),
                        'judge_ranges':{c:[min(s['scores'][c] for s in samples),max(s['scores'][c] for s in samples)] for c in ['R1','R2','R3','R4','R5','R8']}})
for condition,rows in results.items():
    (BASE/f'{condition}-scores.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
(BASE/'content-score-summary.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n')
proc=subprocess.run(['python3',str(BASE.parents[1]/'skills/skill-build/scripts/score_rubric.py'),
                     '--with',str(BASE/'with-scores.json'),'--without',str(BASE/'without-scores.json'),'--json'],
                    capture_output=True,text=True,check=True)
(BASE/'rubric-audit.json').write_text(proc.stdout)
print(json.dumps(details,ensure_ascii=False,indent=2))
