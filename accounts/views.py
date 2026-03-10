from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Profile

def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        role = request.POST.get("role", "BUYER")
        phone = request.POST.get("phone", "").strip()
        city = request.POST.get("city", "").strip()

        if not username or not password:
            messages.error(request, "Username et mot de passe requis.")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Ce username existe déjà.")
            return redirect("signup")

        user = User.objects.create_user(username=username, password=password)

        profile = Profile.objects.get(user=user)
        profile.role = role
        profile.phone = phone
        profile.city = city
        profile.save()

        login(request, user)
        return redirect("dashboard")

    return render(request, "accounts/signup.html")

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("dashboard")
        messages.error(request, "Identifiants invalides.")
        return redirect("login")

    return render(request, "accounts/login.html")

def logout_view(request):
    logout(request)
    return redirect("home")
