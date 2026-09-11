import unittest
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from core import FIELDS
import event_formatter
from evaluate_events import inspect_case,summarize,rescore_saved_report,score_safely,cli_progress


def record(text,field='impact'):
    return {'event_type':'other','sections':{f:[{'text':text,'evidence':[text]}] if f==field else [] for f in FIELDS},
            'suggestions':[],'missing_fields':[f for f in FIELDS if f!=field],'status':'needs_confirmation',
            'issues':[],'questions':[],'review_excerpts':[],'human_approval_required':True}


def grouped_output(source,records):
    with patch('event_formatter.coach.process_note',side_effect=records):
        return event_formatter.process_note(None,None,source)


class EventEvaluationTests(unittest.TestCase):
    def test_cli_progress_accepts_both_runtime_callback_signatures_and_flushes(self):
        with patch('builtins.print') as output:
            cli_progress('dev-example','events')(.5,'Room A · organizing notes · part 1/2')
            cli_progress('dev-example','legacy')('Preparing suggestions',2,3)
        self.assertEqual(output.call_args_list[0].args,('PROGRESS','dev-example','events','50%','Room A · organizing notes · part 1/2'))
        self.assertEqual(output.call_args_list[1].args,('PROGRESS','dev-example','legacy','Preparing suggestions','part 2/3'))
        self.assertTrue(all(call.kwargs.get('flush') is True for call in output.call_args_list))

    def case(self):
        return {'id':'dev-test-1','source_text':'EVENT: A\ndelay unknown\nEVENT: B\nno delay',
                'domain':'fictional office','mode':'draft','assist':False,
                'expectations':{'event_count':2,'expected_event_labels':['A','B'],'checks':[
            {'event_label':'B','section':'impact','required_fragments':['delay unknown'],'forbidden_fragments':['no delay'],'review_note':'Preserve uncertainty.'}]}}

    def test_global_match_cannot_hide_wrong_event_placement(self):
        output=grouped_output(self.case()['source_text'],[record('delay unknown'),record('no delay')])
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
        output=grouped_output(self.case()['source_text'],[record('delay unknown'),record('no delay')])
        output['event_results'][1]['result']['sections']['impact']=[{'text':'delay unknown','evidence':['delay unknown']}]
        self.assertTrue(inspect_case(self.case(),output,'events')['event_quote_issues'])

    def test_summary_separates_variants_and_keeps_denominators(self):
        checks=inspect_case(self.case(),record('delay unknown'),'legacy')
        report={'outputs':[{'variant':'legacy','seconds':1.0,'checks':checks}]}
        summary=summarize(report)['legacy']
        self.assertEqual(summary['attempted'],1)
        self.assertEqual(summary['cases_with_missing_or_forbidden_scoped_fragments'],0)

    def test_real_wrapper_shape_and_original_locations_validate(self):
        output=grouped_output(self.case()['source_text'],[record('delay unknown'),record('no delay')])
        checked=inspect_case(self.case(),output,'events')
        self.assertEqual(checked['structure_errors'],[])
        self.assertTrue(checked['complete_structured_output'])

    def test_malformed_nested_results_do_not_stop_scoring(self):
        original=grouped_output(self.case()['source_text'],[record('delay unknown'),record('no delay')])
        malformed=[None,[],{'sections':None}]
        for nested in (None,{'sections':None},dict(record('delay unknown'),missing_fields=[{}])):
            output=copy.deepcopy(original)
            output['event_results'][0]['result']=nested
            malformed.append(output)
        output=copy.deepcopy(original);output['event_results']=[None];malformed.append(output)
        output=copy.deepcopy(original);output['event_results'][0]['result']['sections']['impact']=[None,{'text':12,'evidence':[5]}];malformed.append(output)
        for output in malformed:
            with self.subTest(output=repr(output)[:100]):
                checked=inspect_case(self.case(),output,'events')
                self.assertFalse(checked['complete_structured_output'])
                self.assertTrue(checked['structure_errors'])

    def test_nested_partial_status_prevents_complete_score(self):
        output=grouped_output(self.case()['source_text'],[record('delay unknown'),record('no delay')])
        output['event_results'][1]['result']['status']='incomplete_draft'
        output['status']='needs_confirmation'
        self.assertFalse(inspect_case(self.case(),output,'events')['complete_structured_output'])

    def test_tampered_original_span_is_a_structure_failure(self):
        output=grouped_output(self.case()['source_text'],[record('delay unknown'),record('no delay')])
        output['event_results'][0]['source_evidence'][0]['quotes'][0]['candidates'][0]['segments'][0]['start']+=1
        checked=inspect_case(self.case(),output,'events')
        self.assertFalse(checked['complete_structured_output'])
        self.assertTrue(any('source_evidence' in error for error in checked['structure_errors']))

    def test_dropping_an_ambiguous_location_is_a_structure_failure(self):
        row=self.case();row['source_text']='EVENT: A\ndelay unknown\ndelay unknown\nEVENT: B\nno delay'
        output=grouped_output(row['source_text'],[record('delay unknown'),record('no delay')])
        quote=output['event_results'][0]['source_evidence'][0]['quotes'][0]
        quote['candidates']=quote['candidates'][:1];quote['ambiguous']=False
        self.assertFalse(inspect_case(row,output,'events')['complete_structured_output'])

    def test_flat_compatibility_fields_do_not_supply_event_global_scores(self):
        row=self.case();row['expectations']['checks'][0]['required_fragments']=['invented target']
        output=grouped_output(row['source_text'],[record('delay unknown'),record('no delay')])
        output['sections']['impact'].append({'text':'invented target','evidence':['invented target']})
        self.assertEqual(inspect_case(row,output,'events')['checks'][0]['global_missing_fragments'],['invented target'])

    def test_unexpected_scorer_exception_is_recorded_without_raising(self):
        with patch('evaluate_events.inspect_case',side_effect=RuntimeError('synthetic scorer failure')):
            checked,error=score_safely(self.case(),{},'events')
        self.assertFalse(checked['complete_structured_output'])
        self.assertIn('synthetic scorer failure',error)

    def saved_fixture(self,directory):
        row=self.case()
        dataset=directory/'development.jsonl'
        dataset.write_text(json.dumps(row)+'\n',encoding='utf-8')
        output=grouped_output(row['source_text'],[record('delay unknown'),record('no delay')])
        output['raw_outputs']=['unaltered saved raw response']
        report={'complete':True,'dataset':'evaluation-v3/development.jsonl',
                'dataset_sha256':hashlib.sha256(dataset.read_bytes()).hexdigest(),
                'selected_ids':[row['id']],'legacy_ids':[],
                'code_sha256':{'event_formatter.py':'recorded-generation-hash'},
                'outputs':[{'id':row['id'],'variant':'events','seconds':3.0,
                            'domain':row['domain'],'source_text':row['source_text'],'mode':row['mode'],'assist':row['assist'],
                            'error':None,'result':output,'draft':'Saved draft remains exactly as generated.',
                            'checks':{'old_score':'retained'}}]}
        source=directory/'original.json';source.write_text(json.dumps(report),encoding='utf-8')
        return source,dataset,report

    def test_rescore_preserves_saved_generation_without_loading_a_model(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);source,dataset,original=self.saved_fixture(directory)
            original_bytes=source.read_bytes();destination=directory/'rescored.json'
            with patch('evaluate_events.core.load_model',side_effect=AssertionError('No model allowed')), \
                 patch('evaluate_events.event_formatter.process_note',side_effect=AssertionError('No inference allowed')):
                revised=rescore_saved_report(source,destination,dataset)
            self.assertEqual(source.read_bytes(),original_bytes)
            for field in ('result','draft','source_text','seconds','domain','mode','assist','error'):
                self.assertEqual(revised['outputs'][0][field],original['outputs'][0][field])
            self.assertEqual(revised['outputs'][0]['generation_checks'],{'old_score':'retained'})
            self.assertTrue(revised['scoring_only_revision']);self.assertFalse(revised['inference_performed_by_this_command'])
            self.assertEqual(revised['recorded_generation_code_sha256'],original['code_sha256'])
            self.assertIn('evaluate_v2.py',revised['scoring_code_sha256'])
            self.assertEqual(revised['source_report_sha256'],hashlib.sha256(original_bytes).hexdigest())
            self.assertEqual(json.loads(destination.read_text(encoding='utf-8')),revised)

    def test_rescore_rejects_changed_dataset_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);source,dataset,original=self.saved_fixture(directory)
            destination=directory/'new.json'
            dataset.write_text(dataset.read_text(encoding='utf-8')+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'SHA-256'):rescore_saved_report(source,destination,dataset)
            self.assertFalse(destination.exists())
            destination.write_text('existing evidence',encoding='utf-8')
            with self.assertRaises(FileExistsError):rescore_saved_report(source,destination,dataset)
            self.assertEqual(destination.read_text(encoding='utf-8'),'existing evidence')

    def test_rescore_rejects_mismatched_selection_outputs_and_source(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);source,dataset,original=self.saved_fixture(directory)
            variants=[]
            candidate=copy.deepcopy(original);candidate['selected_ids']=['unknown'];variants.append(candidate)
            candidate=copy.deepcopy(original);candidate['outputs']=[];variants.append(candidate)
            candidate=copy.deepcopy(original);candidate['outputs'][0]['source_text']='Changed notes';variants.append(candidate)
            candidate=copy.deepcopy(original);candidate['complete']=False;variants.append(candidate)
            for index,candidate in enumerate(variants):
                with self.subTest(index=index):
                    source.write_text(json.dumps(candidate),encoding='utf-8')
                    destination=directory/f'new-{index}.json'
                    with self.assertRaises(ValueError):rescore_saved_report(source,destination,dataset)
                    self.assertFalse(destination.exists())

    def test_rescore_keeps_malformed_saved_result_and_records_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);source,dataset,original=self.saved_fixture(directory)
            original['outputs'][0]['result']={'sections':None}
            source.write_text(json.dumps(original),encoding='utf-8')
            revised=rescore_saved_report(source,directory/'rescored.json',dataset)
            self.assertEqual(revised['outputs'][0]['result'],{'sections':None})
            self.assertFalse(revised['outputs'][0]['checks']['complete_structured_output'])


if __name__=='__main__':unittest.main()
