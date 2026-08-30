"""Тесты извлечения текста и сегментации документов материалов дела."""

from collections.abc import Callable

from app.case_materials.extraction import (
    DocumentSegmenter,
    DocxTextExtractor,
    ExtractedText,
    PdfTextExtractor,
)
from app.case_materials.fields.base import HIGH, LOW

RESOLUTION_LINES = [
    "УТВЕРЖДАЮ",
    "Начальник Иванов Иван Иванович",
    "ПОСТАНОВЛЕНИЕ",
    "о проведении оперативно-розыскного мероприятия",
    "Я, Петров Петр Петрович",
    "рассмотрев материалы рапорт",
    "руководствуясь ст. 7 Федерального закона от 12 августа 1995 г.",
    "провести оперативно-розыскное мероприятие «проверочная закупка»",
]


def test_pdf_extractor_returns_text(pdf_factory: Callable[[list[str]], bytes]) -> None:
    extracted = PdfTextExtractor().extract(pdf_factory(RESOLUTION_LINES), "x.pdf")

    assert "ПОСТАНОВЛЕНИЕ" in extracted.text
    assert len(extracted.pages) == 1


def test_docx_extractor_returns_text(
    docx_factory: Callable[[list[str]], bytes],
) -> None:
    extracted = DocxTextExtractor().extract(docx_factory(RESOLUTION_LINES), "x.docx")

    assert "ПОСТАНОВЛЕНИЕ" in extracted.text
    assert extracted.pages == [extracted.text]


def test_segmenter_splits_multiple_documents(
    pdf_factory: Callable[[list[str]], bytes],
) -> None:
    lines = [
        *RESOLUTION_LINES,
        "ПРОТОКОЛ",
        "досмотра лица, участвующего в оперативно-розыскном",
        "Я, Сидоров Сидор Сидорович",
        "в помещении ул. Ленина 1",
        "в присутствии незаинтересованных лиц (представителей общественности)",
    ]
    extracted = PdfTextExtractor().extract(pdf_factory(lines), "x.pdf")

    documents = DocumentSegmenter().segment(extracted)

    assert [d.kind.value for d in documents] == [
        "resolution_to_conduct_orm",
        "search_protocol_before",
    ]
    resolution = documents[0]
    assert resolution.fields["orm_type"].value == "проверочная закупка"
    assert resolution.fields["orm_type"].confidence == HIGH
    assert resolution.suggested_answers["criterion_13"] == {
        "orm_type": "проверочная закупка"
    }

    protocol = documents[1]
    assert protocol.fields["disinterested_persons"].value is True
    assert protocol.suggested_answers["criterion_13"] == {"orm_type": "досмотр"}


def test_segmenter_recognizes_known_type_without_fields() -> None:
    extracted = ExtractedText(text="ЗАЯВЛЕНИЕ\nЯ, Иванов Иван Иванович", pages=["x"])

    documents = DocumentSegmenter().segment(extracted)

    assert len(documents) == 1
    assert documents[0].kind.value == "consent_statement"
    assert documents[0].fields == {}


def test_field_extractor_marks_low_confidence_when_anchor_missing() -> None:
    extracted = ExtractedText(
        text=(
            "ПОСТАНОВЛЕНИЕ\n"
            "о проведении оперативно-розыскного мероприятия\n"
            "Я, Иванов Иван Иванович\n"
        ),
        pages=["x"],
    )

    documents = DocumentSegmenter().segment(extracted)

    assert documents[0].fields["orm_type"].value is None
    assert documents[0].fields["orm_type"].confidence == LOW


def test_inspection_order_extracts_premises_and_acquainted() -> None:
    extracted = ExtractedText(
        text=(
            "РАСПОРЯЖЕНИЕ № 1\n"
            "о проведении гласного оперативно-розыскного мероприятия\n"
            "обследование помещений\n"
            "Я, Иванов Иван Иванович\n"
            "рассмотрев сведения о нарушении законодательства\n"
            "Руководствуясь ст. 6 Федерального закона\n"
            "обследование жилого помещения\n"
            "С распоряжением ознакомлен Сидоров Сидор Сидорович\n"
        ),
        pages=["x"],
    )

    documents = DocumentSegmenter().segment(extracted)

    assert documents[0].kind.value == "inspection_order"
    assert documents[0].fields["premises_type"].value == "жилое"
    assert documents[0].fields["premises_type"].confidence == HIGH
    assert documents[0].fields["acquainted"].value is True
    assert documents[0].suggested_answers["criterion_6"] == {
        "premises_type": "жилое",
        "residents_consent": True,
    }
