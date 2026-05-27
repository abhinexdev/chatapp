"""
chat/models.py — Message, Conversation, and FileAttachment models
"""
from django.db import models
from django.conf import settings
from django.db.models import Q


class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    is_group = models.BooleanField(default=False)
    name = models.CharField(max_length=255, blank=True)
    avatar = models.ImageField(upload_to='group_avatars/', blank=True, null=True)
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='administered_groups')

    class Meta:
        ordering = ['-updated_at']

    @classmethod
    def get_or_create_for_users(cls, user1, user2):
        """Get existing conversation between two users or create a new one."""
        convs = cls.objects.filter(participants=user1).filter(participants=user2)
        for conv in convs:
            if conv.participants.count() == 2:
                return conv, False
        conv = cls.objects.create()
        conv.participants.add(user1, user2)
        return conv, True

    def other_participant(self, user):
        return self.participants.exclude(id=user.id).first()

    def unread_count(self, user):
        return self.messages.filter(receiver=user, is_read=False).count()

    def last_message(self):
        return self.messages.order_by('-timestamp').first()

    def __str__(self):
        if self.is_group:
            return f"Group({self.name})"
        users = list(self.participants.values_list('username', flat=True))
        return f"Conversation({', '.join(users)})"


class GroupMembership(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='group_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)

    class Meta:
        unique_together = ('conversation', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.conversation.name}"


class Message(models.Model):
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'
    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_READ, 'Read'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)
    content = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_SENT)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(
        max_length=10,
        choices=[('text', 'Text'), ('file', 'File'), ('image', 'Image')],
        default='text'
    )
    is_deleted = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversation', 'timestamp']),
            models.Index(fields=['sender', 'receiver']),
        ]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.status = self.STATUS_READ
            self.save(update_fields=['is_read', 'status'])

    def __str__(self):
        return f'{self.sender} → {self.receiver}: {self.content[:40]}'


class FileAttachment(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name='attachment')
    file = models.FileField(upload_to='chat_files/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100)
    thumbnail = models.ImageField(upload_to='chat_thumbs/', blank=True, null=True)

    def is_image(self):
        return self.mime_type.startswith('image/')

    def size_display(self):
        size = self.file_size
        for unit in ['B', 'KB', 'MB']:
            if size < 1024:
                return f'{size:.1f} {unit}'
            size /= 1024
        return f'{size:.1f} GB'

    def __str__(self):
        return self.original_name


class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reactions')
    emoji = models.CharField(max_length=4)

    class Meta:
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} on {self.message_id}"
