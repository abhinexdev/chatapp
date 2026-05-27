from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('conversation/<int:conversation_id>/', views.conversation_view, name='conversation'),
    path('start/<int:user_id>/', views.start_conversation, name='start_conversation'),
    path('api/conversation/<int:conversation_id>/upload/', views.upload_file, name='upload_file'),
    path('api/conversation/<int:conversation_id>/messages/', views.get_messages, name='get_messages'),
    
    # Edit/Delete
    path('api/message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('api/message/<int:message_id>/edit/', views.edit_message, name='edit_message'),
    
    # React
    path('api/message/<int:message_id>/react/', views.react_message, name='react_message'),
    
    # Groups
    path('group/create/', views.create_group, name='create_group'),
    path('group/<int:group_id>/add-member/', views.add_group_member, name='add_group_member'),
    path('group/<int:group_id>/remove-member/', views.remove_group_member, name='remove_group_member'),
    path('group/<int:group_id>/leave/', views.leave_group, name='leave_group'),
    path('group/<int:group_id>/members/', views.group_members, name='group_members'),
]
