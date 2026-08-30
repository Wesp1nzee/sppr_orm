"""Константы домена «Импорт материалов дела».

Содержит статусы загрузки, справочник типовых документов ОРД и ограничения
на загружаемые файлы. Имена/заголовки документов взяты из референсного PDF
пустых бланков (``docs/samples/case_materials_blank_forms.pdf``) и подлежат
пересмотру при получении реального образца от заказчика.
"""

from enum import StrEnum

#: Максимальный размер загружаемого файла в байтах (25 МБ).
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

#: Допустимые MIME-типы загружаемых файлов.
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
)

#: Эвристика пустоты текста: если среднее число символов на страницу ниже
#: порога — считаем, что текст не извлёкся (скан/нечитаемый PDF).
MIN_TEXT_CHARS_PER_PAGE = 40

#: Сообщение, сохраняемое в ``error_message`` при нечитаемом файле.
TEXT_EXTRACTION_FAILED_MESSAGE = (
    "Не удалось извлечь текст автоматически. "
    "Введите данные вручную через мастер проверки."
)


class CaseMaterialStatus(StrEnum):
    """Жизненный цикл загруженного материала дела."""

    uploaded = "uploaded"
    processing = "processing"
    extracted = "extracted"
    text_extraction_failed = "text_extraction_failed"
    failed = "failed"


class CaseDocumentKind(StrEnum):
    """Типовые оперативно-служебные документы ОРД из референсного PDF."""

    raport = "raport"
    resolution_to_conduct_orm = "resolution_to_conduct_orm"
    inspection_order = "inspection_order"
    consent_statement = "consent_statement"
    search_protocol_before = "search_protocol_before"
    search_protocol_after = "search_protocol_after"
    money_inspection_protocol = "money_inspection_protocol"
    sts_delivery_protocol = "sts_delivery_protocol"
    sts_withdrawal_protocol = "sts_withdrawal_protocol"
    vehicle_inspection_protocol_before = "vehicle_inspection_protocol_before"
    vehicle_inspection_protocol_after = "vehicle_inspection_protocol_after"
    declassification_resolution = "declassification_resolution"
    representation_resolution = "representation_resolution"


#: Заголовки документов для интерфейса (по референсному PDF).
DOCUMENT_KIND_TITLES: dict[CaseDocumentKind, str] = {
    CaseDocumentKind.raport: "Рапорт о проведении ОРМ",
    CaseDocumentKind.resolution_to_conduct_orm: (
        "Постановление о проведении оперативно-розыскного мероприятия"
    ),
    CaseDocumentKind.inspection_order: (
        "Распоряжение о проведении гласного ОРМ «обследование помещений»"
    ),
    CaseDocumentKind.consent_statement: "Заявление о добровольном участии в ОРМ",
    CaseDocumentKind.search_protocol_before: (
        "Протокол досмотра лица до проведения ОРМ"
    ),
    CaseDocumentKind.search_protocol_after: (
        "Протокол досмотра лица после проведения ОРМ"
    ),
    CaseDocumentKind.money_inspection_protocol: (
        "Протокол осмотра, пометки и вручения денежных средств"
    ),
    CaseDocumentKind.sts_delivery_protocol: (
        "Протокол вручения специального технического средства"
    ),
    CaseDocumentKind.sts_withdrawal_protocol: (
        "Протокол изъятия специального технического средства"
    ),
    CaseDocumentKind.vehicle_inspection_protocol_before: (
        "Протокол обследования ТС до проведения ОРМ"
    ),
    CaseDocumentKind.vehicle_inspection_protocol_after: (
        "Протокол обследования ТС после проведения ОРМ"
    ),
    CaseDocumentKind.declassification_resolution: (
        "Постановление о рассекречивании сведений"
    ),
    CaseDocumentKind.representation_resolution: (
        "Постановление о представлении результатов ОРД"
    ),
}


__all__ = [
    "ALLOWED_MIME_TYPES",
    "DOCUMENT_KIND_TITLES",
    "MAX_UPLOAD_BYTES",
    "MIN_TEXT_CHARS_PER_PAGE",
    "TEXT_EXTRACTION_FAILED_MESSAGE",
    "CaseDocumentKind",
    "CaseMaterialStatus",
]
