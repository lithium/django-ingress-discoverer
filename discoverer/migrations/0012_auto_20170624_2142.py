# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-25 04:42
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('discoverer', '0011_auto_20170624_2037'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='portalindex',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='portalindex',
            name='updated_by',
        ),
        migrations.AlterUniqueTogether(
            name='portalinfo',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='portalinfo',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='portalinfo',
            name='updated_by',
        ),
        migrations.DeleteModel(
            name='PortalIndex',
        ),
        migrations.DeleteModel(
            name='PortalInfo',
        ),
    ]