import unittest

from evidence_checks import factual_risk


class EvidenceRiskTests(unittest.TestCase):
    def test_reversed_negation_is_flagged(self):
        self.assertIn("negation", factual_risk("The form was sent.", ["The form was not sent."]))
        self.assertIn("negation", factual_risk("The form was not sent.", ["The form was sent."]))

    def test_contracted_negation_is_preserved(self):
        self.assertIsNone(factual_risk("The form was not sent.", ["The form wasn't sent."]))
        self.assertIn("negation", factual_risk("The form was sent.", ["The form wasn't sent."]))

    def test_requested_and_planned_work_are_not_completed(self):
        for quote in ("The desk planned to check the file.", "The desk would check the file.",
                      "The desk was asked to check the file."):
            with self.subTest(quote=quote):
                self.assertIn("completed", factual_risk("The desk checked the file.", [quote]))

    def test_stated_plan_and_request_can_be_paraphrased(self):
        self.assertIsNone(factual_risk("The desk will check the file.", ["The desk planned to check the file."]))
        self.assertIsNone(factual_risk("The desk was asked to review the form.", ["I asked the desk to review the form."]))

    def test_imperative_plan_does_not_treat_object_adjectives_as_completed_verbs(self):
        self.assertIsNone(factual_risk("Confirm the approved copy tomorrow.", [
            "I will confirm the approved copy tomorrow."
        ]))
        self.assertIsNone(factual_risk("Check the completed form.", [
            "I will check the completed form."
        ]))

    def test_uncertainty_cannot_become_certainty(self):
        self.assertIn("uncertainty", factual_risk("The report was delayed.", ["The report may have been delayed."]))
        self.assertIn("uncertainty", factual_risk("The caller initials were KR.", ["I think the caller initials were KR."]))

    def test_equivalent_uncertainty_can_be_retained(self):
        self.assertIsNone(factual_risk("The report might have been delayed.", ["The report may have been delayed."]))
        self.assertIsNone(factual_risk("The report delay is unconfirmed.", ["The report delay is not confirmed."]))

    def test_no_report_is_not_no_impact(self):
        self.assertIsNotNone(factual_risk("No impact.", ["No impact reported."]))
        self.assertIsNone(factual_risk("No impact has been confirmed.", ["No impact has been confirmed."]))

    def test_unstated_blanket_no_action_is_flagged(self):
        quote = "I stopped preparing the print bundle; I did not cancel the class."
        self.assertIn("blanket", factual_risk("The author stopped preparing the print bundle; no other action was taken.", [quote]))
        self.assertIn("blanket", factual_risk("Nothing else was done.", [quote]))
        self.assertIn("blanket", factual_risk("No further action was taken.", ["No further action was required."]))

    def test_explicit_no_action_is_preserved(self):
        self.assertIsNone(factual_risk("No other action was taken.", ["No other action was taken."]))
        self.assertIsNone(factual_risk("The author took no other action.", ["No other action was taken."]))

    def test_unrelated_negation_does_not_poison_positive_fact(self):
        quote = "I saved the workbook. I did not cancel the class."
        self.assertIsNone(factual_risk("The author saved the workbook.", [quote]))

    def test_unrelated_uncertainty_does_not_poison_positive_fact(self):
        quote = "I saved the workbook. The class attendance is unknown."
        self.assertIsNone(factual_risk("The author saved the workbook.", [quote]))

    def test_asking_whether_is_a_contact_not_an_uncertain_contact(self):
        self.assertIsNone(factual_risk("Contacted Records Desk (TM).", [
            "I asked Records Desk, initials TM, to check whether the catalog service was available."
        ]))

    def test_coordinated_negation_does_not_poison_a_positive_fact(self):
        self.assertIsNone(factual_risk("The author saved the original email without editing or forwarding.", [
            "I saved the original email. I did not edit it. I did not forward it."
        ]))
        self.assertIsNone(factual_risk("A status update is expected.", [
            "ES expects a status update, but nobody promised the correction would be completed."
        ]))
        self.assertIsNone(factual_risk("The author did not check the paper sheet.", [
            "Might just be a copied row, I didn't check the paper sheet."
        ]))

    def test_original_source_and_simple_cleanup_remain_accepted(self):
        for quote in ("I think Support (KR) replied, but this is not confirmed.",
                      "The desk planned to check the file.", "The form was not sent."):
            with self.subTest(quote=quote):
                self.assertIsNone(factual_risk(quote, [quote]))
        self.assertIsNone(factual_risk("At 09:10 UTC, the training console froze.", ["09:10 UTC training console froze"]))

    def test_iso_dates_are_compared_as_complete_values(self):
        self.assertIn("calendar date", factual_risk("The event was on 2026-11-09.", ["The event was on 2026-09-11."]))
        self.assertIsNone(factual_risk("On 2026-09-11 the event occurred.", ["The event occurred on 2026-09-11."]))

    def test_parenthesized_contact_initials_cannot_disappear(self):
        self.assertIn("initials", factual_risk("Support was contacted.", ["Support (KR) was contacted."]))
        self.assertIsNone(factual_risk("The author contacted Support (KR).", ["I contacted Support (KR). "]))
        self.assertIsNone(factual_risk("The form was saved.", ["The form was saved. Support (KR) was contacted."]))

    def test_lowercase_parentheses_are_not_assumed_to_be_initials(self):
        self.assertIsNone(factual_risk("Support was contacted.", ["Support (old) was contacted."]))

    def test_reference_ids_are_compared_as_complete_values(self):
        self.assertIn("reference identifier", factual_risk("Ticket REQ-12 was opened.", [
            "Ticket ANN-12 was opened."
        ]))
        self.assertIn("reference identifier", factual_risk("Reference ABC_91 was recorded.", [
            "Reference XYZ_91 was recorded."
        ]))
        self.assertIsNone(factual_risk("The author opened ticket ANN-12.", ["I opened ticket ANN-12."]))
        self.assertIsNone(factual_risk("The author reviewed the sign-in form.", ["I reviewed the sign-in form."]))


if __name__ == "__main__":
    unittest.main()
