# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-15 00:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('discoverer', '0006_portalinfo_stored_county'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kmloutput',
            options={'ordering': ('-created_at',), 'permissions': (('read_kmloutput', 'Allowed to download the kml'),)},
        ),
        migrations.RemoveField(
            model_name='kmloutput',
            name='portal_count',
        ),
        migrations.AddField(
            model_name='discovereruser',
            name='discovered_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='discovereruser',
            name='updated_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='kmloutput',
            name='portal_index_etag',
            field=models.CharField(default=b'_missing_etag_', max_length=254),
        ),
    ]
