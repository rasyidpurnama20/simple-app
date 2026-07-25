"""Declarative template definition seeds for the 4 implemented types.

Each definition specifies fields, reference sources, validation rules, and
business key (Requirements 1.3, 1.4, 1.5, 1.6).
"""

DEFERRED_TYPES = ["Roster", "Grades", "Attainment_Measurement", "CQI"]

DEFINITIONS = {
    "Curriculum": {
        "schema_version": "1.0.0",
        "fields": [
            {"name": "code", "label": "Kode Kurikulum", "type": "text", "required": True},
            {"name": "name", "label": "Nama Kurikulum", "type": "text", "required": True},
            {"name": "year", "label": "Tahun", "type": "text", "required": True},
            {"name": "description", "label": "Deskripsi", "type": "text", "required": False},
        ],
        "reference_sources": [
            {"name": "programs", "service": "curriculum", "method": "get_programs", "columns": ["code", "name"]},
        ],
        "validation_rules": [
            {"field": "code", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "name", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "year", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
        ],
        "business_key": ["code"],
    },
    "CPL": {
        "schema_version": "1.0.0",
        "fields": [
            {"name": "curriculum_code", "label": "Kode Kurikulum", "type": "text", "required": True},
            {"name": "code", "label": "Kode CPL", "type": "text", "required": True},
            {"name": "description", "label": "Deskripsi", "type": "text", "required": True},
            {"name": "target_value", "label": "Nilai Target", "type": "number", "required": True},
        ],
        "reference_sources": [
            {"name": "curricula", "service": "curriculum", "method": "list_curricula", "columns": ["code", "name"]},
        ],
        "validation_rules": [
            {"field": "curriculum_code", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "code", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "description", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "target_value", "rule": "is_number", "params": {"min": 0, "max": 100}, "message_key": "cell_invalid"},
        ],
        "business_key": ["curriculum_code", "code"],
    },
    "RPS": {
        "schema_version": "1.0.0",
        "fields": [
            {"name": "course_code", "label": "Kode Mata Kuliah", "type": "text", "required": True},
            {"name": "class_name", "label": "Kelas", "type": "text", "required": True},
            {"name": "period", "label": "Periode", "type": "text", "required": True},
            {"name": "cpmk_code", "label": "Kode CPMK", "type": "text", "required": False},
            {"name": "cpmk_description", "label": "Deskripsi CPMK", "type": "text", "required": False},
        ],
        "reference_sources": [
            {"name": "courses", "service": "curriculum", "method": "get_courses", "columns": ["code", "name"]},
            {"name": "cpls", "service": "curriculum", "method": "get_cpls", "columns": ["code", "description"]},
        ],
        "validation_rules": [
            {"field": "course_code", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "class_name", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "period", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
        ],
        "business_key": ["course_code", "class_name", "period"],
    },
    "Rubric": {
        "schema_version": "1.0.0",
        "fields": [
            {"name": "instrument_name", "label": "Nama Instrumen", "type": "text", "required": True},
            {"name": "criterion_name", "label": "Nama Kriteria", "type": "text", "required": True},
            {"name": "weight", "label": "Bobot (%)", "type": "number", "required": True},
            {"name": "level_label", "label": "Label Level", "type": "text", "required": True},
            {"name": "level_score", "label": "Skor Level", "type": "number", "required": True},
        ],
        "reference_sources": [
            {"name": "instruments", "service": "rps", "method": "get_instruments", "columns": ["name"]},
        ],
        "validation_rules": [
            {"field": "instrument_name", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "criterion_name", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "weight", "rule": "is_number", "params": {"min": 0, "max": 100}, "message_key": "cell_invalid"},
            {"field": "level_label", "rule": "not_empty", "params": {}, "message_key": "cell_empty"},
            {"field": "level_score", "rule": "is_number", "params": {"min": 0, "max": 100}, "message_key": "cell_invalid"},
        ],
        "business_key": ["instrument_name", "criterion_name", "level_label"],
    },
}
