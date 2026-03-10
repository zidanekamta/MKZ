import re
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import localtime, now

from django.contrib.auth.models import User
from accounts.models import Profile
from django.db import models


from .models import (
    Room, Message, MessageImage, MessageReport,
    Conversation, DirectMessage, DirectMessageImage, DirectMessageReport,
    Notification
)

MENTION_RE = re.compile(r"@([A-Za-z0-9_\.]{3,30})")


def _role_of(user):
    prof = getattr(user, "profile", None)
    return getattr(prof, "role", "")


def user_can_access(room: Room, user) -> bool:
    if room.is_archived:
        return False
    if room.visibility == "ALL":
        return True
    if room.visibility == "ADMINS":
        return user.is_staff or user.is_superuser

    prof = getattr(user, "profile", None)
    role = getattr(prof, "role", None)

    if room.visibility == "BREEDERS":
        return role == "BREEDER"
    if room.visibility == "BUYERS":
        return role == "BUYER"
    if room.visibility == "CUSTOM":
        return room.members.filter(id=user.id).exists() or user.is_staff or user.is_superuser

    return False


def user_can_post(room: Room, user) -> bool:
    if room.post_permission == "ALL":
        return True
    return user.is_staff or user.is_superuser


def can_delete_message(user, sender):
    # auteur peut supprimer son message, admin peut supprimer tout
    return user.is_staff or user.is_superuser or user.id == sender.id


def _create_mentions_notifications(actor, text, *, room=None, room_message=None, conversation=None, dm_message=None):
    usernames = set(MENTION_RE.findall(text or ""))
    if not usernames:
        return
    users = User.objects.filter(username__in=list(usernames)).all()
    for u in users:
        if u.id == actor.id:
            continue
        if room and room_message:
            Notification.objects.create(
                user=u, actor=actor, kind="MENTION_ROOM",
                text=f"@{actor.username} t'a mentionné dans {room.name}",
                room=room, room_message=room_message,
            )
        elif conversation and dm_message:
            Notification.objects.create(
                user=u, actor=actor, kind="MENTION_DM",
                text=f"@{actor.username} t'a mentionné en message privé",
                conversation=conversation, dm_message=dm_message,
            )


# ----------------- ROOMS (groupe) -----------------

@login_required
def room_list(request):
    rooms = Room.objects.filter(is_archived=False).order_by("name")
    accessible = [r for r in rooms if user_can_access(r, request.user)]
    return render(request, "community/room_list.html", {"rooms": accessible})


@login_required
def room_detail(request, slug):
    room = get_object_or_404(Room, slug=slug)

    if not user_can_access(room, request.user):
        return HttpResponseForbidden("Accès refusé.")

    if request.method == "POST":
        if not user_can_post(room, request.user):
            return HttpResponseForbidden("Seuls les admins peuvent écrire ici.")

        content = (request.POST.get("content") or "").strip()
        images = request.FILES.getlist("images")

        if content or images:
            msg = Message.objects.create(room=room, sender=request.user, content=content or "")
            for f in images:
                MessageImage.objects.create(message=msg, image=f)

            _create_mentions_notifications(request.user, msg.content, room=room, room_message=msg)

        return redirect("community_room_detail", slug=room.slug)

    messages_qs = (
        room.messages
        .select_related("sender")
        .prefetch_related("images")
        .filter(is_deleted=False)
        .order_by("-id")[:200]
    )
    messages_list = list(reversed(messages_qs))

    can_post = user_can_post(room, request.user)

    return render(
        request,
        "community/room_detail.html",
        {"room": room, "messages": messages_list, "can_post": can_post},
    )


@login_required
def room_messages_json(request, slug):
    room = get_object_or_404(Room, slug=slug)
    if not user_can_access(room, request.user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    after = request.GET.get("after", "0")
    try:
        after_id = int(after)
    except Exception:
        after_id = 0

    qs = (
        room.messages
        .select_related("sender")
        .prefetch_related("images")
        .filter(is_deleted=False, id__gt=after_id)
        .order_by("id")[:100]
    )

    out = []
    for m in qs:
        out.append({
            "id": m.id,
            "sender": m.sender.username,
            "role": _role_of(m.sender),
            "is_admin": bool(m.sender.is_staff or m.sender.is_superuser),
            "content": m.content,
            "created_at": localtime(m.created_at).strftime("%d/%m/%Y %H:%M"),
            "images": [img.image.url for img in m.images.all()],
            "can_delete": can_delete_message(request.user, m.sender),
        })

    return JsonResponse({"ok": True, "messages": out})


@login_required
def message_report(request, msg_id: int):
    msg = get_object_or_404(Message, pk=msg_id)
    if not user_can_access(msg.room, request.user):
        return HttpResponseForbidden("Accès refusé.")
    if request.method != "POST":
        return redirect("community_room_detail", slug=msg.room.slug)

    reason = (request.POST.get("reason") or "").strip()[:255]
    MessageReport.objects.get_or_create(message=msg, reporter=request.user, defaults={"reason": reason})

    # Notif admin (optionnel)
    if msg.reports.count() >= 3:
        # envoie notif aux admins (simple)
        for admin_user in User.objects.filter(is_staff=True):
            Notification.objects.create(
                user=admin_user, actor=request.user, kind="REPORT_UPDATE",
                text=f"Message signalé (>=3) dans {msg.room.name}",
                room=msg.room, room_message=msg
            )

    return redirect("community_room_detail", slug=msg.room.slug)


@login_required
def message_delete(request, msg_id: int):
    msg = get_object_or_404(Message, pk=msg_id)
    if not user_can_access(msg.room, request.user):
        return HttpResponseForbidden("Accès refusé.")
    if request.method != "POST":
        return redirect("community_room_detail", slug=msg.room.slug)

    if not can_delete_message(request.user, msg.sender):
        return HttpResponseForbidden("Suppression interdite.")

    msg.is_deleted = True
    msg.deleted_by = request.user
    msg.deleted_at = now()
    msg.content = ""  # on vide le contenu
    msg.save(update_fields=["is_deleted", "deleted_by", "deleted_at", "content"])
    return redirect("community_room_detail", slug=msg.room.slug)


# ----------------- NOTIFICATIONS -----------------

@login_required
def notifications(request):
    notifs = Notification.objects.filter(user=request.user).order_by("-created_at")[:200]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, "community/notifications.html", {"notifs": notifs, "unread_count": unread_count})


