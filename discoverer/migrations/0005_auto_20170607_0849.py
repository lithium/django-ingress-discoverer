# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-07 15:49
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('discoverer', '0004_kmloutput'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='portalindex',
            options={'ordering': ('name',), 'permissions': (('read_portalindex', 'Allowed to fetch the portal index'), ('read_iitcplugin', 'Allowed download IITC plugin'))},
        ),
    ]