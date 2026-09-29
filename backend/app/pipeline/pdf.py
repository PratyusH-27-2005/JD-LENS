"""PDF → plain text for resumes. No LLM: if the text layer is missing (a scanned PDF),
we say so instead of guessing."""

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.pipeline.ingest import clean

MAX_PAGES = 10
MIN_TEXT_CHARS = 100  # below this there's no usable text layer

# pypdf warns loudly about harmless quirks in real-world PDFs.
logging.getLogger("pypdf").setLevel(logging.ERROR)


class PdfUnreadable(Exception):
    """The file isn't a PDF we can read text from. The message is safe to show the user."""


def pdf_to_text(data: bytes) -> str:
    if not data.startswith(b"%PDF-"):
        raise PdfUnreadable("that file isn't a PDF")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise PdfUnreadable("the PDF is password-protected")
        if len(reader.pages) > MAX_PAGES:
            raise PdfUnreadable(f"the PDF has more than {MAX_PAGES} pages; is it a resume?")
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as e:
        raise PdfUnreadable("the PDF is damaged or not a real PDF") from e
    text = clean(text)
    if len(text) < MIN_TEXT_CHARS:
        raise PdfUnreadable(
            "no text found in the PDF (a scanned image?). Export it as a text PDF and retry."
        )
    return text
