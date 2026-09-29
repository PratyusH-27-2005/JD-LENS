from app.pipeline.ingest import clean, content_hash


def test_clean_collapses_spaces_and_blank_lines_but_keeps_line_breaks():
    raw = "  Stipend :\t Rs. 25,00   Per Month  \r\n\r\n\r\n\r\nCTC : 12 LPA \n"
    assert clean(raw) == "Stipend : Rs. 25,00 Per Month\n\nCTC : 12 LPA"


def test_same_posting_with_different_whitespace_has_same_hash():
    a = "Kasparro\nStipend : Rs. 25,00 Per Month"
    b = "  Kasparro \r\n Stipend :  Rs. 25,00\tPer Month\n\n"
    assert content_hash(clean(a)) == content_hash(clean(b))


def test_different_text_has_different_hash():
    assert content_hash(clean("Rs. 25,00")) != content_hash(clean("Rs. 25,000"))
