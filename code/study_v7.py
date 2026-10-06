"""Fixed-protocol v7 experiments, checkpointed separately per instance."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time
import traceback

from relscreen_v6 import ModelParams, ScenarioBank, SpeedProfile, make_synthetic_instance, environment_metadata
from relscreen_v7 import audit_old_failure, clock_aware, evaluate, plan_from_dict, screen_generator


def run(record, output, seconds):
    seed=record['instance_seed']; n=record['customers']
    destination=Path(output)/f'instance_{seed}.json'
    if destination.exists():
        return seed,'checkpoint exists'
    started=time.perf_counter()
    params=ModelParams(); profile=SpeedProfile()
    data=make_synthetic_instance(n,record['vehicles_available'],seed)
    rr=record['reference_ranges']
    ranges=None if rr is None else (rr['lower'],rr['upper'])
    screen=ScenarioBank(1000,100000+seed,params)
    # Distance screening needs no scaling ranges; the weighted capped family does.
    conservative=screen_generator(data,params,profile,ranges,screen,record,conservative=True,seconds=seconds)
    if ranges is None:
        capped={'candidates':[],'selected_plan':None,'procedure_plan':None,
                'procedure_source':'not_attempted: anchors returned no plan',
                'best_beta':None,'best_lcb':None}
    else:
        capped=screen_generator(data,params,profile,ranges,screen,record,capped=True,seconds=seconds)
    if record['static']['plan'] is None:
        clock={'plan':None,'iterations':[],'status':'not_attempted: nominal plan absent'}
    else:
        clock=clock_aware(data,params,profile,record,total_seconds=seconds)
    # Only after all choices are fixed is a new validation bank instantiated.
    bank=ScenarioBank(5000,400000+seed,params)
    configs={
        'nominal':record['static']['plan'],
        'conservative':record['peak_aware_distance']['plan'],
        'slack':record['weighted_objective_only']['plan'],
        'fleet_matched':record['fleet_matched_distance']['plan'],
        'procedure':record['screened']['selected_plan'] or record['weighted_objective_only']['plan'],
        'screened_conservative':conservative['procedure_plan'],
        'capped_procedure':capped['procedure_plan'],
        'clock_aware':clock['plan'],
    }
    s1=record['configuration_status']
    def _why(raw,reason):
        return 'ok' if raw is not None else reason
    status={
        'nominal':_why(configs['nominal'],s1['static']),
        'conservative':_why(configs['conservative'],s1['peak_aware_distance']),
        'slack':_why(configs['slack'],s1['weighted_objective_only']),
        'fleet_matched':_why(configs['fleet_matched'],s1['fleet_matched_distance']),
        'procedure':_why(configs['procedure'],
            'not_attempted: anchors returned no plan' if ranges is None
            else 'no_plan: no screen-selected plan and slack-aware fallback absent'),
        'screened_conservative':_why(configs['screened_conservative'],
            'no_plan: no screen-selected plan and no conservative or slack-aware fallback'),
        'capped_procedure':_why(configs['capped_procedure'],
            capped['procedure_source'] if capped['procedure_source'].startswith('not_attempted')
            else 'no_plan: no screen-selected plan and slack-aware fallback absent'),
        'clock_aware':_why(configs['clock_aware'],clock.get('status','no_plan: no deterministically feasible schedule found')),
    }
    evaluations={}
    for name,raw in configs.items():
        if raw is None:
            evaluations[name]=None; continue
        plan=plan_from_dict(raw)
        evaluations[name]={'plan':raw,'validation':evaluate(plan,data,params,profile,bank),
            'deterministic':evaluate(plan,data,replace(params,sigma=0.),profile,ScenarioBank(1,400000+seed,replace(params,sigma=0.))),
            'sensitivity':{}}
    for sigma in (.1,.2,.3):
        for rho in (0.,.5,.9):
            p=replace(params,sigma=sigma,rho_log=rho)
            sb=ScenarioBank(1000,500000+seed,p)
            for name,raw in configs.items():
                if raw is not None:
                    evaluations[name]['sensitivity'][f'{sigma:.2f},{rho:.1f}']=evaluate(plan_from_dict(raw),data,p,profile,sb)
    result={
        'schema':'routeops-v7-instance-1','instance_seed':seed,'customers':n,
        'vehicles_available':record['vehicles_available'],
        'environment':environment_metadata(),'candidate_seconds':seconds,
        'screening_seed':100000+seed,'validation_seed':400000+seed,'sensitivity_seed':500000+seed,
        'old_failure_audit':audit_old_failure(record,data,params),
        'screened_conservative':conservative,'capped_procedure':capped,'clock_aware':clock,
        'configurations':evaluations,'configuration_status':status,
        'elapsed_seconds':time.perf_counter()-started,
        'source_record_sha256':hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest(),
    }
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2))
    return seed,{
        'n':n,'conservative_selected':conservative['selected_plan'] is not None,
        'capped_selected':capped['selected_plan'] is not None,
        'clock_found':clock['plan'] is not None,'elapsed':round(result['elapsed_seconds'],1),
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--inputs',nargs='+',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('results/v7'))
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--seconds',type=float,default=5.)
    args=parser.parse_args()
    records=[]
    for path in args.inputs: records.extend(json.loads(path.read_text())['records'])
    if args.limit: records=records[:args.limit]
    args.output.mkdir(parents=True,exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run,r,str(args.output),args.seconds):r for r in records}
        for future in as_completed(futures):
            r=futures[future]
            try:print(future.result(),flush=True)
            except Exception as exc:  # noqa: BLE001 - recorded, never scored
                # No-plan outcomes are recorded per configuration inside run().
                # Anything reaching here is a software error: recorded with its
                # traceback, never scored. Confirmatory analysis refuses to run
                # while any software_error file exists.
                (args.output/f"software_error_{r['instance_seed']}.json").write_text(json.dumps(
                    {'customers':r['customers'],'instance_seed':r['instance_seed'],'stage':2,
                     'error':f'{type(exc).__name__}: {exc}',
                     'traceback':''.join(traceback.format_exception(exc))},indent=2))
                print(f"seed={r['instance_seed']} SOFTWARE ERROR in stage 2: {exc}",flush=True)


if __name__=='__main__':main()
