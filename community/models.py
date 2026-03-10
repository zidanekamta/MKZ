from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify


class Room(models.Model):
    VISIBILITY = [
        ("ALL", "Tous (connectés)"),
        ("BREEDERS", "Éleveurs uniquement"),
        ("BUYERS", "Acheteurs uniquement"),
        ("ADMINS", "Admins uniquement"),
        ("CUSTOM", "Custom (membres)"),
    ]
    POST_PERMISSION = [
        ("ALL", "Tout le monde peut écrire"),
        ("ADMINS_ONLY", "Admins uniquement"),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)

    visibility = models.CharField(max_length=12, choices=VISIBILITY, default="ALL")
    post_permission = models.CharField(max_length=12, choices=POST_PERMISSION, default="ALL")

    members = models.ManyToManyField(User, blank=True, related_name="community_rooms")  # CUSTOM

    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="rooms_created")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "room"
            slug = base
            i = 2
            while Room.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="community_messages")
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="deleted_room_messages")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.room.name} - {self.sender.username}"


class MessageImage(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="community/room_images/")
    created_at = models.DateTimeField(auto_now_add=True)


class MessageReport(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="room_reports")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "reporter")


# --------- DM (1–1) ----------

class Conversation(models.Model):
    # stocke toujours user1_id < user2_id (on impose dans code)
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conv_user1")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="conv_user2")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user1", "user2")

    def __str__(self):
        return f"DM({self.user1.username}, {self.user2.username})"

    def other(self, user):
        return self.user2 if user.id == self.user1_id else self.user1


class DirectMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dm_messages")
    content = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="deleted_dm_messages")
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"DM {self.sender.username} -> conv {self.conversation_id}"


class DirectMessageImage(models.Model):
    message = models.ForeignKey(DirectMessage, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="community/dm_images/")
    created_at = models.DateTimeField(auto_now_add=True)


class DirectMessageReport(models.Model):
    message = models.ForeignKey(DirectMessage, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="dm_reports")
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "reporter")


# --------- Mentions / Notifications ----------

class Notification(models.Model):
    KIND = [
        ("MENTION_ROOM", "Mention (Room)"),
        ("MENTION_DM", "Mention (DM)"),
        ("REPORT_UPDATE", "Signalement"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")       # destinataire
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications_sent")
    kind = models.CharField(max_length=20, choices=KIND)
    text = models.CharField(max_length=255, blank=True)

    room = models.ForeignKey(Room, null=True, blank=True, on_delete=models.CASCADE)
    room_message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE)

    conversation = models.ForeignKey(Conversation, null=True, blank=True, on_delete=models.CASCADE)
    dm_message = models.ForeignKey(DirectMessage, null=True, blank=True, on_delete=models.CASCADE)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]