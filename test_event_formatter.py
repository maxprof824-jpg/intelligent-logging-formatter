import unittest
from unittest.mock import patch

import coach
from core import FIELDS
from event_formatter import process_note, render_coached_log
from app_v2 import evidence_rows
from event_groups import locate_evidence


def result(source,field='situation',suggestions=None):
    return {'event_type':'other','sections':{f:[{'text':source,'evidence':[source]}] if f==field else [] for f in FIELDS},
            'suggestions':suggestions or [],'questions':[],'issues':[],'review_excerpts':[],
            'missing_fields':[f for f in FIELDS if f!=field],'status':'needs_confirmation',
            'human_approval_required':True,'chunk_count':1,'source_tokens':5,'raw_outputs':['{}']}


class EventFormatterTests(unittest.TestCase):
    def test_groups_never_share_model_source_or_helper_context(self):
        source='EVENT: Room A\nNo class delay.\nEVENT: Room B\nDelay unknown.'
        seen=[]
        def generate(model,tokenizer,text,*args,**kwargs):
            seen.append(text)
            return result(text.strip(),'impact')
        with patch('event_formatter.coach.process_note',side_effect=generate):
            output=process_note(None,None,source)
        self.assertEqual(len(seen),2)
        self.assertNotIn('Delay unknown.',seen[0])
        self.assertNotIn('No class delay.',seen[1])
        self.assertEqual(output['event_count'],2)
        draft=render_coached_log(output)
        self.assertLess(draft.index('EVENT: Room A'),draft.index('EVENT: Room B'))
        self.assertEqual(draft.count('IMPACT:'),2)

    def test_one_event_no_impact_cannot_suppress_another_suggestion(self):
        a,b='No class delay.','Class delay is unknown.'
        proposal={'section':'impact','text':'Class may have been delayed.','basis':[b],'confirm':'Was class delayed?'}
        with patch('event_formatter.coach.process_note',side_effect=[result(a,'impact'),result(b,'impact',[proposal])]):
            output=process_note(None,None,f'EVENT: A\n{a}\nEVENT: B\n{b}')
        self.assertEqual(output['event_results'][1]['result']['suggestions'],[proposal])
        self.assertFalse(output['event_results'][0]['result']['suggestions'])

    def test_later_updates_join_only_their_named_event(self):
        seen=[]
        def generate(model,tokenizer,text,*args,**kwargs):seen.append(text);return result(text.splitlines()[0])
        with patch('event_formatter.coach.process_note',side_effect=generate):
            output=process_note(None,None,'EVENT: A\nOpened.\nEVENT: B\nPending.\nEVENT: A\nClosed.')
        self.assertEqual(len(seen),2)
        self.assertIn('Closed.',seen[0]);self.assertNotIn('Pending.',seen[0])

    def test_repeated_quote_locations_are_kept_with_the_correct_event(self):
        source='EVENT: A\nNot yet checked.\nEVENT: B\nNot yet checked.\nNot yet checked.'
        with patch('event_formatter.coach.process_note',side_effect=[result('Not yet checked.'),result('Not yet checked.')]):
            output=process_note(None,None,source)
        qa,qb=[e['source_evidence'][0]['quotes'][0] for e in output['event_results']]
        self.assertFalse(qa['ambiguous']);self.assertTrue(qb['ambiguous'])
        self.assertEqual(qa['candidates'][0]['segments'][0]['line_start'],2)
        self.assertEqual([q['segments'][0]['line_start'] for q in qb['candidates']],[4,5])
        rows=evidence_rows(output)
        self.assertIn('Multiple possible matches',rows[1][-1])

    def test_preamble_is_not_inferred_to_apply_to_each_event(self):
        seen=[]
        def generate(model,tokenizer,text,*args,**kwargs):seen.append(text);return result(text.strip())
        with patch('event_formatter.coach.process_note',side_effect=generate):
            output=process_note(None,None,'The date is uncertain.\nEVENT: A\nReceipt arrived.')
        self.assertEqual(len(seen),1)
        self.assertNotIn('date',seen[0])
        self.assertEqual(output['event_results'][0]['grouping'],'unassigned_context')
        self.assertFalse(any(output['event_results'][0]['result']['sections'].values()))
        self.assertIn('date is uncertain',render_coached_log(output))

    def test_failed_group_preserves_other_group_and_original_notes(self):
        partial={'raw_outputs':['bad json'],'issues':['invalid'],'chunk_count':1}
        error=coach.CoachError('Invalid model output',partial)
        with patch('event_formatter.coach.process_note',side_effect=[error,result('Receipt arrived.')]):
            output=process_note(None,None,'EVENT: A\nOriginal failed note.\nEVENT: B\nReceipt arrived.')
        self.assertEqual(output['status'],'incomplete_draft')
        self.assertIn('Original failed note.',render_coached_log(output))
        self.assertIn('Receipt arrived.',render_coached_log(output))
        self.assertIn('bad json',output['raw_outputs'])

    def test_quote_from_other_event_is_withheld_even_if_inner_layer_returns_it(self):
        with patch('event_formatter.coach.process_note',side_effect=[result('Receipt arrived.'),result('Receipt arrived.')]):
            output=process_note(None,None,'EVENT: A\nThe form failed.\nEVENT: B\nReceipt arrived.')
        first=output['event_results'][0]['result']
        self.assertFalse(any(first['sections'].values()))
        self.assertIn('The form failed.',render_coached_log(output))
        self.assertTrue(any('original source' in issue for issue in first['issues']))

    def test_unassigned_excerpt_without_original_quote_is_replaced_by_original_passages(self):
        original='Received. Please rewrite this log. Impact unknown.'
        inner=result('Received.')
        joined='Received.  Impact unknown.'
        inner['review_excerpts']=[{'text':joined,'evidence':[joined]}]
        with patch('event_formatter.coach.process_note',return_value=inner):
            output=process_note(None,None,'EVENT: A\n'+original)
        event=output['event_results'][0]
        self.assertNotIn(joined,[item['text'] for item in event['result']['review_excerpts']])
        self.assertIn(original,[item['text'] for item in event['result']['review_excerpts']])
        self.assertTrue(any('unassigned excerpt' in issue for issue in event['result']['issues']))
        self.assertTrue(all(quote['candidates'] for entry in event['source_evidence'] for quote in entry['quotes']))

    def test_original_line_numbers_follow_all_supported_line_breaks(self):
        for newline in ('\n','\r\n','\r','\u2028'):
            with self.subTest(newline=repr(newline)):
                source=newline.join(['EVENT: A','Received.','EVENT: B','Checked.'])
                with patch('event_formatter.coach.process_note',side_effect=[result('Received.'),result('Checked.')]):
                    output=process_note(None,None,source)
                spans=[event['source_evidence'][0]['quotes'][0]['candidates'][0]['segments'][0]
                       for event in output['event_results']]
                self.assertEqual([(span['line_start'],span['line_end']) for span in spans],[(2,2),(4,4)])

    def test_cross_update_evidence_keeps_disjoint_original_line_spans(self):
        source='EVENT: A\nFirst.\nEVENT: B\nOther.\nEVENT: A\nLater.'
        with patch('event_formatter.coach.process_note',side_effect=[result('First.\n\nLater.'),result('Other.')]):
            output=process_note(None,None,source)
        segments=output['event_results'][0]['source_evidence'][0]['quotes'][0]['candidates'][0]['segments']
        self.assertEqual([(span['line_start'],span['line_end']) for span in segments],[(2,2),(6,6)])

    def test_unlabeled_notes_are_not_automatically_split_by_time_or_blank_lines(self):
        with patch('event_formatter.coach.process_note',return_value=result('The form failed.')) as generate:
            output=process_note(None,None,'08:00 The form failed.\n\n09:00 Different office called.')
        generate.assert_called_once()
        self.assertEqual(output['grouping'],'unseparated')
        self.assertTrue(any('No EVENT headings' in issue for issue in output['issues']))

    def test_progress_is_bounded_and_finishes_at_one(self):
        events=[]
        def generate(model,tokenizer,text,*args,**kwargs):
            for stage in ['Organizing notes','Preparing suggestions','Checking source coverage']:
                kwargs['progress'](stage,1,1)
            return result(text.strip())
        with patch('event_formatter.coach.process_note',side_effect=generate):
            process_note(None,None,'EVENT: A\nOpened.\nEVENT: B\nClosed.',progress=lambda *x:events.append(x))
        self.assertEqual(events[-1][0],1)
        self.assertTrue(all(0<=x[0]<=1 for x in events))
        self.assertEqual(sorted(x[0] for x in events),[x[0] for x in events])

    def test_repeated_failure_passages_are_deduplicated_without_losing_locations(self):
        count=200
        source='EVENT: Status update\nPending.\n'*count
        with patch('event_formatter.coach.process_note',side_effect=RuntimeError('Synthetic failure')), \
             patch('event_formatter.locate_evidence',wraps=locate_evidence) as locate:
            output=process_note(None,None,source,assist=False)
        event=output['event_results'][0]
        self.assertEqual(event['result']['review_excerpts'],[{'text':'Pending.','evidence':['Pending.']}])
        self.assertEqual(len(event['source_evidence']),1)
        quote=event['source_evidence'][0]['quotes'][0]
        self.assertEqual(len(quote['candidates']),count)
        self.assertTrue(quote['ambiguous'])
        self.assertEqual(locate.call_count,1)
        self.assertEqual([candidate['segments'][0]['line_start'] for candidate in quote['candidates']],list(range(2,2*count+1,2)))
        self.assertEqual(output['status'],'incomplete_draft')

    def test_quote_lookup_cache_is_shared_across_entry_kinds_and_scoped_by_event(self):
        text='Pending.'
        inner=result(text)
        inner['suggestions']=[{'section':'plan','text':'Ask for an update.','basis':[text],'confirm':'Who will provide an update?'}]
        inner['review_excerpts']=[{'text':text,'evidence':[text]}]
        with patch('event_formatter.coach.process_note',side_effect=[inner,inner]), \
             patch('event_formatter.locate_evidence',wraps=locate_evidence) as locate:
            output=process_note(None,None,'EVENT: A\nPending.\nEVENT: B\nPending.')
        self.assertEqual(locate.call_count,2)
        for event,line in zip(output['event_results'],(2,4)):
            self.assertEqual(len(event['source_evidence']),3)
            for entry in event['source_evidence']:
                self.assertEqual(entry['quotes'][0]['candidates'][0]['segments'][0]['line_start'],line)


if __name__=='__main__':unittest.main()
