"""Extensions for the fixed v7 protocol; archived v6 core is unchanged."""
from __future__ import annotations

import math
import time
from dataclasses import replace
import numpy as np

from relscreen_v6 import (
    ModelParams, Plan, RoutingSolver, ScenarioBank, SpeedProfile,
    _evaluate_route, normalized_score, td_travel_minutes, wilson_lower_bound,
)
from extended_study_v6 import plan_from_dict


def vector_travel(distance, departure, profile):
    """Same integrated speed profile as the scalar evaluator, over scenarios."""
    departure = np.asarray(departure, dtype=float)
    current = departure.copy()
    remaining = np.full(current.shape, float(distance))
    for (_, end), speed in zip(profile.periods, profile.speeds_km_per_minute()):
        available = np.maximum(0.0, end - current) * speed
        traveled = np.minimum(remaining, available)
        current += traveled / speed
        remaining -= traveled
    current += remaining / profile.speeds_km_per_minute()[-1]
    return current - departure


def evaluate(plan, data, params, profile, bank):
    counts = np.zeros(bank.scenarios, dtype=int)
    lateness = np.zeros(bank.scenarios)
    durations = np.zeros(bank.scenarios)
    successes = np.zeros(bank.scenarios)
    late_clock_arc_count = 0
    used = 0
    for ridx, route in enumerate(plan.routes):
        if len(route) <= 2:
            continue
        used += 1
        now = np.full(bank.scenarios, plan.departures[ridx], dtype=float)
        route_late = np.zeros(bank.scenarios, dtype=int)
        for i, j in zip(route[:-1], route[1:]):
            clock = now + params.shift_start_minute
            late_clock_arc_count += int(np.sum(clock >= 1020))
            travel = vector_travel(data.distance[i][j], clock, profile)
            log_error = params.sigma * (
                math.sqrt(params.rho_log) * bank._global
                + math.sqrt(1-params.rho_log) * bank.local_errors((i,j))
            )
            now += travel * np.exp(log_error)
            if j:
                lo, hi = data.offered_windows[j]
                now = np.maximum(now, lo)
                delay = np.maximum(0.0, now-hi)
                route_late += delay > 1e-9
                lateness += delay
                now += params.service_minutes
        counts += route_late
        successes += route_late == 0
        durations += now-plan.departures[ridx]
    if not used:
        raise ValueError('empty plan')
    fraction = 1-counts/data.num_customers
    probability = float(np.mean(fraction >= params.kappa))
    return {
        'scenarios':bank.scenarios,
        'service_level_success':probability,
        'service_level_lcb':wilson_lower_bound(probability,bank.scenarios,params.eta),
        'mean_on_time_fraction':float(fraction.mean()),
        'expected_late_customers':float(counts.mean()),
        'mean_total_lateness':float(lateness.mean()),
        'mean_simulated_driver_duration':float(durations.mean()),
        'fleet_day_success':float(np.mean(counts==0)),
        'mean_route_success':float(np.mean(successes/used)),
        'service_probability_by_kappa':{
            f'{k:.2f}':float(np.mean(fraction>=k)) for k in (.9,.95,.98,1.)
        },
        'arcs_departing_at_or_after_1700':late_clock_arc_count,
    }


def reachability(data, params, speed=None):
    matrix = np.array(RoutingSolver(data,params,planning_speed_kmh=speed)._nominal_time)
    edges = matrix.copy()
    edges[1:,:] += params.service_minutes
    np.fill_diagonal(edges,0)
    for k in range(len(edges)):
        edges = np.minimum(edges, edges[:,k,None]+edges[None,k,:])
    direct = [max(data.offered_windows[i][0],int(matrix[0,i])) for i in range(len(matrix))]
    lower = [max(data.offered_windows[i][0],int(edges[0,i])) for i in range(len(matrix))]
    return direct, lower


def contracted_data(data, params, beta, capped=False, speed=None):
    base = data.contracted(beta)
    if not capped:
        return base
    direct, _ = reachability(data,params,speed)
    windows=[base.offered_windows[0]]
    for i, (lo,hi) in enumerate(base.offered_windows[1:],1):
        # Never extend an original promise; a beta=0 impossible direct trip
        # cannot be repaired merely by contraction.
        upper=min(data.offered_windows[i][1],max(hi,direct[i]))
        windows.append((lo,upper))
    return replace(data,offered_windows=tuple(windows))


def certificate(data, params, beta, speed=None, capped=False):
    _, lower=reachability(data,params,speed)
    contracted=contracted_data(data,params,beta,capped,speed)
    return [{'customer':i,'upper':hi,'earliest_lower_bound':lower[i]}
            for i,(lo,hi) in enumerate(contracted.offered_windows)
            if i and hi<lower[i]]


def audit_old_failure(record,data,params):
    grid=record['beta_values']
    proofs={str(b):certificate(data,params,b) for b in grid}
    first=next((b for b in grid if proofs[str(b)]),None)
    missing=[c['beta'] for c in record['screened']['candidates'] if c['plan'] is None]
    best=record['screened']['diagnostic'] or {}   # None when screening was not attempted
    return {
        'selected':record['screened']['selected_plan'] is not None,
        'best_beta':best.get('best_beta'), 'best_lcb':best.get('best_service_lcb'),
        'first_no_plan_beta':min(missing) if missing else None,
        'first_reachability_certificate_beta':first,
        'no_plan_before_certificate':any(not proofs[str(b)] for b in missing),
        'certified_no_plan_betas':[b for b in missing if proofs[str(b)]],
        'uncertified_no_plan_betas':[b for b in missing if not proofs[str(b)]],
        'certificates':proofs,
    }


