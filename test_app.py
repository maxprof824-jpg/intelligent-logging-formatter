import unittest
from app_v2 import draft_status, evidence_rows, format_followup


class AppReviewTests(unittest.TestCase):
    def test_empty_model_response_is_not_presented_as_success(self):
        self.assertIn('No supported entries',draft_status({'sections':{'situation':[]}}))

    def test_partial_output_is_prominent(self):
        self.assertIn('Draft not completed',draft_status({'status':'incomplete_draft'}))
        self.assertIn('Partial draft',draft_status({'status':'incomplete_draft','sections':{'situation':[{}]}}))

    def test_unassigned_count_visible(self):
        result={'sections':{'action':[{'text':'Filed the copy.'}]},'review_excerpts':[{}]}
        self.assertIn('1 source passage',draft_status(result))

    def test_evidence_is_linked_to_each_fact(self):
        result={'sections':{'action':[{'text':'Filed the copy.','evidence':['I filed a copy.']}]}}
        self.assertEqual(evidence_rows(result),[['Supplied notes','ACTION','Filed the copy.','I filed a copy.','Not recorded in this saved result']])

    def test_followup_text_does_not_create_a_model_supplied_link(self):
        text=format_followup({'questions':['[Visit](https://example.com) <script>']})
        self.assertNotIn('[Visit](',text)
        self.assertNotIn('<script>',text)


if __name__=='__main__': unittest.main()
