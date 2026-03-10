from django.db import models
from django.contrib.auth.models import User

class Listing(models.Model):
    PRODUCT_TYPE = [
        ("LIVE", "Lapin vivant"),
        ("MEAT", "Viande de lapin"),
    ]

    breeder = models.ForeignKey(User, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=200)
    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE)
    city = models.CharField(max_length=120)
    price_fcfa = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    description = models.TextField(blank=True)
    whatsapp = models.CharField(max_length=30, help_text="Numéro WhatsApp, ex: 2376XXXXXXX")
    created_at = models.DateTimeField(auto_now_add=True)

    def whatsapp_link(self):
        num = self.whatsapp.replace("+", "").replace(" ", "")
        return f"https://wa.me/{num}"

    def avg_rating(self):
        agg = self.reviews.aggregate(models.Avg("rating"))
        return agg["rating__avg"] or 0

    def __str__(self):
        return self.title

class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="listings/")

class Review(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="reviews")
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_made")
    rating = models.PositiveSmallIntegerField()  # 1..5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("listing", "buyer")
        ordering = ["-created_at"]

class PaymentTransaction(models.Model):
    PROVIDER_CHOICES = [
        ("MTN_MOMO", "MTN MoMo"),
        ("ORANGE_OM", "Orange Money"),
    ]
    STATUS_CHOICES = [
        ("PENDING", "En attente"),
        ("SUCCESS", "Succès"),
        ("FAILED", "Échec"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey("Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")

    amount_fcfa = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XAF")

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")

    # Référence interne (ex: UUID MoMo X-Reference-Id, ou payToken Orange)
    reference = models.CharField(max_length=64, unique=True)

    # Téléphone du payeur (acheteur)
    payer_msisdn = models.CharField(max_length=30, blank=True)

    # Données utiles (debug)
    raw_request = models.JSONField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider} {self.amount_fcfa}{self.currency} {self.status}"

# --- PANIER + COMMANDES (Phase A) ---

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="cart")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart({self.user.username})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "listing")

    def __str__(self):
        return f"{self.listing.title} x{self.quantity}"


class Order(models.Model):
    STATUS = [
        ("CREATED", "Créée"),
        ("CONFIRMED", "Confirmée (paiement à la livraison)"),
        ("CANCELLED", "Annulée"),
        ("FULFILLED", "Livrée/Terminée"),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS, default="CREATED")
    total_fcfa = models.PositiveIntegerField(default=0)

    delivery_city = models.CharField(max_length=120, blank=True)
    delivery_address = models.CharField(max_length=255, blank=True)
    delivery_phone = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order#{self.id} {self.buyer.username} {self.status}"


class OrderItem(models.Model):
    STATUS = [
        ("PENDING", "En attente"),
        ("FULFILLED", "Livré"),
        ("CANCELLED", "Annulé"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    listing = models.ForeignKey(Listing, on_delete=models.PROTECT)
    breeder = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders_received")
    unit_price_fcfa = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS, default="PENDING")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order#{self.order_id} {self.listing.title} x{self.quantity} [{self.status}]"