@login_required
def notification_mark_read(request, notif_id: int):
    n = get_object_or_404(Notification, pk=notif_id, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect("community_notifications")


# ----------------- DM (privé) -----------------

def _get_or_create_conversation(u1: User, u2: User) -> Conversation:
    # impose ordre par id pour éviter doublons
    a, b = (u1, u2) if u1.id < u2.id else (u2, u1)
    conv, _ = Conversation.objects.get_or_create(user1=a, user2=b)
    return conv


@login_required
def dm_inbox(request):
    # conversations où l'utilisateur est user1 ou user2
    convs = Conversation.objects.filter(models.Q(user1=request.user) | models.Q(user2=request.user)).order_by("-updated_at")
    return render(request, "community/dm_inbox.html", {"convs": convs})


@login_required
def dm_start(request, username: str):
    other = get_object_or_404(User, username=username)
    if other.id == request.user.id:
        return redirect("community_dm_inbox")
    conv = _get_or_create_conversation(request.user, other)
    return redirect("community_dm_thread", conv_id=conv.id)


@login_required
def dm_thread(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id)
    if request.user.id not in (conv.user1_id, conv.user2_id):
        return HttpResponseForbidden("Accès refusé.")

    if request.method == "POST":
        content = (request.POST.get("content") or "").strip()
        images = request.FILES.getlist("images")

        if content or images:
            msg = DirectMessage.objects.create(conversation=conv, sender=request.user, content=content or "")
            for f in images:
                DirectMessageImage.objects.create(message=msg, image=f)

            conv.save(update_fields=["updated_at"])  # bump
            _create_mentions_notifications(request.user, msg.content, conversation=conv, dm_message=msg)

        return redirect("community_dm_thread", conv_id=conv.id)

    messages_qs = (
        conv.messages
        .select_related("sender")
        .prefetch_related("images")
        .filter(is_deleted=False)
        .order_by("-id")[:200]
    )
    messages_list = list(reversed(messages_qs))
    other = conv.other(request.user)

    return render(
        request,
        "community/dm_thread.html",
        {"conv": conv, "other": other, "messages": messages_list},
    )


@login_required
def dm_messages_json(request, conv_id: int):
    conv = get_object_or_404(Conversation, pk=conv_id)
    if request.user.id not in (conv.user1_id, conv.user2_id):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    after = request.GET.get("after", "0")
    try:
        after_id = int(after)
    except Exception:
        after_id = 0

    qs = (
        conv.messages
        .select_related("sender")
        .prefetch_related("images")
        .filter(is_deleted=False, id__gt=after_id)
        .order_by("id")[:100]
    )

    out = []
    for m in qs:
        out.append({
            "id": m.id,
            "sender": m.sender.username,
            "is_me": (m.sender_id == request.user.id),
            "is_admin": bool(m.sender.is_staff or m.sender.is_superuser),
            "content": m.content,
            "created_at": localtime(m.created_at).strftime("%d/%m/%Y %H:%M"),
            "images": [img.image.url for img in m.images.all()],
            "can_delete": can_delete_message(request.user, m.sender),
        })

    return JsonResponse({"ok": True, "messages": out})


@login_required
def dm_message_report(request, msg_id: int):
    msg = get_object_or_404(DirectMessage, pk=msg_id)
    conv = msg.conversation
    if request.user.id not in (conv.user1_id, conv.user2_id):
        return HttpResponseForbidden("Accès refusé.")
    if request.method != "POST":
        return redirect("community_dm_thread", conv_id=conv.id)

    reason = (request.POST.get("reason") or "").strip()[:255]
    DirectMessageReport.objects.get_or_create(message=msg, reporter=request.user, defaults={"reason": reason})

    if msg.reports.count() >= 3:
        for admin_user in User.objects.filter(is_staff=True):
            Notification.objects.create(
                user=admin_user, actor=request.user, kind="REPORT_UPDATE",
                text="DM signalé (>=3)",
                conversation=conv, dm_message=msg
            )

    return redirect("community_dm_thread", conv_id=conv.id)


@login_required
def dm_message_delete(request, msg_id: int):
    msg = get_object_or_404(DirectMessage, pk=msg_id)
    conv = msg.conversation
    if request.user.id not in (conv.user1_id, conv.user2_id):
        return HttpResponseForbidden("Accès refusé.")
    if request.method != "POST":
        return redirect("community_dm_thread", conv_id=conv.id)

    if not can_delete_message(request.user, msg.sender):
        return HttpResponseForbidden("Suppression interdite.")

    msg.is_deleted = True
    msg.deleted_by = request.user
    msg.deleted_at = now()
    msg.content = ""
    msg.save(update_fields=["is_deleted", "deleted_by", "deleted_at", "content"])
    return redirect("community_dm_thread", conv_id=conv.id)