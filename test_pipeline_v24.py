import json
import unittest
from unittest.mock import patch
from core import FIELDS
from coach import clean_source, split_source, process_note, parse_coached_output


def record(text):
    return {'event_type':'other','sections':{field:([{'text':text,'evidence':[text]}] if field=='situation' else []) for field in FIELDS},'suggestions':[]}


class PipelineV24Tests(unittest.TestCase):
    def test_dense_note_retains_extra_quotes_without_bypassing_grounding(self):
        quotes=[f'Box DEMO-{i} was listed.' for i in range(49)]
        source=' '.join(quotes)
        item=record(quotes[0])
        item['sections']['situation'][0]['evidence']=quotes
        with patch('coach.split_source',return_value=([source],500)),patch('coach.generate_coached',return_value=json.dumps(item)):
            result=process_note(None,None,source,assist=False)
        self.assertEqual(result['sections']['situation'][0]['evidence'],quotes)
        item['sections']['situation'][0]['evidence'][-1]='An invented source quote.'
        with patch('coach.split_source',return_value=([source],500)),patch('coach.generate_coached',return_value=json.dumps(item)):
            result=process_note(None,None,source,assist=False)
        self.assertFalse(result['sections']['situation'])
        self.assertTrue(any('unsupported source quote' in issue for issue in result['issues']))

    def test_evidence_array_remains_bounded(self):
        from jsonschema import ValidationError
        item=record('The receipt arrived.')
        item['sections']['situation'][0]['evidence']=['The receipt arrived.']*65
        with self.assertRaises(ValidationError):
            parse_coached_output(json.dumps(item))

    def test_mixed_writing_request_retains_event_after_semicolon(self):
        cleaned,removed=clean_source('Need a clear log; 10:30Z Support (KR) confirmed receipt.')
        self.assertIn('10:30Z Support (KR) confirmed receipt.',cleaned)
        self.assertNotIn('Need a clear log',cleaned)
        self.assertEqual(len(removed),1)

    def test_invalid_split_settings_cannot_loop_forever(self):
        for options in ({'chunk_tokens':0},{'chunk_tokens':5,'overlap_tokens':5},{'overlap_tokens':-1}):
            with self.subTest(options=options),self.assertRaises(ValueError):
                split_source('abc',None,**options)

    def test_bad_request_rejected_before_generation(self):
        for source,mode in [(None,'draft'),('abc','bad'),('a'*120001,'draft')]:
            with self.subTest(mode=mode), patch('coach.generate_coached') as gen, self.assertRaises(ValueError):
                process_note(None,None,source,mode=mode)
            gen.assert_not_called()

    def test_a_quote_from_an_unseen_chunk_is_not_accepted(self):
        first,second='The form failed.','The receipt arrived.'
        with patch('coach.split_source',return_value=([first,second],6)), \
             patch('coach.generate_coached',side_effect=[json.dumps(record(second)),json.dumps(record(second))]):
            result=process_note(None,None,first+'\n'+second,assist=False)
        self.assertTrue(any('unsupported source quote' in issue for issue in result['issues']))
        self.assertIn(first,[item['text'] for item in result['review_excerpts']])

    def test_progress_reports_real_chunks_and_final_coverage(self):
        source='The display froze.'
        events=[]
        with patch('coach.split_source',return_value=([source],4)),patch('coach.generate_coached',return_value=json.dumps(record(source))):
            process_note(None,None,source,assist=False,progress=lambda *event:events.append(event))
        self.assertEqual(events,[('Organizing notes',1,1),('Checking source coverage',1,1)])


if __name__=='__main__':unittest.main()
