"""Suggest a mapping from a spreadsheet's actual column headers to a
canonical type's field names, per docs/PRD.md FR-04 "request confirmation
for ambiguous mappings" and docs/DATA_SPECIFICATION.md §5 step 8.
"""
from dataclasses import dataclass, field

from app.services.canonical_schema import CanonicalType, normalize


@dataclass
class MappingResult:
    canonical_type: str
    column_to_field: dict[str, str]  # uploaded column name -> canonical field
    unmapped_required_fields: list[str] = field(default_factory=list)

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.unmapped_required_fields)


def suggest_mapping(columns: list[str], canonical_type: CanonicalType) -> MappingResult:
    normalized_columns = {col: normalize(col) for col in columns}
    column_to_field: dict[str, str] = {}

    for field_name, spec in canonical_type.fields.items():
        candidates = {normalize(field_name), *[normalize(a) for a in spec.aliases]}
        match = next(
            (col for col, norm in normalized_columns.items() if norm in candidates),
            None,
        )
        if match:
            column_to_field[match] = field_name

    mapped_fields = set(column_to_field.values())
    unmapped_required = [f for f in canonical_type.required_fields if f not in mapped_fields]

    return MappingResult(
        canonical_type=canonical_type.name,
        column_to_field=column_to_field,
        unmapped_required_fields=unmapped_required,
    )


def apply_mapping(df, mapping: dict[str, str]):
    """Rename df columns per an (uploaded_column -> canonical_field) mapping
    and drop columns that weren't mapped to anything canonical."""
    renamed = df.rename(columns=mapping)
    return renamed[[c for c in mapping.values() if c in renamed.columns]]
