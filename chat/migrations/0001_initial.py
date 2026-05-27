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
            name='Conversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('participants', models.ManyToManyField(related_name='conversations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[('sent', 'Sent'), ('delivered', 'Delivered'), ('read', 'Read')],
                    default='sent',
                    max_length=10,
                )),
                ('is_read', models.BooleanField(default=False)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('message_type', models.CharField(
                    choices=[('text', 'Text'), ('file', 'File'), ('image', 'Image')],
                    default='text',
                    max_length=10,
                )),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='chat.conversation')),
                ('receiver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_messages', to=settings.AUTH_USER_MODEL)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['timestamp'],
                'indexes': [
                    models.Index(fields=['conversation', 'timestamp'], name='chat_messag_convers_idx'),
                    models.Index(fields=['sender', 'receiver'], name='chat_messag_sender_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='FileAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='chat_files/%Y/%m/%d/')),
                ('original_name', models.CharField(max_length=255)),
                ('file_size', models.PositiveBigIntegerField()),
                ('mime_type', models.CharField(max_length=100)),
                ('thumbnail', models.ImageField(blank=True, null=True, upload_to='chat_thumbs/')),
                ('message', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='attachment', to='chat.message')),
            ],
        ),
    ]
