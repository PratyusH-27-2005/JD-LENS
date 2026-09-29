import pytest

from app.pipeline.normalize.cgpa import parse_cgpa
from app.pipeline.normalize.result import Normalized
from app.pipeline.pdf import PdfUnreadable, pdf_to_text
from tests.resume_fixtures import RESUME_LINES, make_pdf


@pytest.mark.parametrize(
    ("text", "cgpa"),
    [
        ("CGPA: 8.4/10", 8.4),
        ("CGPA 8.10", 8.1),
        ("8.4 CGPA", 8.4),
        ("CPI - 9.0", 9.0),
        ("B.Tech CSE, 2022-2026, CGPA: 7.85 (till 6th sem)", 7.85),
        ("8.4/10", 8.4),
        ("Cumulative GPA of 9.2", 9.2),
    ],
)
def test_parse_cgpa_ok(text, cgpa):
    assert parse_cgpa(text) == Normalized(value={"cgpa": cgpa})


@pytest.mark.parametrize(
    ("text", "reason_part"),
    [
        ("GPA: 3.7/4.0", "not on a 10-point scale"),
        ("Class XII: 91%", "no CGPA found"),
        ("CGPA: 8.1, SGPA: 9.0", "more than one CGPA"),
        ("CGPA 85", "above 10"),
    ],
)
def test_parse_cgpa_flags_instead_of_converting(text, reason_part):
    result = parse_cgpa(text)
    assert result.flag == "ambiguous"
    assert reason_part in result.reason


def test_pdf_to_text_reads_every_line():
    text = pdf_to_text(make_pdf(RESUME_LINES))
    for line in RESUME_LINES:
        assert line in text


@pytest.mark.parametrize(
    ("data", "reason_part"),
    [
        (b"PK\x03\x04 this is a zip, e.g. a .docx", "isn't a PDF"),
        (b"%PDF-1.4\nnot really a pdf", "damaged"),
        (make_pdf([]), "no text found"),  # like a scanned image
    ],
)
def test_pdf_to_text_refuses_unreadable_files(data, reason_part):
    with pytest.raises(PdfUnreadable, match=reason_part):
        pdf_to_text(data)
