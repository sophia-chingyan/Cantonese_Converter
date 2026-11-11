"""Tests for the skipped-sentence check and its retry / fallback.

Run with:  python -m unittest discover tests
"""
import unittest

from extractors.base import ExtractedDocument
from jobs import registry, runner
from translator import TranslatorClient, chunk_document, incompleteness_reason

SOURCE = "我們今天去公園。他們沒有來。天氣很好。我們很開心。"
FULL = "我哋今日去咗公園。佢哋冇嚟。天氣好好。我哋好開心。"
MISSING = "我哋今日去咗公園。天氣好好。"  # dropped two sentences

CONFIG = {"CHUNK_SIZE_CHARS": 1500, "CONTEXT_CARRYOVER_CHARS": 200}


class ScriptedClient(TranslatorClient):
    name = "fake"

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        return answer(prompt) if callable(answer) else answer


def run(doc, client):
    runner.get_client = lambda provider, config: client
    runner.load_entries = lambda config: []
    chunks = chunk_document(doc, CONFIG["CHUNK_SIZE_CHARS"])
    job_id = registry.create_job(len(chunks), doc.kind, "txt", None)
    runner._translate_all(job_id, doc, chunks, "fake", CONFIG, [])
    return registry.get_job(job_id)


class ReasonTests(unittest.TestCase):
    def test_complete(self):
        self.assertIsNone(incompleteness_reason(SOURCE, FULL))

    def test_missing_sentences(self):
        self.assertIsNotNone(incompleteness_reason(SOURCE, MISSING))


class RunnerTests(unittest.TestCase):
    def test_retry_recovers_skipped_sentences(self):
        client = ScriptedClient([MISSING, FULL])
        job = run(ExtractedDocument(kind="plain", paragraphs=[SOURCE]), client)
        self.assertEqual(job["preview_text"], FULL)
        self.assertFalse(job["has_failures"])
        self.assertEqual(len(client.prompts), 2)

    def test_falls_back_to_paragraphs(self):
        # Whole chunk keeps losing the second paragraph; each paragraph
        # on its own comes back complete.
        client = ScriptedClient([FULL, FULL, FULL, FULL])
        doc = ExtractedDocument(kind="plain", paragraphs=[SOURCE, SOURCE])
        job = run(doc, client)
        self.assertEqual(job["preview_text"], FULL + "\n\n" + FULL)
        self.assertFalse(job["has_failures"])
        self.assertIn("2 paragraphs", client.prompts[0])

    def test_marks_when_still_incomplete(self):
        client = ScriptedClient([MISSING] * 4)
        job = run(ExtractedDocument(kind="plain", paragraphs=[SOURCE]), client)
        self.assertTrue(job["has_failures"])
        self.assertTrue(job["preview_text"].startswith(runner.INCOMPLETE_MARKER))
        self.assertIn(SOURCE, job["preview_text"])


if __name__ == "__main__":
    unittest.main()
