from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    code: str
    label: str
    purpose: str
    future_responsibilities: tuple[str, ...]


ROLES = (
    Role(
        code="prodi",
        label="Program Studi (Prodi)",
        purpose="Menentukan arah kurikulum dan memastikan proses akademik program studi tertata.",
        future_responsibilities=(
            "Menyusun dan mengajukan kurikulum serta CPL.",
            "Menetapkan mata kuliah dan memantau tindak lanjut mutu.",
        ),
    ),
    Role(
        code="gpm",
        label="Gugus Penjaminan Mutu (GPM)",
        purpose="Meninjau proses dan bukti mutu secara independen dari pelaksana pembelajaran.",
        future_responsibilities=(
            "Meninjau kesesuaian RPS, asesmen, dan capaian.",
            "Memberi catatan mutu tanpa mengambil alih pekerjaan Prodi atau Pengampu.",
        ),
    ),
    Role(
        code="pengampu",
        label="Pengampu",
        purpose="Merencanakan pembelajaran, melaksanakan asesmen, dan menjelaskan hasilnya.",
        future_responsibilities=(
            "Menyusun RPS dan instrumen asesmen untuk mata kuliah yang ditugaskan.",
            "Memasukkan nilai dan menindaklanjuti capaian mahasiswa.",
        ),
    ),
    Role(
        code="mahasiswa",
        label="Mahasiswa",
        purpose="Melihat proses dan hasil belajar miliknya secara jelas dan terlindungi.",
        future_responsibilities=(
            "Melihat rencana, asesmen, nilai, dan capaian milik sendiri.",
            "Mengirim pekerjaan atau umpan balik ketika fiturnya telah disetujui.",
        ),
    ),
)

ROLE_BY_CODE = {role.code: role for role in ROLES}


def role_for_user(user) -> Role | None:
    group_names = set(user.groups.values_list("name", flat=True))
    return next((role for role in ROLES if role.code in group_names), None)
