import unittest
from source_coverage import evidence_coverage, add_source_coverage


class SourceCoverageTests(unittest.TestCase):
    def test_untimed_detail_remains_visible(self):
        source = 'The display froze. Pat asked us to keep the paper register.'
        sections = {'situation':[{'text':'The display froze.','evidence':['The display froze.']}]}
        result = {'sections':sections,'issues':[],'status':'ready_for_human_review'}
        add_source_coverage(result,source)
        self.assertEqual(result['review_excerpts'][0]['text'],'Pat asked us to keep the paper register.')
        self.assertEqual(result['status'],'needs_confirmation')

    def test_overlap_is_not_double_counted(self):
        value = evidence_coverage('abcdef',{'situation':[{'evidence':['abcd','cdef']}]})
        self.assertEqual(value['characters_in_fact_evidence'],6)
        self.assertEqual(value['unquoted_spans'],[])

    def test_suggestion_evidence_does_not_cover_missing_facts(self):
        result={'sections':{},'suggestions':[{'basis':['Keep the receipt.']}], 'issues':[], 'status':'incomplete_draft'}
        add_source_coverage(result,'Keep the receipt.')
        self.assertEqual(result['review_excerpts'][0]['text'],'Keep the receipt.')
        self.assertEqual(result['status'],'incomplete_draft')

    def test_heading_is_not_an_unreported_event(self):
        value=evidence_coverage('IMPACT:\nNo delay.',{'impact':[{'evidence':['No delay.']}]})
        self.assertEqual(value['unquoted_spans'],[])

    def test_decimal_and_reference_remain_intact(self):
        result={'sections':{},'issues':[],'status':'needs_confirmation'}
        add_source_coverage(result,'Saved 10.5 MB under REF.42; completion unknown.')
        self.assertEqual(result['review_excerpts'][0]['text'],'Saved 10.5 MB under REF.42; completion unknown.')

    def test_existing_excerpt_not_duplicated(self):
        item={'text':'Not checked.','evidence':['Not checked.']}
        result={'sections':{},'issues':[],'status':'needs_confirmation','review_excerpts':[item]}
        add_source_coverage(result,'Not checked.')
        self.assertEqual(result['review_excerpts'],[item])

    def test_no_discard_of_long_passage(self):
        source='detail '*600
        result={'sections':{},'issues':[],'status':'needs_confirmation'}
        add_source_coverage(result,source)
        self.assertEqual(' '.join(f['text'] for f in result['review_excerpts']),source.strip())
        self.assertTrue(all(f['text'] in source for f in result['review_excerpts']))


if __name__=='__main__': unittest.main()
