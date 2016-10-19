# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-10-19 19:09
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('siteapp', '0002_auto_20161019_1859'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='receipt_sender',
            field=models.CharField(default='if.then.fund', help_text='The receipt email From: display name (not email).', max_length=128),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='campaign',
            name='receipt_subject',
            field=models.CharField(default='Your Contribution', help_text='The receipt email Subject: header.', max_length=128),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='campaign',
            name='receipt_template',
            field=models.TextField(default='Thank you!', help_text='Receipt email body text (plain text), as a Django template.'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='contribution',
            name='receipt_sent_at',
            field=models.DateTimeField(blank=True, help_text='If set, the datetime when a receipt email was sent to the contributor. If empty, the email has not yet been sent.', null=True),
        ),
    ]
