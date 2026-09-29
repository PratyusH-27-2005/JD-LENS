"""Test resumes: a tiny PDF writer (no binary fixtures in the repo) and a fictional CV."""

from typing import Any

RESUME_LINES = [
    "Asha Verma",
    "Bhubaneswar, Odisha | asha.verma@example.com",
    "EDUCATION",
    "B.Tech in Computer Science, KIIT University, 2022-2026. CGPA: 8.4/10",
    "Class XII (CBSE), 2022: 91%",
    "SKILLS",
    "Languages: Python, TypeScript, SQL",
    "Frameworks: FastAPI, React.js, Next.js",
    "Tools: PostgreSQL, Docker, Git",
    "PROJECTS",
    "JD Lens - a job posting parser with evidence checks (FastAPI, Postgres)",
]
RESUME_TEXT = "\n".join(RESUME_LINES)


def make_pdf(lines: list[str]) -> bytes:
    """A minimal valid one-page PDF with the lines as real text (Helvetica, ASCII)."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    content = "BT /F1 11 Tf 50 780 Td 14 TL\n"
    content += "".join(f"({esc(line)}) Tj T*\n" for line in lines) + "ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    return out


def mention(value: str | None, evidence: str | None = None) -> dict[str, str | None]:
    return {"value": value, "evidence": value if evidence is None else evidence}


def resume_response(**overrides: Any) -> dict[str, Any]:
    """What a well-behaved model returns for RESUME_TEXT."""
    skills = ["Python", "TypeScript", "SQL", "FastAPI", "React.js", "Next.js", "PostgreSQL"]
    response = {
        "schema_version": "1.0",
        "name": mention("Asha Verma"),
        "cgpa": mention("8.4/10", "CGPA: 8.4/10"),
        "skills": [{"name": s, "evidence": s} for s in [*skills, "Docker", "Git"]],
    }
    return response | overrides
