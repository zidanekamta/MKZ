from rest_framework import serializers
from .models import Listing, ListingPhoto, Review

class ListingPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingPhoto
        fields = ["id", "image"]

class ReviewSerializer(serializers.ModelSerializer):
    buyer_username = serializers.CharField(source="buyer.username", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "buyer_username", "rating", "comment", "created_at"]

class ListingSerializer(serializers.ModelSerializer):
    whatsapp_url = serializers.SerializerMethodField()
    photos = ListingPhotoSerializer(many=True, read_only=True)
    avg_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "product_type", "city", "price_fcfa", "quantity",
            "description", "whatsapp", "whatsapp_url", "created_at",
            "photos", "avg_rating", "reviews_count",
        ]

    def get_whatsapp_url(self, obj):
        return obj.whatsapp_link()

    def get_avg_rating(self, obj):
        return round(float(obj.avg_rating()), 2)

    def get_reviews_count(self, obj):
        return obj.reviews.count()
