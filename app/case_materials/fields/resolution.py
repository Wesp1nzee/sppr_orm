"""Извлечение полей из постановления о проведении ОРМ."""

from app.case_materials.fields.base import (
    FieldExtractionResult,
    FieldExtractor,
    capture_anchor,
    confident,
    low,
    normalize,
)


class ResolutionFieldExtractor(FieldExtractor):
    """Поля: утвердивший, составитель, основание, вид ОРМ, правовое основание."""

    def extract(self, text: str) -> FieldExtractionResult:
        normalized = normalize(text)
        result = FieldExtractionResult()

        approved_by = capture_anchor(
            normalized,
            r"УТВЕРЖДАЮ\s*Начальник\s+([А-ЯЁа-яё\s.,«»\-]+?)\s+ПОСТАНОВЛЕНИЕ",
        )
        result.fields["approved_by"] = (
            confident(approved_by) if approved_by else low(None)
        )

        compiled_by = capture_anchor(normalized, r"Я,\s*(.+?)\s*рассмотрев")
        result.fields["compiled_by"] = (
            confident(compiled_by) if compiled_by else low(None)
        )

        basis = capture_anchor(
            normalized, r"рассмотрев\s+материалы\s+(.+?)\s+руководствуясь"
        )
        result.fields["basis"] = confident(basis) if basis else low(None)

        orm_type = capture_anchor(
            normalized,
            r"провести\s+оперативно-розыскное\s+мероприятие\s+[«\"]([^»\"]+)[»\"]",
        )
        result.fields["orm_type"] = confident(orm_type) if orm_type else low(None)

        legal_basis = capture_anchor(
            normalized, r"руководствуясь\s+(.+?)\s+Федерального\s+закона"
        )
        result.fields["legal_basis"] = (
            confident(legal_basis) if legal_basis else low(None)
        )

        if approved_by:
            result.suggested_answers["criterion_1"] = {"has_instruction": True}
        if orm_type:
            result.suggested_answers["criterion_13"] = {"orm_type": orm_type}

        return result


__all__ = ["ResolutionFieldExtractor"]
