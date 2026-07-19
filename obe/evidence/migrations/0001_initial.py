import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('shared', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EvidenceRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('object_type', models.CharField(max_length=80)),
                ('object_id', models.CharField(max_length=80)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('verified', 'Verified'), ('rejected', 'Rejected'), ('superseded', 'Superseded'), ('archived', 'Archived')], default='draft', max_length=20)),
                ('verified_by_id', models.CharField(blank=True, max_length=64)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('manifest', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='shared.filemanifest')),
                ('supersedes', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='evidence.evidencerecord')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
