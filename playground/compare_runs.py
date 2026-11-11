"""Re-score retained baseline evidence without modifying the baseline artifacts."""
import argparse
from common import BENCHMARK,FIXTURES,read_json,write_json
from evaluate import score_page,evaluate


def summarize(engine,name):
    rows=[]
    for path in sorted((BENCHMARK/f"runs/{engine}/{name}").glob("sop_*/page_*/evidence.json")):
        status=read_json(path.with_name('status.json'))
        if status['state']!='success':continue
        pred=read_json(path)
        gt=read_json(FIXTURES/f'{path.parent.parent.name}.ground_truth.json')
        assert status['pdf_sha256']==gt['sha256']
        score=score_page(gt['pages'][status['page_number']-1],pred)
        rows.append(score)
    result=dict(engine=engine,run_name=name,pages=len(rows))
    for kind in ['table_detection','figure_detection','cell_text_evaluation']:
        keys=set(k for r in rows for k in r[kind])
        result[kind]={k:sum(r[kind].get(k,0) for r in rows) for k in keys}
    result['complete_grids_exact']=sum(t.get('span_grid_exact',False) for r in rows for t in r['table_matches'])
    result['nested_table_links']=sum(f['nested_explicit'] for r in rows for f in r['figure_matches'])
    result['cell_ownership_verified']=sum(f['cell_ownership_verified'] is True for r in rows for f in r['figure_matches'])
    result['cells_expected_03_mismatches']=[c for r in rows for t in r['table_matches'] for c in t.get('cell_text_checks',[])
        if c['expected']=='03' and c['predicted']!='03']
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run-name',default='refined_v1');args=ap.parse_args()
    output=dict(baseline=[summarize(e,'baseline') for e in ['docling','paddle']],
        refined=[summarize(e,args.run_name) for e in ['docling','paddle']],
        caveat='Same four authored page designs were used during rule development. No held-out generalization claim; exact text includes punctuation and Vietnamese accents.')
    write_json(BENCHMARK/f'experiments/{args.run_name}/comparison.json',output)
    print(__import__('json').dumps(output,ensure_ascii=False,indent=2))