def screen_generator(data,params,profile,ranges,bank,old,*,conservative=False,capped=False,seconds=5.):
    speed=params.nominal_speed_kmh/1.2 if conservative else None
    objective='distance' if conservative else 'weighted'
    candidates=[]; passing=[]
    for beta in old['beta_values']:
        started=time.perf_counter()
        cd=contracted_data(data,params,beta,capped,speed)
        proof=certificate(data,params,beta,speed,capped)
        archived=next((c for c in old['screened']['candidates'] if c['beta']==beta),None)
        plan=None; source='new solve'; attempts=0
        if not conservative and archived is not None and cd.offered_windows==data.contracted(beta).offered_windows:
            plan=None if archived['plan'] is None else plan_from_dict(archived['plan'])
            source='archived identical uniform model'
        elif conservative and beta==0:
            raw=old['peak_aware_distance']['plan']
            plan=None if raw is None else plan_from_dict(raw)
            source='archived conservative base'
        elif proof:
            source='reachability certificate; solve skipped'
        else:
            for attempts in range(1,4):
                plan=RoutingSolver(cd,params,ranges,planning_speed_kmh=speed).solve(objective,seconds)
                if plan is not None:
                    plan.beta=beta
                    break
        report=None if plan is None else evaluate(plan,data,params,profile,bank)
        candidates.append({'beta':beta,'source':source,'attempts':attempts,
            'solve_seconds':time.perf_counter()-started,
            'certificate':proof,'plan':None if plan is None else plan.as_dict(),
            'screening':report})
        if report and report['service_level_lcb']>=params.alpha:
            score=(plan.metrics['distance'],plan.metrics['driver_duration'],beta) if conservative else (normalized_score(plan,ranges,params),beta)
            passing.append((score,plan))
    passing.sort(key=lambda item:item[0])
    chosen=passing[0][1] if passing else None
    fallback_raw=old['peak_aware_distance']['plan'] if conservative else None
    fallback_source='conservative base' if fallback_raw is not None else 'slack-aware base'
    if fallback_raw is None: fallback_raw=old['weighted_objective_only']['plan']
    # With no screen-selected plan and no fallback base, the procedure has no plan.
    procedure=chosen if chosen is not None else (None if fallback_raw is None else plan_from_dict(fallback_raw))
    if chosen is None and fallback_raw is None: fallback_source='no plan: no selection and no fallback base'
    best=max((c for c in candidates if c['screening']),key=lambda c:c['screening']['service_level_lcb'],default=None)
    return {'candidates':candidates,'selected_plan':None if chosen is None else chosen.as_dict(),
        'procedure_plan':None if procedure is None else procedure.as_dict(),'procedure_source':'screen-selected' if chosen else fallback_source,
        'best_beta':None if best is None else best['beta'],
        'best_lcb':None if best is None else best['screening']['service_level_lcb']}


def deterministic_retime(plan,data,params,profile):
    """Latest whole-minute depot departure feasible under the exact FIFO clock."""
    routes=[]; departures=[]; starts={}; duration=0.
    for route in plan.routes:
        if len(route)<=2:
            routes.append(list(route)); departures.append(0.); continue
        def evaluate_departure(t):
            return _evaluate_route(route,t,data,params,profile)
        def feasible(r):
            return r['late_customers']==0 and r['return_time']<=params.shift_length+1e-9
        earliest=evaluate_departure(0)
        if not feasible(earliest):return None
        lo,hi=0,params.shift_length
        while lo<hi:
            mid=(lo+hi+1)//2
            if feasible(evaluate_departure(mid)):lo=mid
            else:hi=mid-1
        r=evaluate_departure(lo)
        routes.append(list(route));departures.append(float(lo));starts.update(r['service_starts'])
        duration+=r['duration']
    metrics=plan.metrics.copy();metrics['driver_duration']=duration
    metrics['tightness']=sum(max(0,params.target_slack-(data.offered_windows[i][1]-s)) for i,s in starts.items())
    return Plan(routes,departures,starts,metrics,'clock-profile-aware distance approximation')


def clock_aware(data,params,profile,old,total_seconds=5.):
    """Two row-frozen matrix solves and exact deterministic schedule checking."""
    reference=plan_from_dict(old['static']['plan'])
    candidates=[]; valid=[]
    started=time.perf_counter()
    for iteration in range(2):
        depart={i:s+params.service_minutes for i,s in reference.service_starts.items()}
        depot_departures={r[1]:reference.departures[k] for k,r in enumerate(reference.routes) if len(r)>2}
        default_depot=float(np.mean(list(depot_departures.values()))) if depot_departures else 0.
        matrix=[]
        for i,row in enumerate(data.distance):
            values=[]
            for j,d in enumerate(row):
                estimate=depart[i] if i else depot_departures.get(j,default_depot)
                values.append(0 if i==j else math.ceil(td_travel_minutes(d,params.shift_start_minute+estimate,profile)))
            matrix.append(tuple(values))
        solver=RoutingSolver(data,params)
        solver._nominal_time=tuple(matrix)
        plan=solver.solve('distance',total_seconds/2)
        if plan is None:
            candidates.append({'iteration':iteration,'plan':None,'deterministic_feasible':False})
            continue
        retimed=deterministic_retime(plan,data,params,profile)
        candidates.append({'iteration':iteration,'plan':plan.as_dict(),'deterministic_feasible':retimed is not None})
        reference=retimed if retimed else plan
        if retimed is not None:valid.append(retimed)
    valid.sort(key=lambda p:(p.metrics['distance'],p.metrics['driver_duration']))
    return {'plan':None if not valid else valid[0].as_dict(),'iterations':candidates,
        'solve_seconds':time.perf_counter()-started,'total_search_budget_seconds':total_seconds}
