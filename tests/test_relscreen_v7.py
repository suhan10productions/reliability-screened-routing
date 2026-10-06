import unittest
from dataclasses import replace
import numpy as np
from relscreen_v6 import ModelParams,SpeedProfile,ScenarioBank,InstanceData,Plan,RoutingSolver,make_synthetic_instance,evaluate_reliability,td_travel_minutes
from relscreen_v7 import vector_travel,evaluate,certificate,contracted_data,deterministic_retime


class V7Checks(unittest.TestCase):
    def test_vector_profile_matches_scalar_across_boundaries(self):
        departures=np.array([0,360,419,420,539.9,540,999,1020,1139,1140,1439,1600.])
        p=SpeedProfile()
        for distance in (0,1,40,200,2000):
            expected=[td_travel_minutes(distance,float(t),p) for t in departures]
            np.testing.assert_allclose(vector_travel(distance,departures,p),expected,atol=1e-10)

    def test_vector_outcomes_match_scalar(self):
        p=ModelParams();d=make_synthetic_instance(12,5,712);sp=SpeedProfile()
        plan=RoutingSolver(d,p).solve('distance',.15)
        self.assertIsNotNone(plan)
        bank=ScenarioBank(151,43,p)
        a=evaluate_reliability(plan,d,p,sp,bank).as_dict(); b=evaluate(plan,d,p,sp,bank)
        for key in ('service_level_success','service_level_lcb','mean_on_time_fraction','expected_late_customers','mean_total_lateness','fleet_day_success','mean_route_success'):
            self.assertAlmostEqual(a[key],b[key],places=10)

    def test_cap_preserves_original_promises_and_avoids_direct_conflict(self):
        p=ModelParams(); d=InstanceData(((0,0),(30,0)),(0,1),((0,600),(0,70)),((0,30),(30,0)),1)
        self.assertTrue(certificate(d,p,30))
        cd=contracted_data(d,p,30,capped=True)
        self.assertEqual(cd.offered_windows[1],(0,45))
        self.assertFalse(certificate(d,p,30,capped=True))
        self.assertLessEqual(cd.offered_windows[1][1],d.offered_windows[1][1])

    def test_shortest_path_certificate_does_not_assume_metric(self):
        p=replace(ModelParams(),service_minutes=1)
        d=InstanceData(((0,0),(0,0),(0,0)),(0,1,1),((0,600),(0,8),(0,8)),((0,10,1),(10,0,1),(1,1,0)),2)
        # Direct depot->1 would incorrectly diagnose infeasibility. Via 2 is 5 min.
        self.assertFalse(certificate(d,p,0))

    def test_deterministic_retiming_respects_exact_profile(self):
        p=ModelParams();sp=SpeedProfile()
        d=InstanceData(((0,0),(30,0)),(0,1),((0,600),(0,150)),((0,30),(30,0)),1)
        raw=Plan([[0,1,0]],[140],{1:185},{'fuel':900.,'distance':60.,'fleet':1.,'driver_duration':100.,'tightness':0.},'distance')
        plan=deterministic_retime(raw,d,p,sp)
        self.assertIsNotNone(plan)
        no_noise=replace(p,sigma=0.)
        report=evaluate(plan,d,no_noise,sp,ScenarioBank(1,2,no_noise))
        self.assertEqual(report['mean_on_time_fraction'],1.)
        self.assertLess(plan.departures[0],140)


if __name__=='__main__':unittest.main()
