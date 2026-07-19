from itertools import cycle

from django.core.management.base import BaseCommand
from django.db import transaction

from obe.curriculum.models import Course, CurriculumVersion, Outcome
from obe.identity.services import ensure_demo_assignments

PL = [
    "Solution Analyst",
    "Artificial Intelligence Engineer and Data Analyst",
    "Software Developer",
    "Professional Entrepreneur",
    "Academician and Researcher Assistant",
]

CPL = [
    "Analisis masalah komputasi kompleks berbasis data",
    "Prinsip informatika lintas disiplin",
    "Siklus solusi teknologi informasi",
    "Algoritma, kecerdasan buatan, dan analitika data",
    "Algoritma dan kompleksitas",
    "Sistem, perangkat lunak, dan keamanan",
    "Teknik dan kakas modern",
    "Tanggung jawab profesional, etika, dan hukum",
    "Keseimbangan teknologi, sosial, dan alam",
    "Kemandirian dan kewirausahaan",
    "Riset dan belajar sepanjang hayat",
    "Komunikasi dan kerja tim",
]

BK = [
    "Dasar Algoritma",
    "Dasar Bahasa Pemrograman",
    "Dasar Pengembangan Perangkat Lunak",
    "Rekayasa Perangkat Lunak",
    "Dasar Sistem",
    "Arsitektur dan Organisasi Komputer",
    "Sistem Operasi",
    "Jaringan dan Komunikasi",
    "Komputasi Paralel dan Terdistribusi",
    "Keamanan",
    "Grafik dan Teknik Interaktif",
    "Kecerdasan Buatan",
    "Pengembangan Platform Khusus",
    "Interaksi Manusia Komputer",
    "Manajemen Data",
    "Masyarakat, Etika, dan Profesionalisme",
    "Dasar Matematika dan Statistika",
    "Literasi Data, Teknologi, dan Manusia",
]

CPMK = [
    "Analitis berbasis data",
    "Formulasi masalah kompleks",
    "Konsep teoretis ilmu komputer",
    "Penerapan konsep komputasional",
    "Implementasi perangkat lunak",
    "Evaluasi perangkat lunak",
    "Searching dan reasoning",
    "Learning dan pemodelan",
    "Rancangan manajemen informasi",
    "Implementasi data analytics",
    "Algoritma sederhana",
    "Algoritma kompleks",
    "Evaluasi kompleksitas",
    "Konsep sistem sederhana",
    "Konsep sistem kompleks dan keamanan",
    "Rancangan perangkat lunak aman",
    "Sistem kompleks",
    "Ketakwaan",
    "Tanggung jawab kemanusiaan",
    "Nasionalisme dan kewarganegaraan",
    "Disiplin dan Pancasila",
    "Taat hukum",
    "Etika akademik",
    "Keberagaman dan kepedulian sosial",
    "Kemandirian proyek",
    "Kewirausahaan",
    "Evaluasi bermutu",
    "Berpikir logis, kritis, dan inovatif",
    "Dokumentasi sistematis",
    "Komunikasi dan kolaborasi",
    "Kepemimpinan",
]

