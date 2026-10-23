from types import SimpleNamespace

from django.test import SimpleTestCase

from api.domain import final_json_to_text
from api.llm import MATERIALS_BUDGET_CHARS, trim_materials
from api.rag import diversify_style_chunks


class DiversifyStyleChunksTests(SimpleTestCase):
    def test_limits_per_source_and_dedups(self):
        chunks = [
            SimpleNamespace(content="a" * 100, reference_id=1, generated_id=None, id=1),
            SimpleNamespace(content="b" * 100, reference_id=1, generated_id=None, id=2),
            SimpleNamespace(content="c" * 100, reference_id=1, generated_id=None, id=3),
            SimpleNamespace(content="b" * 100, reference_id=2, generated_id=None, id=4),
            SimpleNamespace(content="d" * 100, reference_id=2, generated_id=None, id=5),
            SimpleNamespace(content="e" * 100, generated_id=9, reference_id=None, id=6),
        ]
        selected = diversify_style_chunks(chunks, limit=8, max_per_source=2)
        self.assertEqual(len(selected), 4)
        self.assertEqual(selected.count("a" * 100), 1)
        self.assertEqual(selected.count("b" * 100), 1)
        self.assertIn("d" * 100, selected)
        self.assertIn("e" * 100, selected)

    def test_truncates_long_chunks(self):
        chunks = [
            SimpleNamespace(content="x" * 2000, reference_id=1, generated_id=None, id=1),
        ]
        selected = diversify_style_chunks(chunks, max_chars=100)
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(selected[0]), 100)


class TrimMaterialsTests(SimpleTestCase):
    def test_splits_budget_across_files(self):
        materials = [
            {"filename": "a.pdf", "text": "A" * 20000},
            {"filename": "b.pdf", "text": "B" * 20000},
        ]
        trimmed = trim_materials(materials, total_budget=24000)
        self.assertEqual(len(trimmed[0]["text"]), 12000)
        self.assertEqual(len(trimmed[1]["text"]), 12000)
        total = sum(len(item["text"]) for item in trimmed)
        self.assertLessEqual(total, MATERIALS_BUDGET_CHARS)


class FinalJsonToTextTests(SimpleTestCase):
    def test_includes_handout_and_links(self):
        text = final_json_to_text({
            "title": "WW2 vocab",
            "aim": "Practise past forms",
            "sub_aim": "",
            "homework": "Ex 3",
            "handout": "Gap fill about wartime life",
            "links": ["https://wordwall.net/resource/1"],
            "stages": [
                {
                    "stage": "Lead-in",
                    "procedure": "Show photo",
                    "time": "5",
                    "interaction": "WC",
                }
            ],
        })
        self.assertIn("Handout: Gap fill about wartime life", text)
        self.assertIn("https://wordwall.net/resource/1", text)
        self.assertIn("Lead-in | Show photo | 5 WC", text)
