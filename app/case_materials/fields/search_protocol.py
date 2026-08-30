"""Извлечение полей из протокола досмотра"""

from app.case_materials.fields.base import (
    FieldExtractionResult,
    FieldExtractor,
    capture_anchor,
    confident,
    low,
    normalize,
)


class SearchProtocolFieldExtractor(FieldExtractor):

    def extract(self, text: str) -> FieldExtractionResult:
        normalized = normalize(text)
        result = FieldExtractionResult()

        compiled_by = capture_anchor(normalized, r"Я,\s*(.+?)\s+в\s+помещении")
        result.fields["compiled_by"] = (
            confident(compiled_by) if compiled_by else low(None)
        )

        place = capture_anchor(normalized, r"в\s+помещении\s+(.+?)\s+в\s+присутствии")
        result.fields["place"] = confident(place) if place else low(None)

        has_disinterested = "незаинтересованных лиц" in normalized.lower()
        result.fields["disinterested_persons"] = confident(has_disinterested)

        legal_basis = capture_anchor(
            normalized, r"в\s+соответствии\s+со\s+(ст\.\s*\d+\s+Федерального\s+закона)"
        )
        result.fields["legal_basis"] = (
            confident(legal_basis) if legal_basis else low(None)
        )

        result.suggested_answers["criterion_13"] = {"orm_type": "досмотр"}

        return result


__all__ = ["SearchProtocolFieldExtractor"]
