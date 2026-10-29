"""Build original, deterministic laboratory PDFs; never index them automatically."""

import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf"


def draw_paragraph(canvas, text, x, top, width, style):
    paragraph = Paragraph(text, style)
    _, height = paragraph.wrap(width, 750)
    if top - height < 85:
        raise ValueError("Conteúdo excede a área da página; revise o layout antes de publicar.")
    paragraph.drawOn(canvas, x, top - height)
    return top - height


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overwrite", action="store_true", help="Regenerar somente os PDFs do corpus"
    )
    args = parser.parse_args()
    corpus = json.loads((ROOT / "examples/lab/corpus.json").read_text(encoding="utf-8"))
    for document in corpus["documents"]:
        filename = document["filename"]
        if Path(filename).name != filename or not filename.endswith(".pdf"):
            raise ValueError("O corpus deve usar nomes simples de PDF.")
        if (OUTPUT / filename).exists() and not args.overwrite:
            raise FileExistsError("PDF já existe. Para regenerar o corpus, use --overwrite.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    body = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#243449"),
        alignment=TA_LEFT,
    )
    heading = ParagraphStyle("heading", parent=body, fontName="Helvetica-Bold", fontSize=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=11)
    title = ParagraphStyle("title", parent=heading, fontSize=24, leading=29)
    for document in corpus["documents"]:
        path = OUTPUT / document["filename"]
        canvas = Canvas(str(path), pagesize=A4, invariant=1)
        canvas.setTitle(document["title"])
        canvas.setAuthor("NetOps AI - material autoral de laboratório")
        width, height = A4
        for number, page in enumerate(document["pages"], 1):
            canvas.setFillColor(colors.HexColor("#10344C"))
            canvas.rect(0, height - 14, width, 14, fill=1, stroke=0)
            canvas.setFont("Helvetica-Bold", 10)
            canvas.drawString(48, height - 48, "NETOPS AI / BASE DE LABORATÓRIO")
            canvas.setFillColor(colors.HexColor("#557084"))
            canvas.setFont("Helvetica", 9)
            canvas.drawString(48, height - 68, document["title"])
            y = draw_paragraph(canvas, escape(page["title"]), 48, height - 100, width - 96, title)
            y = (
                draw_paragraph(
                    canvas,
                    "Windows 11 / IPv4 / Consulta e observação",
                    48,
                    y - 12,
                    width - 96,
                    small,
                )
                - 24
            )
            for section in page["sections"]:
                y = draw_paragraph(canvas, escape(section["title"]), 48, y, width - 96, heading)
                y = (
                    draw_paragraph(canvas, escape(section["text"]), 48, y - 7, width - 96, body)
                    - 19
                )
            y = (
                draw_paragraph(
                    canvas,
                    "Referências oficiais / consulta em 29/10/2026",
                    48,
                    y - 3,
                    width - 96,
                    heading,
                )
                - 8
            )
            for source in page["sources"]:
                url = escape(source["url"])
                text = f'{escape(source["label"])}<br/><link href="{url}">{url}</link>'
                y = draw_paragraph(canvas, text, 48, y, width - 96, small) - 9
            canvas.setStrokeColor(colors.HexColor("#CEDBE3"))
            canvas.line(48, 65, width - 48, 65)
            canvas.setFillColor(colors.HexColor("#557084"))
            canvas.setFont("Helvetica", 8)
            canvas.drawString(
                48, 49, f"{corpus['version']} | Estudo; não substitui procedimento aprovado."
            )
            canvas.drawRightString(width - 48, 49, f"Página {number} / {len(document['pages'])}")
            canvas.showPage()
        canvas.save()
        print(path)


if __name__ == "__main__":
    main()
