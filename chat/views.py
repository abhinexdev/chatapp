import json
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Count
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import User
from .models import Conversation, Message, FileAttachment, MessageReaction, GroupMembership


@login_required
def index(request):
    conversations = (
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related('participants', 'messages')
        .order_by('-updated_at')
    )
    conv_data = []
    for conv in conversations:
        if conv.is_group:
            other = None
        else:
            other = conv.other_participant(request.user)
            if not other:
                continue
        last_msg = conv.last_message()
        unread = conv.unread_count(request.user)
        conv_data.append({'conv': conv, 'other': other, 'last_msg': last_msg, 'unread': unread})
    return render(request, 'index.html', {'conversations': conv_data, 'user': request.user})


@login_required
def conversation_view(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    if not conv.participants.filter(id=request.user.id).exists():
        return redirect('chat:index')
    other = None if conv.is_group else conv.other_participant(request.user)
    messages_qs = (
        conv.messages
        .select_related('sender', 'receiver', 'attachment', 'reply_to__sender')
        .prefetch_related('reactions')
        .order_by('timestamp')
    )
    # Mark unread as read
    unread = messages_qs.filter(receiver=request.user, is_read=False)
    unread.update(is_read=True, status=Message.STATUS_READ)

    conversations = (
        Conversation.objects.filter(participants=request.user)
        .prefetch_related('participants', 'messages').order_by('-updated_at')
    )
    conv_data = []
    for c in conversations:
        o = None if c.is_group else c.other_participant(request.user)
        if not c.is_group and not o:
            continue
        conv_data.append({
            'conv': c,
            'other': o,
            'last_msg': c.last_message(),
            'unread': c.unread_count(request.user),
        })
    return render(request, 'index.html', {
        'conversations': conv_data,
        'active_conv': conv,
        'other_user': other,
        'messages': messages_qs,
        'user': request.user,
        'is_group': conv.is_group,
    })


@login_required
def start_conversation(request, user_id):
    other = get_object_or_404(User, id=user_id)
    if other == request.user:
        return redirect('chat:index')
    conv, _ = Conversation.get_or_create_for_users(request.user, other)
    return redirect('chat:conversation', conversation_id=conv.id)


@login_required
@require_POST
def upload_file(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    if not conv.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)
    uploaded = request.FILES.get('file')
    if not uploaded:
        return JsonResponse({'error': 'No file'}, status=400)
    if uploaded.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'File too large (max 10MB)'}, status=400)
    mime_type, _ = mimetypes.guess_type(uploaded.name)
    mime_type = mime_type or 'application/octet-stream'
    receiver = None if conv.is_group else conv.other_participant(request.user)
    msg_type = 'image' if mime_type.startswith('image/') else 'file'
    reply_to_id = request.POST.get('reply_to')
    reply_to_msg = Message.objects.filter(id=reply_to_id, conversation=conv).first() if reply_to_id else None
    status = Message.STATUS_SENT
    if not conv.is_group and receiver and receiver.is_online:
        status = Message.STATUS_DELIVERED
    msg = Message.objects.create(
        conversation=conv, sender=request.user, receiver=receiver,
        content='', message_type=msg_type, status=status, reply_to=reply_to_msg,
    )
    attachment = FileAttachment.objects.create(
        message=msg, file=uploaded, original_name=uploaded.name,
        file_size=uploaded.size, mime_type=mime_type,
    )
    conv.save()

    # Broadcast to websocket group
    channel_layer = get_channel_layer()
    reply_data = None
    if reply_to_msg:
        reply_data = {
            'id': reply_to_msg.id,
            'sender_username': reply_to_msg.sender.username,
            'content': reply_to_msg.content[:50] if not reply_to_msg.is_deleted else 'This message was deleted',
        }
    async_to_sync(channel_layer.group_send)(f'chat_{conv.id}', {
        'type': 'chat_message',
        'id': msg.id,
        'content': '',
        'sender_id': request.user.id,
        'sender_username': request.user.username,
        'sender_avatar': request.user.get_avatar_url(),
        'timestamp': msg.timestamp.isoformat(),
        'status': msg.status,
        'message_type': msg_type,
        'reply_to': reply_data,
        'attachment': {
            'file_url': attachment.file.url,
            'original_name': attachment.original_name,
            'file_size': attachment.size_display(),
            'mime_type': mime_type,
            'is_image': attachment.is_image(),
        },
    })

    return JsonResponse({
        'message_id': msg.id,
        'file_url': attachment.file.url,
        'original_name': attachment.original_name,
        'file_size': attachment.size_display(),
        'mime_type': mime_type,
        'is_image': attachment.is_image(),
        'timestamp': msg.timestamp.isoformat(),
        'sender_id': request.user.id,
        'reply_to': reply_data,
    })


