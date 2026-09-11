import unittest
import random

from event_groups import MAX_GROUPS, MAX_LABEL_LENGTH, locate_evidence, split_events


class EventGroupTests(unittest.TestCase):
    def assert_mapping(self, source, event):
        for segment in event["source_segments"]:
            self.assertEqual(
                event["source_text"][segment["local_start"]:segment["local_end"]],
                source[segment["start"]:segment["end"]],
            )

    def test_plain_notes_remain_one_unseparated_group(self):
        source = "  09:00Z a form arrived.\n\n10:00Z the printer stopped.\n"
        events = split_events(source)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["grouping"], "unseparated")
        self.assertEqual(events[0]["source_text"], source)
        self.assertEqual(events[0]["source_segments"], [{
            "local_start": 0, "local_end": len(source), "start": 0, "end": len(source),
        }])

    def test_inline_heading_like_text_does_not_split(self):
        for source in ("The note says EVENT: a printer issue.",
                       "09:00Z EVENT: a printer issue.", "# EVENT: a printer issue."):
            with self.subTest(source=source):
                events = split_events(source)
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["grouping"], "unseparated")

    def test_explicit_headings_preserve_display_labels_and_original_slices(self):
        source = "EVENT: Form delivery\r\n09:00Z received.\r\n\reVeNt : Printer issue\n10:00Z stopped."
        events = split_events(source)
        self.assertEqual([event["label"] for event in events], ["Form delivery", "Printer issue"])
        self.assertEqual([event["event_id"] for event in events], ["event-1", "event-2"])
        self.assertEqual(events[0]["source_text"], "09:00Z received.\r\n\r")
        self.assertEqual(events[1]["source_text"], "10:00Z stopped.")
        self.assertTrue(all(event["grouping"] == "explicit" for event in events))
        for event in events:
            self.assert_mapping(source, event)

    def test_repeated_labels_collect_noncontiguous_updates(self):
        source = "EVENT: Form  Delivery\nFirst update.\nEVENT: Printer\nPrinter note.\nEVENT: form\t delivery\nLater update."
        events = split_events(source)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["label"], "Form  Delivery")
        self.assertEqual(events[0]["event_id"], "event-1")
        self.assertEqual(events[0]["source_text"], "First update.\n\nLater update.")
        self.assertEqual(len(events[0]["source_segments"]), 2)
        self.assertNotIn("Printer note", events[0]["source_text"])
        for event in events:
            self.assert_mapping(source, event)

    def test_preamble_remains_separate_unassigned_context(self):
        source = "Shared handover note; owner unclear.\nEVENT: Printer\nPaper supplied.\nEVENT: Form\nForm received."
        events = split_events(source)
        self.assertEqual(events[0]["grouping"], "unassigned_context")
        self.assertEqual(events[0]["source_text"], "Shared handover note; owner unclear.\n")
        self.assertEqual([event["event_id"] for event in events], ["event-1", "event-2", "event-3"])
        self.assertNotIn("owner unclear", events[1]["source_text"])
        self.assertNotIn("owner unclear", events[2]["source_text"])

    def test_whitespace_preamble_does_not_create_empty_group(self):
        events = split_events("\n  \nEVENT: Form\nForm received.")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], "event-1")

    def test_repeated_quote_within_event_returns_all_occurrences(self):
        source = "EVENT: Form\nReceived. Received."
        event = split_events(source)[0]
        found = locate_evidence(event, "Received.")
        starts = [candidate["segments"][0]["start"] for candidate in found["candidates"]]
        self.assertEqual(starts, [source.index("Received."), source.rindex("Received.")])
        self.assertTrue(found["ambiguous"])

    def test_repeated_quote_in_later_same_event_update_is_ambiguous(self):
        source = "EVENT: Form\nReceived.\nEVENT: Printer\nOther.\nEVENT: Form\nReceived."
        found = locate_evidence(split_events(source)[0], "Received.")
        self.assertEqual(len(found["candidates"]), 2)
        self.assertTrue(found["ambiguous"])

    def test_same_quote_in_different_events_is_scoped_to_its_event(self):
        source = "EVENT: Form\nReceived.\nEVENT: Printer\nReceived."
        events = split_events(source)
        matches = [locate_evidence(event, "Received.") for event in events]
        self.assertTrue(all(not match["ambiguous"] for match in matches))
        self.assertNotEqual(matches[0]["candidates"], matches[1]["candidates"])
        self.assertEqual(matches[1]["candidates"][0]["segments"][0]["start"], source.rindex("Received."))

    def test_cross_join_quote_maps_separate_original_spans(self):
        source = "EVENT: Form\nFirst.\nEVENT: Printer\nOther.\nEVENT: Form\nLater."
        event = split_events(source)[0]
        found = locate_evidence(event, "First.\n\nLater.")
        self.assertEqual(found, {"candidates": [{"segments": [
            {"start": source.index("First."), "end": source.index("First.") + len("First.\n")},
            {"start": source.index("Later."), "end": len(source)},
        ]}], "ambiguous": False})
        self.assertNotIn("Other.", "".join(source[s["start"]:s["end"]] for s in found["candidates"][0]["segments"]))

    def test_synthetic_newline_alone_does_not_invent_an_original_location(self):
        source = "EVENT: Form\nFirst.\nEVENT: Form\nLater."
        event = split_events(source)[0]
        # One real body newline plus one synthetic joining newline exist in
        # source_text; only the real character has an original source span.
        found = locate_evidence(event, "\n")
        original_newline = source.index("\n", source.index("First."))
        self.assertEqual(found, {"candidates": [{"segments": [
            {"start": original_newline, "end": original_newline + 1},
        ]}], "ambiguous": False})

    def test_overlapping_occurrences_are_preserved(self):
        event = split_events("aaa")[0]
        self.assertEqual(locate_evidence(event, "aa"), {"candidates": [
            {"segments": [{"start": 0, "end": 2}]},
            {"segments": [{"start": 1, "end": 3}]},
        ], "ambiguous": True})

    def test_missing_quote_returns_no_candidates(self):
        self.assertEqual(locate_evidence(split_events("Received.")[0], "Not supplied."),
                         {"candidates": [], "ambiguous": False})

    def test_unicode_offsets_are_python_codepoint_offsets(self):
        source = "🗒️ note\nEVENT: Réception\n🙂 reçu."
        event = split_events(source)[1]
        found = locate_evidence(event, "reçu")
        start = found["candidates"][0]["segments"][0]["start"]
        self.assertEqual(start, source.index("reçu"))
        self.assertNotEqual(start, len(source[:start].encode("utf-16-le")) // 2)
        self.assert_mapping(source, event)

    def test_empty_source_and_empty_labels_have_helpful_errors(self):
        for source in ("", " \n\t"):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "Enter notes"):
                split_events(source)
        for source in ("EVENT:\nSome note.", "EVENT: \t\nSome note."):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "line 1.*label"):
                split_events(source)

    def test_empty_heading_bodies_are_rejected(self):
        for source in ("EVENT: Form", "EVENT: Form\n\n", "EVENT: Form\nEVENT: Printer\nSome note.",
                       "EVENT: Form\nEVENT: Form\nLater note."):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "has no notes"):
                split_events(source)

    def test_label_length_limit(self):
        self.assertEqual(len(split_events("EVENT: " + "a" * MAX_LABEL_LENGTH + "\nBody.")), 1)
        with self.assertRaisesRegex(ValueError, "exceeds 100 characters"):
            split_events("EVENT: " + "a" * (MAX_LABEL_LENGTH + 1) + "\nBody.")

    def test_group_limit_counts_unique_labels_and_preamble(self):
        body = "\n".join(f"EVENT: Item {i}\nBody." for i in range(MAX_GROUPS))
        self.assertEqual(len(split_events(body)), MAX_GROUPS)
        self.assertEqual(len(split_events(body + "\nEVENT: Item 0\nLater.")), MAX_GROUPS)
        for source in (body + "\nEVENT: Extra\nExtra body.", "Preamble.\n" + body):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "more than 8 event groups"):
                split_events(source)

    def test_invalid_types_and_empty_quote_are_rejected(self):
        with self.assertRaises(TypeError):
            split_events(None)
        event = split_events("Body.")[0]
        with self.assertRaisesRegex(ValueError, "nonempty"):
            locate_evidence(event, "")
        with self.assertRaises(TypeError):
            locate_evidence(event, None)

    def test_repeated_occurrences_intersect_only_nearby_segments(self):
        class CountedSegments(list):
            accesses=0
            def __iter__(self):
                for value in super().__iter__():
                    self.accesses+=1
                    yield value
            def __getitem__(self,index):
                self.accesses+=1
                return super().__getitem__(index)
        count=200
        event=split_events('EVENT: Status\nPending.\n'*count)[0]
        segments=CountedSegments(event['source_segments'])
        event['source_segments']=segments
        found=locate_evidence(event,'Pending.')
        self.assertEqual(len(found['candidates']),count)
        self.assertLessEqual(segments.accesses,4*count)

    def test_matches_equal_exhaustive_codepoint_mapping_for_disjoint_unicode_inputs(self):
        rng=random.Random(47)
        separators=['\n','\r','\r\n','\v','\f','\x1c','\x1d','\x1e','\x85','\u2028','\u2029']
        source='🙂 Préambule.\r\n'
        for index in range(18):
            newline=separators[index%len(separators)]
            source+='EVENT: '+['Réception','Dossier','Avis'][index%3]+newline
            source+=['🙂 reçu.','échéance inconnue.','未確認.'][index%3]+newline
        for event in split_events(source):
            mapping={}
            for segment in event['source_segments']:
                for local in range(segment['local_start'],segment['local_end']):
                    mapping[local]=segment['start']+local-segment['local_start']
            for _ in range(35):
                start=rng.randrange(len(event['source_text']))
                quote=event['source_text'][start:start+rng.randint(1,20)]
                expected=[];cursor=0
                while True:
                    position=event['source_text'].find(quote,cursor)
                    if position<0:break
                    spans=[]
                    for local in range(position,position+len(quote)):
                        if local not in mapping:continue
                        original=mapping[local]
                        if spans and spans[-1]['end']==original:spans[-1]['end']=original+1
                        else:spans.append({'start':original,'end':original+1})
                    if spans and {'segments':spans} not in expected:expected.append({'segments':spans})
                    cursor=position+1
                self.assertEqual(locate_evidence(event,quote),{'candidates':expected,'ambiguous':len(expected)>1})


if __name__ == "__main__":
    unittest.main()
