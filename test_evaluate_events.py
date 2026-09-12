import unittest
from core import FIELDS
from evaluate_events import inspect_case,summarize


def record(text,field='impact'):
    return {'event_type':'other','sections':{f:[{'text':text,'evidence':[text]}] if f==field else [] for f in FIELDS},
            'suggestions':[],'missing_fields':[f for f in FIELDS if f!=field],'status':'needs_confirmation',
            'issues':[],'human_approval_required':True}


class EventEvaluationTests(unittest.TestCase):
    def case(self):
        return {'expectations':{'event_count':2,'expected_event_labels':['A','B'],'checks':[
            {'event_label':'B','section':'impact','required_fragments':['delay unknown'],'forbidden_fragments':['no delay'],'review_note':'Preserve uncertainty.'}]}}

    def test_global_match_cannot_hide_wrong_event_placement(self):
        output=record('delay unknown')
        output['event_results']=[{'label':'A','grouping':'explicit','source_text':'delay unknown','result':record('delay unknown')},
                                 {'label':'B','grouping':'explicit','source_text':'no delay','result':record('no delay')}]
        check=inspect_case(self.case(),output,'events')['checks'][0]
        self.assertEqual(check['global_missing_fragments'],[])
        self.assertEqual(check['missing_fragments'],['delay unknown'])
        self.assertEqual(check['forbidden_hits'],['no delay'])

    def test_flat_legacy_output_is_not_scored_as_event_aware(self):
        checks=inspect_case(self.case(),record('delay unknown'),'legacy')
        self.assertIsNone(checks['explicit_labels_match'])
        self.assertFalse(checks['checks'][0]['applicable'])
        self.assertIsNone(checks['checks'][0]['missing_fragments'])

    def test_invalid_or_partial_case_does_not_count_as_complete(self):
        self.assertFalse(inspect_case(self.case(),{},'events','failure')['complete_structured_output'])
        output=record('delay unknown');output['status']='incomplete_draft'
        self.assertFalse(inspect_case(self.case(),output,'events')['complete_structured_output'])

    def test_quote_from_other_event_is_reported(self):
        output=record('delay unknown')
        output['event_results']=[{'label':'B','grouping':'explicit','source_text':'No date supplied.','result':record('delay unknown')}]
        self.assertTrue(inspect_case(self.case(),output,'events')['event_quote_issues'])

    def test_summary_separates_variants_and_keeps_denominators(self):
        checks=inspect_case(self.case(),record('delay unknown'),'legacy')
        report={'outputs':[{'variant':'legacy','seconds':1.0,'checks':checks}]}
        summary=summarize(report)['legacy']
        self.assertEqual(summary['attempted'],1)
        self.assertEqual(summary['cases_with_missing_or_forbidden_scoped_fragments'],0)


if __name__=='__main__':unittest.main()
