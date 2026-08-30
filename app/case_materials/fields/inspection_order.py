"""Извлечение полей из распоряжения о гласном ОРМ «обследование помещений»."""

from app.case_materials.fields.base import (
    ExtractedField,
    FieldExtractionResult,
    FieldExtractor,
    capture_anchor,
    confident,
    low,
    normalize,
)


class InspectionOrderFieldExtractor(FieldExtractor):
    """Поля: издавший, правовое основание, тип помещения, отметка об ознакомлении."""

    def extract(self, text: str) -> FieldExtractionResult:
        normalized = normalize(text)
        result = FieldExtractionResult()

        issued_by = capture_anchor(normalized, r"Я,\s*(.+?)\s*рассмотрев")
        result.fields["issued_by"] = confident(issued_by) if issued_by else low(None)

        legal_basis = capture_anchor(
            normalized, r"Руководствуясь\s+(.+?)\s+Федерального\s+закона"
        )
        result.fields["legal_basis"] = (
            confident(legal_basis) if legal_basis else low(None)
        )

        if "жил" in normalized.lower():
            premises_type, confidence = "жилое", "high"
        else:
            premises_type, confidence = "нежилое", "low"
        result.fields["premises_type"] = ExtractedField(premises_type, confidence)

        acquainted = "ознакомлен" in normalized.lower()
        result.fields["acquainted"] = confident(acquainted)

        result.suggested_answers["criterion_6"] = {
            "premises_type": premises_type,
            "residents_consent": acquainted,
        }

        return result


__all__ = ["InspectionOrderFieldExtractor"]
