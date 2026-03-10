from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Profile
from .serializers import ProfileSerializer

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    profile = Profile.objects.get(user=request.user)
    return Response(ProfileSerializer(profile).data)

urlpatterns = [
    path("me/", me),
]
