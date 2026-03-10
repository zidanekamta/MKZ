from django.urls import path
from .views import (
    room_list, room_detail, room_messages_json,
    notifications, notification_mark_read,
    message_report, message_delete,
    dm_inbox, dm_start, dm_thread, dm_messages_json,
    dm_message_report, dm_message_delete,
)

urlpatterns = [
    # Rooms (groupe)
    path("", room_list, name="community_rooms"),
    path("room/<slug:slug>/", room_detail, name="community_room_detail"),
    path("room/<slug:slug>/messages.json", room_messages_json, name="community_room_messages_json"),
    path("room/message/<int:msg_id>/report/", message_report, name="community_message_report"),
    path("room/message/<int:msg_id>/delete/", message_delete, name="community_message_delete"),

    # Notifications (mentions)
    path("notifications/", notifications, name="community_notifications"),
    path("notifications/<int:notif_id>/read/", notification_mark_read, name="community_notification_read"),

    # DM (privé)
    path("dm/", dm_inbox, name="community_dm_inbox"),
    path("dm/start/<str:username>/", dm_start, name="community_dm_start"),
    path("dm/<int:conv_id>/", dm_thread, name="community_dm_thread"),
    path("dm/<int:conv_id>/messages.json", dm_messages_json, name="community_dm_messages_json"),
    path("dm/message/<int:msg_id>/report/", dm_message_report, name="community_dm_report"),
    path("dm/message/<int:msg_id>/delete/", dm_message_delete, name="community_dm_delete"),
]