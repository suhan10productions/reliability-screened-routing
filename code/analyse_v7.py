"""Paired manuscript tables from immutable v7 per-instance records."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
CONFIGS=('nominal','conservative','slack','fleet_matched','procedure','screened_conservative','capped_procedure','clock_aware')
LABELS={'nominal':'Nominal','conservative':'Conservative speed','slack':'Slack-aware',
        'fleet_matched':'Fleet-matched','procedure':'Original procedure',
        'screened_conservative':'Screened conservative','capped_procedure':'Capped procedure','clock_aware':'Clock approximation'}
SIZES=(20,50,100,200)
rng=np.random.default_rng(20261001)


def ci(values,scale=1.):
    a=np.asarray(values,dtype=float)*scale
    if not len(a):return None
    draws=a[rng.integers(0,len(a),(20000,len(a)))].mean(axis=1)
    return [float(a.mean()),float(np.quantile(draws,.025)),float(np.quantile(draws,.975))]


def fmt(x,digits=1):
    return '--' if x is None else f'{x[0]:.{digits}f} [{x[1]:.{digits}f}, {x[2]:.{digits}f}]'.replace('-', '$-$')


def val(r,c,metric='service_level_success'):
    return r['configurations'][c]['validation'][metric]


def metric(r,c,m):return r['configurations'][c]['plan']['metrics'][m]


def table(caption,label,columns,header,rows,size='small'):
    return '\n'.join([r'\begin{table}[htbp]',r'\centering',f'\\{size}',
        f'\\caption{{{caption}}}',f'\\label{{{label}}}',
        f'\\begin{{tabular}}{{{columns}}}',r'\toprule',header+r'\\',r'\midrule',
        *[row+r'\\' for row in rows],r'\bottomrule',r'\end{tabular}',r'\end{table}',''])


def main():
    rows=[json.loads(p.read_text()) for p in sorted((ROOT/'results/v7').glob('instance_*.json'))]
    if len(rows)!=53 or len({r['instance_seed'] for r in rows})!=53:
        raise ValueError('The complete 53-instance experiment is required')
    common=[r for r in rows if r['configurations']['conservative'] is not None]
    assert len(common)==46
    original={r['instance_seed']:r for n in SIZES for r in json.loads((ROOT/f'results/study_v6_n{n}.json').read_text())['records']}
    summary={'schema':'routeops-v7-summary-1','matched_instances':len(common),'sizes':{},'sensitivity':{}}
    sections=[]; supplementary=[]
    sections.append(r'\subsection{Complete procedures on matched instances}')
    sections.append('Table~\\ref{tab:matched} compares every original configuration on the same '
        'subset of instances, those on which conservative-speed planning returned a plan. The paired contrasts '
        'are computed from differences within each instance, so their intervals measure the comparison directly; '
        'they are not obtained by subtracting the endpoints of separate intervals.')
    means=[];contrasts=[];costs=[];procedure_rows=[];clock_rows=[];cap_cost_rows=[]
    for n in SIZES:
        full=[r for r in rows if r['customers']==n]; matched=[r for r in common if r['customers']==n]
        s={'count':len(full),'matched_count':len(matched),'matched':{},'all':{},'paired':{},'screening':{},'resources':{}}
        for c in CONFIGS:
            eligible=[r for r in full if r['configurations'][c] is not None]
            eligible_match=[r for r in matched if r['configurations'][c] is not None]
            s['all'][c]={'count':len(eligible),'probability':ci([val(r,c) for r in eligible],100),
                'on_time':ci([val(r,c,'mean_on_time_fraction') for r in eligible],100)}
            s['matched'][c]={'count':len(eligible_match),'probability':ci([val(r,c) for r in eligible_match],100),
                'on_time':ci([val(r,c,'mean_on_time_fraction') for r in eligible_match],100),
                'expected_late':ci([val(r,c,'expected_late_customers') for r in eligible_match])}
        means.append(f'{n} & {len(matched)} & '+' & '.join(fmt(s['matched'][c]['probability']) for c in CONFIGS[:5]))
        for c in ('slack','procedure','screened_conservative','capped_procedure'):
            s['paired'][c+'_minus_conservative']=ci([val(r,c)-val(r,'conservative') for r in matched],100)
        contrasts.append(f'{n} & '+ ' & '.join(fmt(s['paired'][c+'_minus_conservative']) for c in ('slack','procedure','screened_conservative')))
        resource={
            'distance':ci([(metric(r,'procedure','distance')/metric(r,'conservative','distance')-1) for r in matched],100),
            'scheduled_duration':ci([(metric(r,'procedure','driver_duration')/metric(r,'conservative','driver_duration')-1) for r in matched],100),
            'simulated_duration':ci([(val(r,'procedure','mean_simulated_driver_duration')/val(r,'conservative','mean_simulated_driver_duration')-1) for r in matched],100),
            'fleet':ci([metric(r,'procedure','fleet')-metric(r,'conservative','fleet') for r in matched]),
        }
        s['resources']['procedure_vs_conservative']=resource
        costs.append(f'{n} & {fmt(resource["distance"])} & {fmt(resource["scheduled_duration"])} & {fmt(resource["simulated_duration"])} & {fmt(resource["fleet"],2)}')
        cap_resource={
            'distance':ci([metric(r,'capped_procedure','distance')/metric(r,'procedure','distance')-1 for r in full],100),
            'scheduled_duration':ci([metric(r,'capped_procedure','driver_duration')/metric(r,'procedure','driver_duration')-1 for r in full],100),
            'simulated_duration':ci([val(r,'capped_procedure','mean_simulated_driver_duration')/val(r,'procedure','mean_simulated_driver_duration')-1 for r in full],100),
            'fleet':ci([metric(r,'capped_procedure','fleet')-metric(r,'procedure','fleet') for r in full]),
        }
        s['resources']['capped_vs_original']=cap_resource
        cap_cost_rows.append(f'{n} & {fmt(cap_resource["distance"])} & {fmt(cap_resource["scheduled_duration"])} & {fmt(cap_resource["simulated_duration"])} & {fmt(cap_resource["fleet"],2)}')
        for c in ('procedure','screened_conservative','capped_procedure'):
            if c=='procedure':selected=[r for r in full if original[r['instance_seed']]['screened']['selected_plan'] is not None]
            else:selected=[r for r in full if r[c]['selected_plan'] is not None]
            retained=[r for r in selected if val(r,c,'service_level_lcb')>=.95]
            s['screening'][c]={'selected':len(selected),'retained':len(retained)}
            procedure_rows.append(f'{n} & {LABELS[c]} & {len(selected)}/{len(full)} & {len(retained)}/{len(selected)} & {fmt(s["all"][c]["probability"])}')
        clock=[r for r in full if r['configurations']['clock_aware'] is not None]
        s['clock_pairs']={c:ci([val(r,c) for r in clock],100) for c in ('nominal','procedure','clock_aware')}
        s['clock_pairs']['clock_minus_nominal']=ci([val(r,'clock_aware')-val(r,'nominal') for r in clock],100)
        clock_rows.append(f'{n} & {len(clock)}/{len(full)} & '+' & '.join(fmt(s['clock_pairs'][c]) for c in ('nominal','clock_aware','procedure','clock_minus_nominal')))
        summary['sizes'][str(n)]=s
    sections.append(table('Validated service-event probability (\\%) on the same 46 instances: every entry in a row has the displayed denominator; $k$ is the number of instances per size. Entries are mean [95\\% instance-bootstrap interval]. N, C, S, F and P denote nominal, conservative-speed, slack-aware, fleet-matched and original procedure, respectively.',
        'tab:matched','rrlllll','$n$ & $k$ & N & C & S & F & P',means,'scriptsize'))
    sections.append(table('Paired differences in service probability (percentage points) on the same subsets as Table~\\ref{tab:matched}. SC denotes screened conservative speed with its prespecified fallback.',
        'tab:paired','rlll','$n$ & S minus C & P minus C & SC minus C',contrasts,'small'))
    proc_range=[summary['sizes'][str(n)]['paired']['procedure_minus_conservative'][0] for n in SIZES]
    sections.append(f'In the paired contrasts of Table~\\ref{{tab:paired}}, the complete original procedure exceeds conservative-speed planning by '
        f'{min(proc_range):.1f}--{max(proc_range):.1f} percentage points, depending on size. '
        'The slack-aware objective without screening shows no such advantage. '
        'At $n=200$ the interval includes zero, so the positive mean at that size is not conclusive.')
    sections.append(r'\subsection{Resources on the common subset}')
    sections.append(table('Paired original-procedure changes relative to conservative speed on the common subset. Distance and duration are mean percentage changes; fleet is an absolute difference. Scheduled duration is each planner\'s own $F_3$. Simulated duration uses the same realized traffic model and planned departures for both configurations.',
        'tab:cost','rllll','$n$ & Distance & Scheduled time & Simulated time & Fleet',costs,'scriptsize'))
    sections.append('Scheduled driver duration differs from the realized driving, service and waiting time in simulation: '
        'the conservative planner budgets padded arc times, while in simulation those arcs may be driven faster. '
        'Table~\\ref{tab:cost} therefore reports both. Absolute distance premiums also depend on solver quality: '
        'in the five-second deterministic benchmark, OR-Tools routes are about 11\\% longer than HGS routes at $n=200$.')
    sections.append('The original procedure does not use fewer resources at every size. At $n=20$ it has slightly more scheduled time and more vehicles, '
        'and at $n=100$ it also uses slightly more vehicles. The simulated-time interval excludes zero only for the increase at $n=20$. '
        'The service gain is therefore bought with some extra operating resources.')
    sections.append(r'\subsection{Screening a replaceable generator and capping contractions}')
    sections.append(table('Procedure outcomes on all instances. Selected counts instances where the lower bound of some candidate on the screening bank reached 0.95; retained counts the selections whose lower bound on the fresh validation bank also reached 0.95. Probability includes fallback plans as well as selected plans.',
        'tab:screen','rllll','$n$ & Procedure & Selected / instances & Retained / selected & Probability (\\%)',procedure_rows,'small'))
    for c in ('procedure','screened_conservative','capped_procedure'):
        selected=sum(summary['sizes'][str(n)]['screening'][c]['selected'] for n in SIZES)
        retained=sum(summary['sizes'][str(n)]['screening'][c]['retained'] for n in SIZES)
        summary[c]={'selected':selected,'retained':retained,'all_probability':ci([val(r,c) for r in rows],100)}
    paired_new={c:ci([val(r,c)-val(r,'procedure') for r in rows],100) for c in ('screened_conservative','capped_procedure')}
    summary['all_paired_vs_original']=paired_new
    sections.append(f'In Table~\\ref{{tab:screen}}, screened conservative speed selects a plan on {summary["screened_conservative"]["selected"]} of 53 instances, '
        f'and {summary["screened_conservative"]["retained"]} of these selections keep the target lower bound on the fresh bank. '
        f'Over all instances, its paired difference from the original procedure is {fmt(paired_new["screened_conservative"])} points. '
        f'The capped variant selects a plan on {summary["capped_procedure"]["selected"]} of 53, with '
        f'{summary["capped_procedure"]["retained"]} retained, and its paired difference from the original procedure is '
        f'{fmt(paired_new["capped_procedure"])} points. Capping removes only the reachability obstruction at individual customers; '
        'limits from capacity, sequencing and finite search remain.')
    sections.append(table('Operating cost of the capped variant relative to the original procedure on all 53 instances. Percentage changes are paired by instance; fleet changes are absolute. Capping can lead to different routes and resources, so its reliability gain is not attributed to schedule structure alone.',
        'tab:cap-cost','rllll','$n$ & Distance & Scheduled time & Simulated time & Fleet',cap_cost_rows,'scriptsize'))
    summary['capped_resources_all']={
        'distance':ci([metric(r,'capped_procedure','distance')/metric(r,'procedure','distance')-1 for r in rows],100),
        'duration':ci([metric(r,'capped_procedure','driver_duration')/metric(r,'procedure','driver_duration')-1 for r in rows],100),
        'fleet':ci([metric(r,'capped_procedure','fleet')-metric(r,'procedure','fleet') for r in rows]),
    }
    sections.append(f'Over all instances (Table~\\ref{{tab:cap-cost}}), the capped variant uses {summary["capped_resources_all"]["distance"][0]:.1f}\\% more distance and '
        f'{summary["capped_resources_all"]["fleet"][0]:.2f} more vehicles than the original procedure. '
        'At $n=200$ the extra fleet is substantial. The earlier fleet-matched ablation concerns the uncontracted objective and does not cover this cost.')
    sections.append(r'\subsection{Clock-aware approximation}')
    sections.append(table('Clock-aware approximation. Each row uses the same instances for every column: those where the approximation found an exact deterministic schedule. Probabilities are percentages, and paired changes are percentage points. The two matrix solves share a five-second search budget.',
        'tab:clock','rrllll','$n$ & Found & Nominal & Clock-aware & Original P & Clock minus N',clock_rows,'scriptsize'))
    sections.append('The clock-aware rows test a practical approximation that uses departure times. '
        'Exact deterministic retiming checks every reported route, so its success at $\\sigma=0$ is a condition for acceptance '
        'and says nothing about robustness to random delay. Conservative-speed planning also guarantees deterministic on-time service '
        'within the planned horizon, because its planned arc times are never shorter than the deterministic ones. Both 100\\% results hold by construction.')
    clock_gain=[summary['sizes'][str(n)]['clock_pairs']['clock_minus_nominal'][0] for n in SIZES]
    sections.append(f'In Table~\\ref{{tab:clock}}, the approximation exceeds nominal distance by {min(clock_gain):.1f}--{max(clock_gain):.1f} points on the instances where it finds a schedule, '
        'but stays below the original procedure. The latest-feasible-departure rule and the two-pass search are part of this result, '
        'and the comparison does not show what an optimal time-dependent planner could achieve.')
    sections.append(r'\subsection{Matched disturbance sensitivity}')
    sens_rows=[]
    for sigma in (.1,.2,.3):
        for rho in (0.,.5,.9):
            key=f'{sigma:.2f},{rho:.1f}'
            x={c:ci([r['configurations'][c]['sensitivity'][key]['service_level_success'] for r in common],100) for c in ('conservative','procedure','screened_conservative','capped_procedure')}
            x['procedure_minus_conservative']=ci([r['configurations']['procedure']['sensitivity'][key]['service_level_success']-r['configurations']['conservative']['sensitivity'][key]['service_level_success'] for r in common],100)
            summary['sensitivity'][key]=x
            sens_rows.append(f'{sigma:.2f} & {rho:.1f} & '+ ' & '.join(fmt(x[c]) for c in ('conservative','procedure','screened_conservative','procedure_minus_conservative')))
    sections.append(table('Fixed-plan sensitivity on the 46 common instances. Each cell uses 1,000 common scenarios from a bank separate from the main validation bank; plans are not re-screened or re-optimized for each setting. C, P and SC are conservative speed, the original procedure and screened conservative speed.',
        'tab:sensitivity','rrllll','$\\sigma$ & $\\rho$ & C (\\%) & P (\\%) & SC (\\%) & P minus C (points)',sens_rows,'scriptsize'))
    sections.append('The comparison of interest in Table~\\ref{tab:sensitivity} is the paired difference P minus C, '
        'which Fig.~\\ref{fig:reliability} plots across the disturbance grid. '
        'It shows how the same fixed plans compare under each setting. This column alone cannot separate '
        'screening from the contracted candidate family, and the nine cells share instances and common random numbers.')
    low=summary['sensitivity']['0.10,0.0']['procedure_minus_conservative']
    high=summary['sensitivity']['0.30,0.0']['procedure_minus_conservative']
    sections.append(f'For independent disturbances, raising $\\sigma$ from 0.10 to 0.30 moves the paired difference from '
        f'{fmt(low)} to {fmt(high)} points. This supports a growing advantage of the complete screened procedure in that setting. '
        'At $\\rho=0.9$ the increase is not monotonic, so the data do not show that the value of screening always rises with the noise scale.')
    sections.append(r'\subsection{Diagnosis of screening failures}')
    failed=[r for r in rows if not r['old_failure_audit']['selected']]
    cert=sum(r['old_failure_audit']['first_reachability_certificate_beta'] is not None for r in failed)
    earlier=sum(r['old_failure_audit']['no_plan_before_certificate'] for r in failed)
    summary['failures']={'instances':len(failed),'certified_somewhere':cert,'no_certificate':len(failed)-cert,'earlier_uncertified':earlier}
    sections.append(f'Of the {len(failed)} instances on which the original procedure admitted no plan, {cert} reach a buffer at which some customer '
        f'is provably unreachable, and {len(failed)-cert} have no such certificate up to 60 minutes. '
        f'On {earlier} instances the solver also returned no plan at a buffer not covered by a certificate. Those outcomes remain unresolved: '
        'failing a necessary reachability test proves infeasibility, but passing it does not show that a feasible multi-customer routing exists. '
        'Appendix~\\ref{sec:failure-audit} gives the audit for each instance.')
    evening=sum(r['configurations'][c]['validation']['arcs_departing_at_or_after_1700'] for r in rows for c in CONFIGS if r['configurations'][c])
    summary['arcs_departing_after_1700_primary']=evening
    summary['fresh_validation_seeds']=[r['validation_seed'] for r in rows]
    summary['all_feasible_counts']={c:sum(r['configurations'][c] is not None for r in rows) for c in CONFIGS}

    # Full customer and resource outcomes for every configuration on the same 46.
    customer_rows=[];fullcost=[];kappa=[]
    for c in CONFIGS:
        matched=[r for r in common if r['configurations'][c] is not None]
        customer_rows.append(f'{LABELS[c]} & {len(matched)} & {fmt(ci([val(r,c,"mean_on_time_fraction") for r in matched],100))} & {fmt(ci([val(r,c,"expected_late_customers") for r in matched],1),2)}')
        fullcost.append(f'{LABELS[c]} & {len(matched)} & '+ ' & '.join(fmt(ci([metric(r,c,m) for r in matched]),2 if m=='fleet' else 1) for m in ('distance','driver_duration','fleet')))
    supplementary.append(table('Customer outcomes on the instances where conservative-speed planning returned a plan. The clock approximation also excludes the instances where it found no schedule, and the counts show this.','tab:customers','lrll','Configuration & $k$ & On time (\\%) & Expected late',customer_rows,'small'))
    supplementary.append(table('Mean absolute planned resources on the same instances as Table~\\ref{tab:customers}: distance in km, scheduled duration in minutes, and vehicles. These are not claims of optimality.','tab:fullcost','lrlll','Configuration & $k$ & Distance & Duration & Fleet',fullcost,'scriptsize'))
    for k in ('0.90','0.95','0.98','1.00'):
        kappa.append(k+' & '+' & '.join(fmt(ci([r['configurations'][c]['validation']['service_probability_by_kappa'][k] for r in common],100)) for c in ('nominal','conservative','slack','procedure','screened_conservative')))
    supplementary.append(table('Sensitivity to the service threshold $\\kappa$ on the 46 common instances, with the same plans and the same fresh validation bank in every column. At $n=20/50/100/200$, the number of customers allowed to be late is $2/5/10/20$ at $\\kappa=.90$, $1/2/5/10$ at $.95$, $0/1/2/4$ at $.98$, and zero at 1.00.','tab:kappa','rlllll','$\\kappa$ & N & C & S & P & SC',kappa,'scriptsize'))
    failure_rows=[]
    for r in failed:
        a=r['old_failure_audit'];cv=lambda v:'--' if v is None else str(v)
        failure_rows.append(f'{r["customers"]} & {r["instance_seed"]} & {cv(a["best_beta"])} & {100*a["best_lcb"]:.1f} & {cv(a["first_no_plan_beta"])} & {cv(a["first_reachability_certificate_beta"])} & '+('Yes' if a['no_plan_before_certificate'] else 'No'))
    supplementary.append(r'\subsection{Instance-level failure audit}\label{sec:failure-audit}')
    supplementary.append(table('Every instance on which the original procedure admitted no plan. Best $\\beta$ and the lower confidence bound (LCB) refer to the best returned candidate; the no-plan $\\beta$ is the first buffer at which the solver returned no plan; the proof $\\beta$ is the first buffer with a reachability certificate. Unresolved marks at least one no-plan result without a certificate. A dash means none up to 60 minutes.','tab:failure','rrrrrrc','$n$ & Seed & Best $\\beta$ & LCB (\\%) & No-plan $\\beta$ & Proof $\\beta$ & Unresolved',failure_rows,'scriptsize'))
    benchmark=[]
    for n in SIZES:
        payload=json.loads((ROOT/f'results/benchmark_v5_n{n}.json').read_text())
        values=[];counts=[]
        for budget in (1.,5.):
            valid=[r['ortools_excess_distance_percent'] for r in payload['records']
                   if r['budget_seconds']==budget and r.get('ortools_excess_distance_percent') is not None]
            values.append(fmt(ci(valid)));counts.append(len(valid))
        benchmark.append(f'{n} & {counts[0]}/{counts[1]} & '+ ' & '.join(values))
        summary.setdefault('benchmark_source_files',[]).append(f'results/benchmark_v5_n{n}.json')
    supplementary.append(table('Retained equal-budget benchmark on the deterministic core: excess distance of OR-Tools routes over PyVRP/HGS routes (\\%). Counts are valid pairs at the one-second and five-second budgets; one pair is missing at one second.','tab:hgs','rrll','$n$ & Valid pairs (1s/5s) & One second & Five seconds',benchmark,'small'))
    # An auditable JSON summary includes every analysed mean and interval.
    (ROOT/'results/summary_v7.json').write_text(json.dumps(summary,indent=2))
    (ROOT/'paper/results_summary_v7.tex').write_text('\n\n'.join(sections))
    (ROOT/'paper/additional_results_v7.tex').write_text('\n\n'.join(supplementary).replace(r'\begin{table}[htbp]',r'\begin{table}[H]'))
    macros={
        'ProcConsRange':f'{min(proc_range):.1f}--{max(proc_range):.1f}',
        'ConservativeSelected':str(summary['screened_conservative']['selected']),
        'ConservativeRetained':str(summary['screened_conservative']['retained']),
        'CappedSelected':str(summary['capped_procedure']['selected']),
        'CappedRetained':str(summary['capped_procedure']['retained']),
        'OriginalRetained':str(summary['procedure']['retained']),
        'OriginalProbability':f'{summary["procedure"]["all_probability"][0]:.1f}',
        'ConservativeProbability':f'{summary["screened_conservative"]["all_probability"][0]:.1f}',
        'CappedProbability':f'{summary["capped_procedure"]["all_probability"][0]:.1f}',
        'ClockFound':str(summary['all_feasible_counts']['clock_aware']),
        'CappedGainInterval':fmt(summary['all_paired_vs_original']['capped_procedure']),
        'CappedDistanceCost':f'{summary["capped_resources_all"]["distance"][0]:.1f}',
        'CappedFleetCost':f'{summary["capped_resources_all"]["fleet"][0]:.2f}',
    }
    # Framing macros: derived directly from the raw records so that every
    # number in the abstract and conclusion regenerates from the archive.
    _val=lambda r,c:r['configurations'][c]['validation']['service_level_success']
    _sw=lambda r,c,k:r['configurations'][c]['sensitivity'][k]['service_level_success']
    _com=[r for r in rows if r['configurations'].get('conservative')]
    _fail=[r for r in rows if not r['old_failure_audit']['selected']]
    _large=[r for r in rows if r['customers']>=100]
    _cap_by_n=[100*float(np.mean([_val(r,'capped_procedure') for r in rows if r['customers']==n])) for n in (100,200)]
    assert all(r['customers']<=50 for r in rows if r['capped_procedure']['selected_plan'] is None), \
        "conclusion text assumes every capped fallback occurs at 20 or 50 customers"
    macros.update({
        'OriginalSelected':str(sum(bool(r['old_failure_audit']['selected']) for r in rows)),
        'FailureCount':str(len(_fail)),
        'CertifiedFailures':str(sum(r['old_failure_audit']['first_reachability_certificate_beta'] is not None for r in _fail)),
        'SweepLowIndep':f"{100*float(np.mean([_sw(r,'procedure','0.10,0.0')-_sw(r,'conservative','0.10,0.0') for r in _com])):.1f}",
        'SweepHighIndep':f"{100*float(np.mean([_sw(r,'procedure','0.30,0.0')-_sw(r,'conservative','0.30,0.0') for r in _com])):.1f}",
        'CappedLargeRange':f'{min(_cap_by_n):.1f}--{max(_cap_by_n):.1f}',
        'CappedLargeSelected':f"{sum(r['capped_procedure']['selected_plan'] is not None for r in _large)}/{len(_large)}",
        'CappedLargeRetained':f"{sum(r['capped_procedure']['selected_plan'] is not None and r['configurations']['capped_procedure']['validation']['service_level_lcb']>=0.95 for r in _large)}/{len(_large)}",
        # Decomposition of the pooled target gap: admitted plans versus fallbacks.
        **(lambda: (lambda sel_o, sel_c: {
            'OriginalSelectedMean': f"{100*float(np.mean([_val(r,'procedure') for r in rows if sel_o(r)])):.1f}",
            'OriginalFallbackMean': f"{100*float(np.mean([_val(r,'procedure') for r in rows if not sel_o(r)])):.1f}",
            'CappedSelectedMean': f"{100*float(np.mean([_val(r,'capped_procedure') for r in rows if sel_c(r)])):.1f}",
            'CappedFallbackMean': f"{100*float(np.mean([_val(r,'capped_procedure') for r in rows if not sel_c(r)])):.1f}",
            'CappedFallbackCount': str(sum(not sel_c(r) for r in rows)),
        })(lambda r: bool(r['old_failure_audit']['selected']),
           lambda r: r['capped_procedure']['selected_plan'] is not None))(),
        # Exploratory search-budget diagnostic (results/search_budget_diagnostic.json).
        **(lambda d: {
            'BudgetDiagCases': str(len(d)),
            'BudgetDiagSearchLimits': str(sum(1 for x in d if x['plan_found_with_budget_s'])),
            'BudgetDiagUnresolved': str(sum(1 for x in d if not x['plan_found_with_budget_s'])),
        })(json.loads((ROOT/'results/search_budget_diagnostic.json').read_text())['results']),
        'CappedFleetLarge':f"{float(np.mean([r['configurations']['capped_procedure']['plan']['metrics']['fleet']-r['configurations']['procedure']['plan']['metrics']['fleet'] for r in rows if r['customers']==200])):.2f}",
    })
    (ROOT/'paper/result_macros_v7.tex').write_text('\n'.join('\\newcommand{\\'+k+'}{'+v+'}' for k,v in macros.items()))
    # Journal artwork rules: Arial/Helvetica lettering, fonts embedded as TrueType (Type 42).
    from matplotlib import font_manager
    installed={f.name for f in font_manager.fontManager.ttflist}
    sans=next((f for f in ('Arial','Liberation Sans','Helvetica') if f in installed),'DejaVu Sans')
    plt.rcParams.update({'font.size':9,'font.family':'sans-serif','font.sans-serif':[sans],
                         'mathtext.fontset':'custom','mathtext.rm':sans,'mathtext.it':sans+':italic',
                         'mathtext.cal':sans,'pdf.fonttype':42,'ps.fonttype':42})
    fig,ax=plt.subplots(figsize=(6.3,3.6))
    for rho,marker,color in [(0.,'o','0.15'),(.5,'s','0.45'),(.9,'^','0.68')]:
        intervals=[summary['sensitivity'][f'{s:.2f},{rho:.1f}']['procedure_minus_conservative'] for s in (.1,.2,.3)]
        means=np.array([a[0] for a in intervals]);low=np.array([a[1] for a in intervals]);high=np.array([a[2] for a in intervals])
        ax.errorbar(np.array([.1,.2,.3])+(rho-.5)*.006,means,yerr=[means-low,high-means],color=color,marker=marker,capsize=3,label=rf'$\rho={rho:.1f}$')
    for s_exact in (.1,.2,.3):
        ax.axvline(s_exact,color='0.88',linewidth=.6,zorder=0)   # exact sigma values; markers are offset only for legibility
    ax.axhline(0,color='#17375e',linewidth=.8,linestyle='--')
    ax.set(xlabel=r'Log-error scale $\sigma$',ylabel='P \u2212 C service probability\n(percentage points)',xticks=[.1,.2,.3])
    ax.set_xticklabels(['0.10','0.20','0.30'])
    ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False,ncol=3,loc='upper left')
    fig.tight_layout()
    for out in ('paper/matched_sensitivity_v7.pdf','paper/Fig1.pdf','paper/Fig1.eps'):
        fig.savefig(ROOT/out,bbox_inches='tight')
    plt.close(fig)
    print(json.dumps({k:summary[k] for k in ('procedure','screened_conservative','capped_procedure','all_paired_vs_original','failures','all_feasible_counts','arcs_departing_after_1700_primary')},indent=2))


if __name__=='__main__':main()
