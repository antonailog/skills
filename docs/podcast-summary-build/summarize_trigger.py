"""Summarize observed first-step skill reads without reclassifying near misses."""
import json
from pathlib import Path
import statistics

BASE = Path(__file__).resolve().parent


def metrics(runs):
    valid = [r for r in runs if r['turn_completed'] and r['returncode'] == 0]
    tp = sum(r['expected'] and r['observed_skill_read'] for r in valid)
    fp = sum(not r['expected'] and r['observed_skill_read'] for r in valid)
    fn = sum(r['expected'] and not r['observed_skill_read'] for r in valid)
    tn = sum(not r['expected'] and not r['observed_skill_read'] for r in valid)
    total_tokens = [(r.get('usage') or {}).get('input_tokens',0)+(r.get('usage') or {}).get('output_tokens',0) for r in valid]
    return {'runs':len(runs),'completed':len(valid),'tp':tp,'fp':fp,'fn':fn,'tn':tn,
            'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,
            'accuracy':(tp+tn)/len(valid) if valid else None,
            'median_duration_ms':statistics.median(r['duration_ms'] for r in valid) if valid else None,
            'total_tokens':sum(total_tokens),'mean_tokens':statistics.mean(total_tokens) if valid else None,
            'mismatches':[{'id':r['id'],'run':r['run']} for r in valid if r['expected']!=r['observed_skill_read']]}


data=json.loads((BASE/'trigger-results.json').read_text())
summary={key:metrics([r for r in data if key=='all' or r['split']==key]) for key in ['all','train','test']}
summary['limits']='Controlled first-preparation-step read-only task, not a production routing rate. A successful SKILL.md read counts as a trigger even if the assistant later decides not to apply the workflow.'
(BASE/'trigger-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
