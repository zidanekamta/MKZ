from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Room

@receiver(post_migrate)
def create_default_rooms(sender, **kwargs):
    # Crée seulement lors des migrations (toutes apps) — on filtre par nom app si besoin
    try:
        Room.objects.get_or_create(
            name="MKZ • Communauté",
            defaults={
                "description": "Groupe général : Éleveurs + Acheteurs + Admin.",
                "visibility": "ALL",
                "post_permission": "ALL",
            },
        )
        Room.objects.get_or_create(
            name="MKZ • Annonces officielles",
            defaults={
                "description": "Infos officielles (seuls les admins publient).",
                "visibility": "ALL",
                "post_permission": "ADMINS_ONLY",
            },
        )
        Room.objects.get_or_create(
            name="MKZ • Support",
            defaults={
                "description": "Assistance et questions (Admin + utilisateurs).",
                "visibility": "ALL",
                "post_permission": "ALL",
            },
        )
    except Exception:
        # Eviter de casser migrate si db pas prête
        pass