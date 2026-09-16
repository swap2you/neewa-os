#!/usr/bin/env python3
"""Deterministic NEEWA model/resource router."""
from __future__ import annotations
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; QUALITY={"basic":0,"balanced":1,"premium":2,"exceptional":3}; COST={"free-local":0,"subscription":1,"paid":2}
def load_models(path=ROOT/'11_CONFIG/models.json'): return json.loads(Path(path).read_text())['models']
def route(risk='low',privacy='standard',quality='basic',online=True,models=None):
 models=models or load_models(); candidates=[]
 for m in models:
  if m.get('availability')!='verified': continue
  if not online and m.get('location')!='local': continue
  if privacy=='local-only' and m.get('location')!='local': continue
  if QUALITY.get(m.get('quality_class'),-1)<QUALITY[quality]: continue
  candidates.append(m)
 if not candidates:return {'status':'BLOCKED','reason':'no eligible verified model'}
 if risk in {'high','critical'} and privacy!='local-only' and online:
  premium=[m for m in candidates if QUALITY.get(m.get('quality_class'),-1)>=2]
  if premium:candidates=premium
 candidates.sort(key=lambda m:(COST.get(m.get('cost_class'),9),m.get('fallback_priority',99)))
 c=candidates[0]; return {'status':'ROUTED','model_id':c['id'],'provider':c['provider'],'model':c['model'],'reason':f'least-cost verified match for risk={risk}, privacy={privacy}, quality={quality}, online={online}'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--risk',choices=['low','medium','high','critical'],default='low');p.add_argument('--privacy',choices=['standard','local-only'],default='standard');p.add_argument('--quality',choices=list(QUALITY),default='basic');p.add_argument('--offline',action='store_true');a=p.parse_args();r=route(a.risk,a.privacy,a.quality,not a.offline);print(json.dumps(r,indent=2));return 0 if r['status']=='ROUTED' else 2
if __name__=='__main__':raise SystemExit(main())
