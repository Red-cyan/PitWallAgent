from app.schemas.pdf import PdfPage, PdfTable
from app.services.regulation_parser import RegulationStructureParser


def test_parser_carries_clause_across_pages_and_rejects_header_clause() -> None:
    pages = [
        PdfPage(page_number=10, text="B10 2026 Formula 1: Sporting Regulations\nB5.14.2 Unsafe release\nCars must not be released unsafely."),
        PdfPage(page_number=11, text="This obligation continues on the next page.\nB5.14.3\nThe stewards may impose a penalty."),
    ]

    document = RegulationStructureParser().parse("FIA 2026 F1 Regulations - Section B", pages)
    clauses = [clause for article in document.articles for clause in article.clauses]

    assert [clause.clause_id for clause in clauses] == ["B5.14.2", "B5.14.3"]
    assert clauses[0].page_start == 10
    assert clauses[0].page_end == 11
    assert "continues on the next page" in clauses[0].content


def test_parser_preserves_nested_list_and_owned_table() -> None:
    table = PdfTable(page_number=4, headers=["Item", "Limit"], rows=[["ATR", "80%"]])
    page = PdfPage(
        page_number=4,
        text="C2.1 Requirements\na.\nFirst requirement.\ni)\nNested requirement.",
        tables=[table],
    )

    clause = RegulationStructureParser().parse("FIA 2026 F1 Regulations - Section C", [page]).articles[0].clauses[0]

    assert clause.list_items == ["a. First requirement.", "i) Nested requirement."]
    assert clause.tables == [table]


def test_parser_skips_contents_continuation_page() -> None:
    page = PdfPage(
        page_number=2,
        text="A4.1\nFit and Proper Persons Test\n17\nA4.2\nAnti-doping\n17\nA4.3\nSafeguarding\n18",
    )

    document = RegulationStructureParser().parse("FIA 2026 F1 Regulations - Section A", [page])

    assert document.articles == []


def test_parser_keeps_reprinted_clause_under_appendix_scope() -> None:
    page = PdfPage(page_number=20, text="APPENDIX B6: APPROVED CHANGES\nB2.5.2\nReplacement race distance text.")

    clause = RegulationStructureParser().parse("FIA 2026 F1 Regulations - Section B", [page]).articles[0].clauses[0]

    assert clause.clause_id == "B2.5.2"
    assert clause.scope == "APPENDIX B6"


def test_parser_recognizes_prefixed_article_heading() -> None:
    page = PdfPage(page_number=12, text="ARTICLE D5: EXCLUSIONS\nD5.1\nRelevant costs may exclude listed items.")

    article = RegulationStructureParser().parse("FIA 2026 F1 Regulations - Section D", [page]).articles[0]

    assert article.article_id == "D5"
    assert article.title == "EXCLUSIONS"
    assert [clause.clause_id for clause in article.clauses] == ["D5", "D5.1"]
