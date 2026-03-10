from django.contrib import admin
from .models import Listing, ListingPhoto, Review, PaymentTransaction

class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 1

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "product_type", "city", "price_fcfa", "quantity", "breeder", "created_at")
    list_filter = ("product_type", "city")
    search_fields = ("title", "city", "description", "breeder__username")
    inlines = [ListingPhotoInline]

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("listing", "buyer", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("listing__title", "buyer__username", "comment")

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "amount_fcfa", "status", "reference", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("user__username", "reference")