CORE_COURSES = [
    "Dasar Sistem",
    "Dasar Pemrograman",
    "Struktur Diskret",
    "Matematika I",
    "Aljabar Linier",
    "Pancasila",
    "Kewarganegaraan",
    "Bahasa Inggris I",
    "Bahasa Inggris II",
    "Bahasa Inggris III",
    "Bahasa Indonesia",
    "Pendidikan Agama",
    "Olah Raga",
    "Organisasi dan Arsitektur Komputer",
    "Algoritma dan Pemrograman",
    "Basis Data",
    "Matematika II",
    "Internet of Things",
    "Sistem Operasi",
    "Struktur Data",
    "Manajemen Basis Data",
    "Rekayasa Perangkat Lunak",
    "Statistika",
    "Metode Numerik",
    "Jaringan Komputer",
    "Pemrograman Berorientasi Objek",
    "Sistem Informasi",
    "Analisis dan Strategi Algoritma",
    "Kecerdasan Buatan",
    "Grafik dan Teknik Interaktif",
    "Komputasi Tersebar dan Paralel",
    "Pengembangan Platform Khusus",
    "Keamanan dan Jaminan Informasi",
    "Proyek Perangkat Lunak",
    "Pembelajaran Mesin",
    "Probabilitas Diskret",
    "Analitika Data",
    "Uji Perangkat Lunak",
    "Masyarakat dan Etika Profesi",
    "Manajemen Proyek",
    "Interaksi Manusia Komputer",
    "Teori Bahasa dan Automata",
    "Metodologi dan Penulisan Ilmiah",
    "PKL",
    "Kewirausahaan",
    "KKN",
    "Tugas Akhir",
]

ELECTIVE_COURSES = [
    "Topik Khusus I",
    "Topik Khusus II",
    "Metode Perangkat Lunak",
    "Kualitas Perangkat Lunak",
    "Pemodelan dan Simulasi",
    "Visi Komputer",
    "Visualisasi Data",
    "Penambangan Data",
    "Sistem Tertanam",
    "Algoritma Evolusioner",
    "Komputasi Lunak",
    "Temu Balik Informasi",
    "Evolusi Perangkat Lunak",
    "Rekayasa Sistem",
    "Komputasi Awan",
    "Arsitektur Perangkat Lunak",
    "Pemrograman Lanjut",
    "Pengenalan Pola",
    "Kriptografi",
    "Bioinformatika",
    "Keamanan Siber",
    "Forensik Digital",
    "Data Besar",
    "Intelijen Bisnis",
    "Rekayasa Data",
    "Sistem Enterprise",
    "Robotika",
    "Pengolahan Bahasa Alami",
    "Analisis Jaringan Sosial",
    "Sains Data",
]


class Command(BaseCommand):
    help = "Seed katalog OBE dan empat akun demo secara idempotent"

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_demo_assignments()

        curriculum, _ = CurriculumVersion.objects.get_or_create(
            program_code="IF",
            version=1,
            defaults={"name": "Kurikulum Informatika OBE", "cohort_from": 2024},
        )
        for kind, prefix, names in (
            ("PL", "PL", PL),
            ("CPL", "CPL", CPL),
            ("BK", "BK", BK),
            ("CPMK", "CPMK", CPMK),
        ):
            width = 2
            for index, name in enumerate(names, 1):
                code = f"{prefix}{index:0{width}d}"
                Outcome.objects.get_or_create(
                    curriculum=curriculum,
                    kind=kind,
                    code=code,
                    version=1,
                    defaults={"name": name, "description": name, "weight": 0, "target": 75},
                )

        core_credits = [3] * 26 + [2] * 18 + [3, 3, 6]
        semesters = cycle(range(1, 9))
        for index, (name, credits) in enumerate(zip(CORE_COURSES, core_credits, strict=True), 1):
            semester = next(semesters)
            Course.objects.get_or_create(
                curriculum=curriculum,
                code=f"IF{index:03}",
                version=1,
                defaults={
                    "name": name,
                    "credits": credits,
                    "required": True,
                    "recommended_semester": semester,
                    "term": "odd" if semester % 2 else "even",
                },
            )
        for index, name in enumerate(ELECTIVE_COURSES, 1):
            Course.objects.get_or_create(
                curriculum=curriculum,
                code=f"PIL{index:02}",
                version=1,
                defaults={
                    "name": name,
                    "credits": 3,
                    "required": False,
                    "recommended_semester": 7 if index % 2 else 8,
                    "term": "odd" if index % 2 else "even",
                },
            )
        self.stdout.write(
            self.style.SUCCESS("Seed selesai: 5 PL, 12 CPL, 18 BK, 31 CPMK, 77 mata kuliah")
        )
