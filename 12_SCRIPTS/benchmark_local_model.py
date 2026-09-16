#!/usr/bin/env python3
"""Benchmark the loopback Ollama fallback with fixed probes."""
from __future__ import annotations
import argparse,json,time,urllib.request
from pathlib import Path
MODEL='qwen3:4b-instruct-2507-q4_K_M'; URL='http'+':'+'//'+'127.0.0.1'+':'+'11434/api/chat'; OPTIONS={'seed':42,'temperature':0,'top_p':1,'num_ctx':65536,'num_predict':128}
def invoke(messages,tools=None):
 body={'model':MODEL,'stream':False,'think':False,'messages':messages,'options':OPTIONS}
 if tools:body['tools']=tools
 req=urllib.request.Request(URL,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'});start=time.monotonic()
 with urllib.request.urlopen(req,timeout=600) as response:r=json.loads(response.read())
 pe=r.get('prompt_eval_duration') or 1;ee=r.get('eval_duration') or 1;m=r.get('message',{})
 return {'wall_seconds':round(time.monotonic()-start,3),'content':m.get('content',''),'tool_calls':m.get('tool_calls',[]),'prompt_tokens':r.get('prompt_eval_count',0),'output_tokens':r.get('eval_count',0),'prompt_tps':round(r.get('prompt_eval_count',0)/(pe/1e9),2),'output_tps':round(r.get('eval_count',0)/(ee/1e9),2),'load_seconds':round((r.get('load_duration') or 0)/1e9,3)}
def run():
 exact=invoke([{'role':'user','content':'Reply with exactly: NEEWA LOCAL READY'}]);tool={'type':'function','function':{'name':'get_system_mode','description':'Return NEEWA mode','parameters':{'type':'object','properties':{},'required':[]}}};call=invoke([{'role':'user','content':'Use the available tool to get the current system mode.'}],[tool]);tool_ok=bool(call['tool_calls']) and call['tool_calls'][0].get('function',{}).get('name')=='get_system_mode';return {'schema_version':1,'model':MODEL,'context':65536,'exact':exact,'tool_call':call,'acceptance':{'exact_output':exact['content'].strip()=='NEEWA LOCAL READY','tool_call_valid':tool_ok,'functional':exact['content'].strip()=='NEEWA LOCAL READY' and tool_ok}}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output');a=p.parse_args();r=run();text=json.dumps(r,indent=2)+'\n';print(text,end='');
 if a.output:o=Path(a.output);o.parent.mkdir(parents=True,exist_ok=True);o.write_text(text)
 return 0 if r['acceptance']['functional'] else 1
if __name__=='__main__':raise SystemExit(main())