@login_required
@require_GET
def get_messages(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    if not conv.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)
    before_id = request.GET.get('before')
    qs = (
        conv.messages
        .select_related('sender', 'attachment', 'reply_to__sender')
        .prefetch_related('reactions')
        .order_by('-timestamp')
    )
    if before_id:
        qs = qs.filter(id__lt=before_id)
    qs = qs[:30]
    messages_data = []
    for m in reversed(list(qs)):
        item = {
            'id': m.id,
            'content': m.content,
            'sender_id': m.sender_id,
            'sender_username': m.sender.username,
            'sender_avatar': m.sender.get_avatar_url(),
            'timestamp': m.timestamp.isoformat(),
            'status': m.status,
            'message_type': m.message_type,
            'is_read': m.is_read,
            'is_deleted': m.is_deleted,
            'edited_at': m.edited_at.isoformat() if m.edited_at else None,
        }
        if m.reply_to:
            item['reply_to'] = {
                'id': m.reply_to.id,
                'sender_username': m.reply_to.sender.username,
                'content': m.reply_to.content[:50] if not m.reply_to.is_deleted else 'This message was deleted',
            }
        item['reactions'] = list(m.reactions.values('emoji').annotate(count=Count('id')))
        try:
            att = m.attachment
            item['attachment'] = {
                'file_url': att.file.url,
                'original_name': att.original_name,
                'file_size': att.size_display(),
                'mime_type': att.mime_type,
                'is_image': att.is_image(),
            }
        except Exception:
            pass
        messages_data.append(item)
    return JsonResponse({'messages': messages_data})


@login_required
@require_POST
def delete_message(request, message_id):
    msg = get_object_or_404(Message, id=message_id, sender=request.user)
    msg.is_deleted = True
    msg.content = ''
    msg.save(update_fields=['is_deleted', 'content'])
    async_to_sync(get_channel_layer().group_send)(
        f'chat_{msg.conversation_id}',
        {'type': 'message_deleted', 'id': msg.id},
    )
    return JsonResponse({'status': 'deleted'})


@login_required
@require_POST
def edit_message(request, message_id):
    msg = get_object_or_404(Message, id=message_id, sender=request.user, is_deleted=False)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    if (timezone.now() - msg.timestamp).total_seconds() > 900:
        return JsonResponse({'error': 'Edit time limit exceeded (15 min)'}, status=403)
    new_content = data.get('content', '').strip()
    if not new_content:
        return JsonResponse({'error': 'Content cannot be empty'}, status=400)
    msg.content = new_content
    msg.edited_at = timezone.now()
    msg.save(update_fields=['content', 'edited_at'])
    async_to_sync(get_channel_layer().group_send)(
        f'chat_{msg.conversation_id}',
        {
            'type': 'message_edited',
            'id': msg.id,
            'content': msg.content,
            'edited_at': msg.edited_at.isoformat(),
        },
    )
    return JsonResponse({'status': 'edited', 'edited_at': msg.edited_at.isoformat()})


@login_required
def react_message(request, message_id):
    msg = get_object_or_404(Message, id=message_id)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        emoji = data.get('emoji')
        if emoji:
            MessageReaction.objects.update_or_create(
                message=msg, user=request.user,
                defaults={'emoji': emoji},
            )
    elif request.method == 'DELETE':
        MessageReaction.objects.filter(message=msg, user=request.user).delete()
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    reactions = list(msg.reactions.values('emoji').annotate(count=Count('id')))
    async_to_sync(get_channel_layer().group_send)(
        f'chat_{msg.conversation_id}',
        {'type': 'reaction_update', 'message_id': msg.id, 'reactions': reactions},
    )
    return JsonResponse({'status': 'ok', 'reactions': reactions})


@login_required
@require_POST
def create_group(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Group name is required'}, status=400)
    conv = Conversation.objects.create(is_group=True, name=name, admin=request.user)
    GroupMembership.objects.create(conversation=conv, user=request.user, is_admin=True)
    conv.participants.add(request.user)
    for uid in data.get('member_ids', []):
        try:
            u = User.objects.get(id=uid)
            GroupMembership.objects.create(conversation=conv, user=u)
            conv.participants.add(u)
        except User.DoesNotExist:
            pass
    return JsonResponse({'status': 'created', 'group_id': conv.id})


@login_required
@require_POST
def add_group_member(request, group_id):
    conv = get_object_or_404(Conversation, id=group_id, is_group=True, admin=request.user)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    user = get_object_or_404(User, id=data.get('user_id'))
    if not conv.participants.filter(id=user.id).exists():
        GroupMembership.objects.create(conversation=conv, user=user)
        conv.participants.add(user)
    return JsonResponse({'status': 'added'})


@login_required
@require_POST
def remove_group_member(request, group_id):
    conv = get_object_or_404(Conversation, id=group_id, is_group=True, admin=request.user)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    user_id = data.get('user_id')
    if str(user_id) == str(request.user.id):
        return JsonResponse({'error': 'Cannot remove yourself'}, status=400)
    user = get_object_or_404(User, id=user_id)
    GroupMembership.objects.filter(conversation=conv, user=user).delete()
    conv.participants.remove(user)
    return JsonResponse({'status': 'removed'})


@login_required
@require_POST
def leave_group(request, group_id):
    conv = get_object_or_404(Conversation, id=group_id, is_group=True)
    if request.user == conv.admin:
        return JsonResponse({'error': 'Admin cannot leave without reassigning admin first'}, status=400)
    GroupMembership.objects.filter(conversation=conv, user=request.user).delete()
    conv.participants.remove(request.user)
    return JsonResponse({'status': 'left'})


@login_required
@require_GET
def group_members(request, group_id):
    conv = get_object_or_404(Conversation, id=group_id, is_group=True)
    if not conv.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Forbidden'}, status=403)
    members = []
    for m in conv.participants.values('id', 'username', 'is_online', 'avatar'):
        members.append({
            'id': m['id'],
            'username': m['username'],
            'is_online': m['is_online'],
            'avatar': '/media/' + m['avatar'] if m['avatar'] else '/static/images/default_avatar.png',
            'is_admin': conv.admin_id == m['id'],
        })
    return JsonResponse({'members': members, 'is_admin': conv.admin == request.user})
