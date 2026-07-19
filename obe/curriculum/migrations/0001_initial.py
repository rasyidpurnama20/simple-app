import django.db.models.deletion
import uuid
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CurriculumVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('program_code', models.CharField(max_length=32)),
                ('name', models.CharField(max_length=160)),
                ('cohort_from', models.PositiveSmallIntegerField()),
                ('cohort_to', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('review', 'Review'), ('active', 'Active'), ('archived', 'Archived')], default='draft', max_length=16)),
                ('checksum', models.CharField(blank=True, max_length=64)),
                ('approval_snapshot', models.JSONField(blank=True, default=dict)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('program_code', 'version'), name='curriculum_program_version_unique')],
            },
        ),
        migrations.CreateModel(
            name='CurriculumEdge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('source_type', models.CharField(max_length=20)),
                ('source_id', models.CharField(max_length=80)),
                ('target_type', models.CharField(max_length=20)),
                ('target_id', models.CharField(max_length=80)),
                ('allocation_weight', models.DecimalField(decimal_places=4, max_digits=7)),
                ('status', models.CharField(default='active', max_length=20)),
                ('curriculum', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='edges', to='curriculum.curriculumversion')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('curriculum', 'source_type', 'source_id', 'target_type', 'target_id', 'version'), name='curriculum_edge_unique')],
            },
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('code', models.CharField(max_length=20)),
                ('name', models.CharField(max_length=200)),
                ('credits', models.PositiveSmallIntegerField()),
                ('required', models.BooleanField(default=True)),
                ('recommended_semester', models.PositiveSmallIntegerField()),
                ('term', models.CharField(choices=[('odd', 'Ganjil'), ('even', 'Genap'), ('both', 'Keduanya')], max_length=10)),
                ('prerequisites', models.JSONField(blank=True, default=list)),
                ('capacity', models.PositiveIntegerField(default=40)),
                ('status', models.CharField(default='active', max_length=20)),
                ('curriculum', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='courses', to='curriculum.curriculumversion')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('curriculum', 'code', 'version'), name='course_code_version_unique')],
            },
        ),
        migrations.CreateModel(
            name='Outcome',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('version', models.PositiveIntegerField(default=1)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('lock_version', models.PositiveIntegerField(default=0)),
                ('kind', models.CharField(choices=[('PL', 'Profil Lulusan'), ('CPL', 'CPL'), ('BK', 'Bahan Kajian'), ('CPMK', 'CPMK Program')], max_length=8)),
                ('code', models.CharField(max_length=20)),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('category', models.CharField(blank=True, max_length=80)),
                ('depth', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('weight', models.DecimalField(decimal_places=4, default=0, max_digits=7)),
                ('target', models.DecimalField(decimal_places=2, default=Decimal('75'), max_digits=5)),
                ('status', models.CharField(default='active', max_length=20)),
                ('curriculum', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='outcomes', to='curriculum.curriculumversion')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('curriculum', 'kind', 'code', 'version'), name='outcome_code_version_unique'), models.CheckConstraint(condition=models.Q(('weight__gte', 0), ('weight__lte', 100)), name='outcome_weight_range')],
            },
        ),
    ]
