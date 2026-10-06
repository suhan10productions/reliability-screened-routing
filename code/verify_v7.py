"""Integrity gate for retained records, not a new performance experiment."""
from pathlib import Path
import json
import math
from relscreen_v6 import ModelParams,RoutingSolver,make_synthetic_instance,normalized_score,ScenarioBank,SpeedProfile
from relscreen_v7 import certificate,contracted_data,evaluate,plan_from_dict

ROOT=Path(__file__).resolve().parents[1]


def main():
    old={r['instance_seed']:r for n in (20,50,100,200)
         for r in json.loads((ROOT/f'results/study_v6_n{n}.json').read_text())['records']}
    records=[json.loads(p.read_text()) for p in sorted((ROOT/'results/v7').glob('instance_*.json'))]
    assert len(records)==53 and {r['instance_seed'] for r in records}==set(old)
    params=ModelParams();profile=SpeedProfile();configurations=0
    for r in records:
        seed=r['instance_seed'];source=old[seed]
        assert r['screening_seed']==100000+seed
        assert r['validation_seed']==400000+seed
        assert r['sensitivity_seed']==500000+seed
        assert len({r['screening_seed'],r['validation_seed'],r['sensitivity_seed']})==3
        data=make_synthetic_instance(r['customers'],r['vehicles_available'],seed)
        ranges=(source['reference_ranges']['lower'],source['reference_ranges']['upper'])
        for name in ('screened_conservative','capped_procedure'):
            candidates=r[name]['candidates'];selected=r[name]['selected_plan']
            passing=[c for c in candidates if c['screening'] and c['screening']['service_level_lcb']>=.95]
            assert bool(passing)==(selected is not None)
            if selected:
                key=(lambda c:(c['plan']['metrics']['distance'],c['plan']['metrics']['driver_duration'],c['beta'])) if name=='screened_conservative' else (lambda c:(normalized_score(plan_from_dict(c['plan']),ranges,params),c['beta']))
                assert selected==min(passing,key=key)['plan']
            for c in candidates:
                for proof in c['certificate']:
                    assert proof['upper']<proof['earliest_lower_bound']
                    assert c['plan'] is None
                if name=='capped_procedure':
                    cd=contracted_data(data,params,c['beta'],capped=True)
                    assert all(lo<=hi<=data.offered_windows[i][1] for i,(lo,hi) in enumerate(cd.offered_windows))
                if c['plan']:
                    visits=[i for route in c['plan']['routes'] for i in route if i]
                    assert sorted(visits)==list(range(1,r['customers']+1))
                    assert all(sum(data.demands[i] for i in route)<=params.capacity for route in c['plan']['routes'])
                    speed=params.nominal_speed_kmh/1.2 if name=='screened_conservative' else None
                    cd=contracted_data(data,params,c['beta'],capped=name=='capped_procedure',speed=speed)
                    matrix=RoutingSolver(cd,params,planning_speed_kmh=speed)._nominal_time
                    for i,start in c['plan']['service_starts'].items():
                        lo,hi=cd.offered_windows[int(i)]
                        assert lo<=start<=hi
                    for ridx,route in enumerate(c['plan']['routes']):
                        if len(route)<=2:continue
                        t=c['plan']['departures'][ridx]
                        for i,j in zip(route[:-1],route[1:]):
                            t+=matrix[i][j]
                            if j:
                                start=c['plan']['service_starts'][str(j)]
                                assert start+1e-9>=t
                                t=start+params.service_minutes
                        assert t<=params.shift_length+1e-9
        for c,record in r['configurations'].items():
            if record is None:continue
            configurations+=1
            v=record['validation']
            assert v['scenarios']==5000
            assert abs(v['expected_late_customers']/r['customers']+v['mean_on_time_fraction']-1)<1e-12
            assert 0<=v['service_level_lcb']<=v['service_level_success']<=1
            assert len(record['sensitivity'])==9
            if c in ('conservative','clock_aware'):
                assert record['deterministic']['mean_on_time_fraction']==1
        assert r['configurations']['fleet_matched']['plan']['metrics']['fleet']==r['configurations']['slack']['plan']['metrics']['fleet']
        # Original-bank agreement demonstrates evaluator change is not a source
        # of the new primary numbers; fresh seeds are the intended difference.
        for c,key in [('nominal','static'),('slack','weighted_objective_only')]:
            bank=ScenarioBank(5000,source['validation_seed'],params)
            v=evaluate(plan_from_dict(source[key]['plan']),data,params,profile,bank)
            for field in ('service_level_success','mean_on_time_fraction','expected_late_customers','mean_total_lateness'):
                assert math.isclose(v[field],source[key]['validation'][field],abs_tol=1e-9)
    report={'status':'passed','instances':53,'configurations_checked':configurations,
            'checks':['seed isolation','selected-plan ordering','capacity and visits',
            'contraction promises','reachability certificates','deterministic guarantee',
            'exact fleet matching','nine-cell sensitivity completeness','scalar/archive agreement']}
    (ROOT/'results/integrity_v7.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
