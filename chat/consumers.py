import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        is_participant = await self.check_participant()
        if not is_participant:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.set_user_online(True)
        await self.broadcast_presence(True)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.set_user_online(False)
            await self.broadcast_presence(False)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type')

        if msg_type == 'chat_message':
            await self.handle_message(data)
        elif msg_type == 'typing':
            await self.handle_typing(data)
        elif msg_type == 'read_receipt':
            await self.handle_read_receipt(data)

    async def handle_message(self, data):
        content = data.get('content', '').strip()
        reply_to_id = data.get('reply_to')
        
        if not content:
            return

        message = await self.save_message(content, reply_to_id)
        if not message:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': message['id'],
                'content': message['content'],
                'sender_id': message['sender_id'],
                'sender_username': message['sender_username'],
                'sender_avatar': message['sender_avatar'],
                'timestamp': message['timestamp'],
                'status': message['status'],
                'reply_to': message.get('reply_to'),
            }
        )

    async def handle_typing(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'is_typing': data.get('is_typing', False),
            }
        )

    async def handle_read_receipt(self, data):
        message_ids = data.get('message_ids', [])
        if message_ids:
            await self.mark_messages_read(message_ids)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'reader_id': self.user.id,
                    'message_ids': message_ids,
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'id': event['id'],
            'content': event['content'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'sender_avatar': event['sender_avatar'],
            'timestamp': event['timestamp'],
            'status': event['status'],
            'reply_to': event.get('reply_to'),
            'message_type': event.get('message_type', 'text'),
            'attachment': event.get('attachment')
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id']
        }))
        
    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'content': event['content'],
            'edited_at': event['edited_at']
        }))
        
    async def reaction_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction_update',
            'message_id': event['message_id'],
            'reactions': event['reactions']
        }))

    async def typing_indicator(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'sender_id': event['sender_id'],
                'sender_username': event['sender_username'],
                'is_typing': event['is_typing'],
            }))

    async def read_receipt(self, event):
        if event['reader_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'read_receipt',
                'reader_id': event['reader_id'],
                'message_ids': event['message_ids'],
            }))

    async def presence_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'presence',
            'user_id': event['user_id'],
            'is_online': event['is_online'],
            'last_seen': event['last_seen'],
        }))

    @database_sync_to_async
    def check_participant(self):
        from .models import Conversation
        try:
            conv = Conversation.objects.get(id=self.conversation_id)
            return conv.participants.filter(id=self.user.id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, reply_to_id=None):
        from .models import Conversation, Message
        try:
            conv = Conversation.objects.get(id=self.conversation_id)
            receiver = None if conv.is_group else conv.participants.exclude(id=self.user.id).first()
            
            reply_to_msg = None
            if reply_to_id:
                reply_to_msg = Message.objects.filter(id=reply_to_id, conversation=conv).first()

            msg = Message.objects.create(
                conversation=conv,
                sender=self.user,
                receiver=receiver,
                content=content,
                status=Message.STATUS_DELIVERED if (receiver and receiver.is_online) else Message.STATUS_SENT,
                reply_to=reply_to_msg
            )
            conv.save()

            avatar_url = self.user.get_avatar_url()
            result = {
                'id': msg.id,
                'content': msg.content,
                'sender_id': self.user.id,
                'sender_username': self.user.username,
                'sender_avatar': avatar_url,
                'timestamp': msg.timestamp.isoformat(),
                'status': msg.status,
            }
            if reply_to_msg:
                result['reply_to'] = {
                    'id': reply_to_msg.id,
                    'sender_username': reply_to_msg.sender.username,
                    'content': reply_to_msg.content[:50] if not reply_to_msg.is_deleted else "This message was deleted"
                }
            return result
        except Exception:
            return None

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        from .models import Message
        Message.objects.filter(
            id__in=message_ids,
            receiver=self.user,
            is_read=False
        ).update(is_read=True, status=Message.STATUS_READ)

    @database_sync_to_async
    def set_user_online(self, status):
        self.user.set_online(status)

    async def broadcast_presence(self, is_online):
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        last_seen = timezone.now().isoformat()

        await channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'presence_update',
                'user_id': self.user.id,
                'is_online': is_online,
                'last_seen': last_seen,
            }
        )

class PresenceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        self.user_group = f'presence_{self.user.id}'
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        await self.set_online(True)

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.set_online(False)
        if hasattr(self, 'user_group'):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    @database_sync_to_async
    def set_online(self, status):
        self.user.set_online(status)

    async def receive(self, text_data):
        pass
