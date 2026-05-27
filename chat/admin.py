from django.contrib import admin
from .models import Conversation, Message, FileAttachment

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('participants',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'status', 'timestamp', 'is_read')
    list_filter = ('status', 'is_read', 'message_type')
    search_fields = ('sender__username', 'receiver__username', 'content')

@admin.register(FileAttachment)
class FileAttachmentAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'mime_type', 'file_size')
