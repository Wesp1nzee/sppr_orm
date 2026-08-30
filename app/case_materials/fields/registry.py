"""Реестр экстракторов полей по типу документа."""

from app.case_materials.constants import CaseDocumentKind
from app.case_materials.fields.base import FieldExtractor
from app.case_materials.fields.inspection_order import InspectionOrderFieldExtractor
from app.case_materials.fields.resolution import ResolutionFieldExtractor
from app.case_materials.fields.search_protocol import SearchProtocolFieldExtractor

FIELD_EXTRACTORS: dict[CaseDocumentKind, FieldExtractor] = {
    CaseDocumentKind.resolution_to_conduct_orm: ResolutionFieldExtractor(),
    CaseDocumentKind.inspection_order: InspectionOrderFieldExtractor(),
    CaseDocumentKind.search_protocol_before: SearchProtocolFieldExtractor(),
    CaseDocumentKind.search_protocol_after: SearchProtocolFieldExtractor(),
}

__all__ = ["FIELD_EXTRACTORS"]
