from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from council.context import build_brief, context_record, evidence_file, read_text
from council.demo import BRIEF, decision, opinion
from council.schema import CouncilError, ValidationError, strict_json, validate_brief, validate_result


class SchemaTests(unittest.TestCase):
    def test_valid_fixtures(self):
        validate_brief(BRIEF)
        validate_result(decision(), 'decision', {'E1'})
        for role in ('believer', 'skeptic', 'operator'):
            validate_result(opinion(role), 'opinion', {'E1'})

    def test_strict_json_rejects_duplicate_nan_fences_trailing(self):
        for raw in ('{"a":1,"a":2}', '{"n":NaN}', '```json\n{}\n```', '{} {}', '[] trailing'):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                strict_json(raw)

    def test_extra_and_missing_fields_rejected(self):
        for change in ('extra', 'missing'):
            data = decision()
            if change == 'extra':
                data['execute_now'] = True
            else:
                del data['next_action']
            with self.assertRaises(ValidationError):
                validate_result(data, 'decision', {'E1'})

    def test_unknown_or_duplicate_evidence_rejected(self):
        for ids in (['E9'], ['E1', 'E1']):
            data = decision()
            data['rationale'][0]['evidence_ids'] = ids
            with self.assertRaises(ValidationError):
                validate_result(data, 'decision', {'E1'})

    def test_fact_requires_citation(self):
        data = opinion('skeptic')
        data['claims'][0]['evidence_ids'] = []
        with self.assertRaises(ValidationError):
            validate_result(data, 'opinion', {'E1'})
        data['claims'][0]['kind'] = 'assumption'
        validate_result(data, 'opinion', {'E1'})

    def test_proceed_and_high_strength_require_premise(self):
        for key, value in [('decision', 'proceed'), ('evidence_strength', 'high')]:
            data = decision()
            data[key] = value
            data['rationale'][0]['evidence_ids'] = []
            with self.assertRaises(ValidationError):
                validate_result(data, 'decision', {'E1'})

    def test_review_must_reference_actual_candidate(self):
        data = {'critiques': [{'candidate_id': 'Z', 'issue': 'Unsupported', 'basis': 'assumption',
                              'evidence_ids': [], 'would_change_decision': True}],
                'strongest_counterargument': 'No data', 'unresolved': []}
        with self.assertRaises(ValidationError):
            validate_result(data, 'review', {'E1'}, {'A'})
        data['critiques'][0]['candidate_id'] = 'A'
        validate_result(data, 'review', {'E1'}, {'A'})

    def test_bool_is_not_integer_coercion(self):
        data = decision()
        data['decision'] = True
        with self.assertRaises(ValidationError):
            validate_result(data, 'decision', {'E1'})

    def test_blank_control_and_oversized_text_rejected(self):
        for text in (' ', 'bad\x00text', 'x' * 1000):
            data = decision()
            data['recommendation'] = text
            with self.assertRaises(ValidationError):
                validate_result(data, 'decision', {'E1'})

    def test_duplicate_and_invalid_evidence_ids_rejected(self):
        for eid in ('E1', 'source-two'):
            brief = copy.deepcopy(BRIEF)
            brief['evidence'].append(dict(brief['evidence'][0], id=eid))
            with self.assertRaises(ValidationError):
                validate_brief(brief)

    def test_brief_byte_budget_is_utf8_aware(self):
        brief = copy.deepcopy(BRIEF)
        brief['question'] = '界' * 16000
        with self.assertRaises(ValidationError):
            validate_brief(brief)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_exact_lines_and_hash_without_absolute_path(self):
        p = self.root / 'spec.txt'
        p.write_text('first\nsecond\nthird\n', encoding='utf-8')
        e = context_record(f'{p}::2:3', 'E1')
        self.assertEqual(e['excerpt'], 'second\nthird')
        self.assertIn('#L2-L3; sha256:', e['source'])
        self.assertNotIn(str(self.root), e['source'])

    def test_bad_line_ranges(self):
        p = self.root / 'x.txt'
        p.write_text('a\nb', encoding='utf-8')
        for suffix in ('0:2', '2:1', '1:4', 'all'):
            with self.assertRaises(CouncilError):
                context_record(f'{p}::{suffix}', 'E1')

    def test_credential_paths_and_content_are_blocked(self):
        for name, text in [('.env', 'harmless'), ('auth.json', '{}'), ('key.pem', 'text'),
                           ('plain.txt', 'sk-proj-' + 'a' * 40)]:
            p = self.root / name
            p.write_text(text, encoding='utf-8')
            with self.assertRaises(CouncilError):
                context_record(str(p), 'E1')

    def test_binary_oversized_and_invalid_utf8_rejected(self):
        p = self.root / 'file'
        for raw in (b'a\x00b', b'\xff', b'12345'):
            p.write_bytes(raw)
            with self.assertRaises(CouncilError):
                read_text(p, 4)

    def test_context_ids_skip_supplied_records(self):
        p = self.root / 'note.txt'
        p.write_text('Selected context', encoding='utf-8')
        brief = build_brief('Which option?', 'technical', [], [str(p)], BRIEF['evidence'])
        self.assertEqual([e['id'] for e in brief['evidence']], ['E1', 'E2'])

    def test_evidence_file_contract(self):
        p = self.root / 'evidence.json'
        p.write_text(json.dumps(BRIEF['evidence']), encoding='utf-8')
        self.assertEqual(evidence_file(p), BRIEF['evidence'])
        p.write_text('{}', encoding='utf-8')
        with self.assertRaises(CouncilError):
            evidence_file(p)

    def test_question_secret_detected(self):
        with self.assertRaises(CouncilError):
            build_brief('Use Bearer ' + 'a' * 30, 'general', [], [], [])
