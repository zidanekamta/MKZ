from django.contrib import admin
from .models import (
    Room, Message, MessageImage, MessageReport,
    Conversation, DirectMessage, DirectMessageImage, DirectMessageReport,
    Notification
)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "visibility", "post_permission", "is_archived", "created_at")
    list_filter = ("visibility", "post_permission", "is_archived")
    search_fields = ("name", "description")
    filter_horizontal = ("members",)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("room", "sender", "created_at", "is_deleted")
    list_filter = ("room", "is_deleted")
    search_fields = ("content", "sender__username", "room__name")

@admin.register(MessageImage)
class MessageImageAdmin(admin.ModelAdmin):
    list_display = ("message", "created_at")

@admin.register(MessageReport)
class MessageReportAdmin(admin.ModelAdmin):
    list_display = ("message", "reporter", "created_at")
    list_filter = ("created_at",)

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("user1", "user2", "updated_at")

@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "sender", "created_at", "is_deleted")
    list_filter = ("is_deleted",)

@admin.register(DirectMessageImage)
class DirectMessageImageAdmin(admin.ModelAdmin):
    list_display = ("message", "created_at")

@admin.register(DirectMessageReport)
class DirectMessageReportAdmin(admin.ModelAdmin):
    list_display = ("message", "reporter", "created_at")

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "actor", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    search_fields = ("user__username", "actor__username", "text")