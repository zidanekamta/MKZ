from django.urls import path
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Listing
from .serializers import ListingSerializer, ReviewSerializer

@api_view(["GET"])
def listings(request):
    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    ptype = request.GET.get("type", "").strip()

    qs = Listing.objects.all().order_by("-created_at")
    if q:
        qs = qs.filter(title__icontains=q)
    if city:
        qs = qs.filter(city__icontains=city)
    if ptype in ["LIVE", "MEAT"]:
        qs = qs.filter(product_type=ptype)

    return Response(ListingSerializer(qs, many=True, context={"request": request}).data)

@api_view(["GET"])
def listing_detail(request, pk: int):
    obj = Listing.objects.get(pk=pk)
    return Response(ListingSerializer(obj, context={"request": request}).data)

@api_view(["GET"])
def listing_reviews(request, pk: int):
    obj = Listing.objects.get(pk=pk)
    return Response(ReviewSerializer(obj.reviews.all(), many=True).data)

urlpatterns = [
    path("listings/", listings),
    path("listings/<int:pk>/", listing_detail),
    path("listings/<int:pk>/reviews/", listing_reviews),
]
