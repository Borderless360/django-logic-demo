from django.db import migrations, models

from clickhouse.client import client as ch_client


def create_clickhouse_stats_table(apps, schema_editor):
    ch_client.command("""
    CREATE TABLE IF NOT EXISTS transition_stats (
        process_class  LowCardinality(String),
        action_name    LowCardinality(String),
        duration_seconds Float64,
        status         LowCardinality(String),
        instance_key   Nullable(String),
        root_id        Nullable(String),
        _timestamp     DateTime DEFAULT now()
    ) ENGINE = MergeTree()
    ORDER BY (_timestamp, process_class, action_name)
    PARTITION BY toYYYYMM(_timestamp)
    TTL _timestamp + INTERVAL 90 DAY
    SETTINGS index_granularity = 8192
    """)


def drop_clickhouse_stats_table(apps, schema_editor):
    ch_client.command("DROP TABLE IF EXISTS transition_stats")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('clickhouse', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AlertConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('alert_type', models.CharField(choices=[('email', 'Email'), ('webhook', 'Webhook')], max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('email_recipients', models.TextField(blank=True, help_text='Comma-separated email addresses')),
                ('email_from', models.EmailField(blank=True, max_length=254)),
                ('webhook_url', models.URLField(blank=True)),
                ('webhook_headers', models.JSONField(blank=True, default=dict)),
                ('std_dev_multiplier', models.FloatField(blank=True, help_text='Override: alert if duration > mean + multiplier * std_dev', null=True)),
                ('min_samples', models.PositiveIntegerField(blank=True, help_text='Override: minimum samples before detection activates', null=True)),
                ('process_class_filter', models.CharField(blank=True, help_text='Only alert for this process class (empty = all)', max_length=255)),
                ('action_name_filter', models.CharField(blank=True, help_text='Only alert for this action name (empty = all)', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Alert Configuration',
                'verbose_name_plural': 'Alert Configurations',
            },
        ),
        migrations.RunPython(create_clickhouse_stats_table, drop_clickhouse_stats_table),
    ]
