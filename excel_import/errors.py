"""DomainError hierarchy and plain-language message catalog for excel_import.

All errors carry a problem + corrective_step and avoid database jargon
(Requirements 8.1, 8.2, 8.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ─── Forbidden jargon tokens ────────────────────────────────────────────────
JARGON_BLOCKLIST = frozenset([
    "null", "constraint", "traceback", "exception", "sql", "stack",
    "foreign key", "unique", "integrity", "column", "table", "index",
    "varchar", "decimal", "integer", "boolean", "migration",
])


@dataclass
class DomainError(Exception):
    """A business-rule violation expressed in plain language.

    Attributes:
        problem: What is wrong, in plain language.
        corrective_step: What the user should do.
        location: Optional sheet!cell for per-cell errors.
    """

    problem: str
    corrective_step: str
    location: str | None = None

    def to_message(self) -> dict:
        return {
            "problem": self.problem,
            "corrective_step": self.corrective_step,
            "location": self.location,
        }

    def __str__(self) -> str:
        return f"{self.problem} {self.corrective_step}"


@dataclass
class DeferredTemplateError(DomainError):
    """Raised when a deferred (not-yet-implemented) template type is requested."""

    available_types: list[str] = field(default_factory=list)


@dataclass
class SchemaVersionMismatchError(DomainError):
    """Raised when embedded schema version doesn't match any definition."""

    embedded_version: str = ""
    available_versions: list[str] = field(default_factory=list)


@dataclass
class CommitFailedError(DomainError):
    """Raised when commit fails and the batch is rolled back."""

    original_error: str = ""


@dataclass
class FileSafetyError(DomainError):
    """Raised by the file validator for unsafe uploads."""

    check_name: str = ""


# ─── Message catalog (plain-language, no jargon) ────────────────────────────
MESSAGE_CATALOG = {
    "deferred_type": {
        "problem": "Tipe template '{type}' belum tersedia saat ini.",
        "corrective_step": "Gunakan salah satu tipe yang tersedia: {available}.",
    },
    "schema_mismatch": {
        "problem": "Versi template pada file ({version}) tidak dikenali.",
        "corrective_step": "Unduh template terbaru dan gunakan file tersebut.",
    },
    "extension_invalid": {
        "problem": "File yang diunggah bukan file .xlsx yang valid.",
        "corrective_step": "Pastikan file berformat .xlsx dan coba unggah kembali.",
    },
    "mime_mismatch": {
        "problem": "Tipe MIME file tidak sesuai dengan format .xlsx.",
        "corrective_step": "Pastikan file adalah spreadsheet Excel (.xlsx) asli.",
    },
    "size_exceeded": {
        "problem": "Ukuran file melebihi batas maksimum yang diperbolehkan.",
        "corrective_step": "Kurangi jumlah data atau bagi menjadi beberapa file.",
    },
    "invalid_zip": {
        "problem": "File tidak dapat dibaca sebagai arsip spreadsheet yang valid.",
        "corrective_step": "Pastikan file adalah .xlsx asli yang tidak rusak.",
    },
    "zip_bomb": {
        "problem": "File terdeteksi memiliki rasio kompresi yang mencurigakan.",
        "corrective_step": "Gunakan file .xlsx standar tanpa kompresi berlebihan.",
    },
    "macro_detected": {
        "problem": "File mengandung makro yang tidak diperbolehkan.",
        "corrective_step": "Hapus semua makro dari file dan simpan sebagai .xlsx.",
    },
    "encrypted_file": {
        "problem": "File terenkripsi atau dilindungi kata sandi.",
        "corrective_step": "Hapus proteksi kata sandi dan simpan ulang sebagai .xlsx.",
    },
    "external_links": {
        "problem": "File mengandung tautan eksternal atau objek tertanam.",
        "corrective_step": "Hapus semua tautan eksternal dan objek tertanam.",
    },
    "formula_detected": {
        "problem": "File mengandung rumus (formula) pada sel {location}.",
        "corrective_step": "Ganti semua rumus dengan nilai tetap.",
    },
    "cell_empty": {
        "problem": "Sel '{field}' kosong padahal wajib diisi.",
        "corrective_step": "Isi sel '{field}' dengan nilai yang sesuai.",
    },
    "cell_invalid": {
        "problem": "Nilai pada sel '{field}' tidak valid: {reason}.",
        "corrective_step": "Perbaiki nilai pada sel '{field}' sesuai format yang diminta.",
    },
    "duplicate_key": {
        "problem": "Terdapat baris duplikat dengan kunci bisnis yang sama.",
        "corrective_step": "Hapus baris duplikat dan pastikan setiap baris memiliki kunci unik.",
    },
    "commit_failed": {
        "problem": "Proses penyimpanan data gagal.",
        "corrective_step": "Coba unggah ulang file. Jika masalah berlanjut, hubungi administrator.",
    },
}


def get_message(key: str, **kwargs) -> dict:
    """Get a message from the catalog with format parameters."""
    entry = MESSAGE_CATALOG.get(key, {
        "problem": "Terjadi kesalahan.",
        "corrective_step": "Coba lagi atau hubungi administrator.",
    })
    return {
        "problem": entry["problem"].format(**kwargs) if kwargs else entry["problem"],
        "corrective_step": entry["corrective_step"].format(**kwargs) if kwargs else entry["corrective_step"],
    }
