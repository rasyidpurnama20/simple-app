import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('role', models.CharField(choices=[('prodi', 'Program Studi'), ('gpm', 'GPM'), ('pengampu', 'Pengampu'), ('mahasiswa', 'Mahasiswa'), ('dpa', 'DPA'), ('koordinator', 'Koordinator'), ('pembimbing', 'Pembimbing'), ('penguji', 'Penguji'), ('mentor', 'Mentor'), ('tpmf', 'TPMF')], max_length=24)),
                ('scope_type', models.CharField(default='global', max_length=80)),
                ('scope_id', models.CharField(default='*', max_length=80)),
                ('actions', models.JSONField(default=list)),
                ('period', models.CharField(blank=True, max_length=40)),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('granted_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assignments_granted', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'constraints': [models.UniqueConstraint(condition=models.Q(('revoked_at__isnull', True)), fields=('user', 'role', 'scope_type', 'scope_id', 'period'), name='active_assignment_unique')],
            },
        ),
    ]
