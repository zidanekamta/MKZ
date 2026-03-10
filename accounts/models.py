from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    ROLE_CHOICES = [
        ("BREEDER", "Éleveur"),
        ("BUYER", "Acheteur"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=120, blank=True)
    verified = models.BooleanField(default=False)  # Éleveur vérifié (admin)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
