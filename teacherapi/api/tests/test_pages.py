from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase
from pydantic import ValidationError

from api.domain import parse_pages
from api.media import extract_text, get_pdf
from api.schemas import GeneratedLessonResponse, LessonGenerateRequest


class ParsePagesTests(SimpleTestCase):
    def test_range_and_list(self):
        self.assertEqual(parse_pages("12-18"), list(range(12, 19)))
        self.assertEqual(parse_pages("12,15,20-22"), [12, 15, 20, 21, 22])
        self.assertEqual(parse_pages(" 3 - 5 , 1 "), [1, 3, 4, 5])
        self.assertEqual(parse_pages(""), [])
        self.assertEqual(parse_pages(None), [])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            parse_pages("12-")
        with self.assertRaises(ValueError):
            parse_pages("abc")
        with self.assertRaises(ValueError):
            parse_pages("0-2")


class PagesSchemaTests(SimpleTestCase):
    def test_normalize_blank_and_valid(self):
        req = LessonGenerateRequest(topic="T", level="A2", pages=" 12-14 ")
        self.assertEqual(req.pages, "12-14")
        blank = LessonGenerateRequest(topic="T", level="A2", pages="  ")
        self.assertIsNone(blank.pages)

    def test_invalid_pages_raise(self):
        with self.assertRaises(ValidationError):
            LessonGenerateRequest(topic="T", level="A2", pages="nope")


class ResponseFactoryTests(SimpleTestCase):
    def test_generated_lesson_response_of(self):
        class Lesson:
            id = 7
            topic = "Clothes"
            level = "A2"
            status = "draft"
            final = None
            task_id = "abc"

        response = GeneratedLessonResponse.of(
            Lesson(),
            draft={"title": "X"},
            iteration_number=2,
        )
        self.assertEqual(response.id, 7)
        self.assertEqual(response.draft, {"title": "X"})
        self.assertEqual(response.iteration_number, 2)


class PdfPageFilterTests(SimpleTestCase):
    @patch("api.media.get_pdf_pages")
    def test_filters_pages_with_markers(self, mock_pages):
        mock_pages.return_value = [
            (1, "ALPHA_PAGE"),
            (2, "BRAVO_PAGE"),
            (3, "CHARLIE_PAGE"),
        ]
        path = Path("dummy.pdf")
        text = get_pdf(path, pages=[2])
        self.assertIn("[Page 2]", text)
        self.assertIn("BRAVO_PAGE", text)
        self.assertNotIn("ALPHA_PAGE", text)

        with self.assertRaises(ValueError):
            get_pdf(path, pages=[99])

    @patch("api.media.get_pdf")
    @patch("api.media.Path.exists", return_value=True)
    def test_extract_text_pdf_passes_pages(self, _exists, mock_get_pdf):
        mock_get_pdf.return_value = "[Page 2]\nX"
        result = extract_text("book.pdf", pages=[2])
        self.assertEqual(result, "[Page 2]\nX")
        self.assertEqual(mock_get_pdf.call_args.kwargs.get("pages"), [2])
