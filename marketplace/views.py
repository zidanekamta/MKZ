from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib import messages
from django.db import transaction
import os
import uuid
from .payment_providers import MtnMomoProvider, OrangeMoneyProvider
from .models import PaymentTransaction

from accounts.models import Profile
from .models import (
    Listing, ListingPhoto, Review,
    Cart, CartItem,
    Order, OrderItem
)
from .payments import initiate_payment, webhook_simulator


def _wa(phone: str) -> str:
    if not phone:
        return ""
    num = phone.replace("+", "").replace(" ", "")
    return f"https://wa.me/{num}"


def home(request):
    return render(request, "marketplace/home.html")


def listing_list(request):
    q = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    ptype = request.GET.get("type", "").strip()

    qs = (
        Listing.objects
        .select_related("breeder")
        .prefetch_related("photos", "reviews")
        .order_by("-created_at")
    )

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if city:
        qs = qs.filter(city__icontains=city)
    if ptype in ["LIVE", "MEAT"]:
        qs = qs.filter(product_type=ptype)

    return render(request, "marketplace/listing_list.html", {"listings": qs})


def listing_detail(request, pk):
    listing = (
        Listing.objects
        .select_related("breeder")
        .prefetch_related("photos", "reviews", "reviews__buyer")
        .get(pk=pk)
    )

    reviews = listing.reviews.select_related("buyer").all()

    # ✅ badge éleveur vérifié (safe)
    breeder_profile = getattr(listing.breeder, "profile", None)
    breeder_verified = bool(getattr(breeder_profile, "verified", False))

    # ✅ photos
    photos = list(listing.photos.all())
    primary_photo = photos[0] if photos else None

    return render(
        request,
        "marketplace/listing_detail.html",
        {
            "listing": listing,
            "reviews": reviews,
            "breeder_verified": breeder_verified,
            "photos": photos,
            "primary_photo": primary_photo,
        },
    )
@login_required
def dashboard(request):
    profile = Profile.objects.get(user=request.user)

    if profile.role == "BREEDER":
        my_listings = Listing.objects.filter(breeder=request.user).order_by("-created_at")

        # ✅ Commandes reçues (aperçu)
        received_items = (
            OrderItem.objects
            .select_related("order", "listing", "order__buyer")
            .filter(breeder=request.user)
            .order_by("-order__created_at")
        )
        received_orders_ids = list(received_items.values_list("order_id", flat=True).distinct())
        received_orders_count = len(received_orders_ids)

        recent_received = []
        seen = set()
        for it in received_items[:20]:  # on prend un peu large puis on déduplique
            if it.order_id in seen:
                continue
            seen.add(it.order_id)
            recent_received.append(it.order)
            if len(recent_received) >= 3:
                break

        return render(
            request,
            "marketplace/dashboard_breeder.html",
            {
                "profile": profile,
                "my_listings": my_listings,
                "received_orders_count": received_orders_count,
                "recent_received": recent_received,
            },
        )

    # Acheteur: 3 dernières commandes
    recent_orders = Order.objects.filter(buyer=request.user).order_by("-created_at")[:3]
    return render(
        request,
        "marketplace/dashboard_buyer.html",
        {"profile": profile, "recent_orders": recent_orders},
    )


@login_required
def listing_create(request):
    profile = Profile.objects.get(user=request.user)
    if profile.role != "BREEDER":
        messages.error(request, "Seuls les éleveurs peuvent publier.")
        return redirect("dashboard")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        product_type = request.POST.get("product_type", "LIVE")
        city = request.POST.get("city", "").strip()
        price_fcfa = int(request.POST.get("price_fcfa", "0") or "0")
        quantity = int(request.POST.get("quantity", "1") or "1")
        description = request.POST.get("description", "").strip()
        whatsapp = request.POST.get("whatsapp", "").strip()

        if not title or not city or price_fcfa <= 0 or not whatsapp:
            messages.error(request, "Merci de remplir les champs obligatoires.")
            return redirect("listing_create")

        listing = Listing.objects.create(
            breeder=request.user,
            title=title,
            product_type=product_type,
            city=city,
            price_fcfa=price_fcfa,
            quantity=quantity,
            description=description,
            whatsapp=whatsapp,
        )

        for img in request.FILES.getlist("photos"):
            ListingPhoto.objects.create(listing=listing, image=img)

        messages.success(request, "Annonce publiée ✅")
        return redirect("dashboard")

    return render(request, "marketplace/listing_create.html")


@login_required
def listing_delete(request, pk):
    listing = get_object_or_404(Listing, pk=pk, breeder=request.user)
    if request.method == "POST":
        listing.delete()
        messages.success(request, "Annonce supprimée.")
    return redirect("dashboard")


@login_required
def add_review(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    profile = Profile.objects.get(user=request.user)

    if profile.role != "BUYER":
        messages.error(request, "Seuls les acheteurs peuvent laisser un avis.")
        return redirect("listing_detail", pk=pk)

    if request.method == "POST":
        rating = int(request.POST.get("rating", "0") or "0")
        comment = request.POST.get("comment", "").strip()

        if rating < 1 or rating > 5:
            messages.error(request, "Note invalide (1 à 5).")
            return redirect("listing_detail", pk=pk)

        Review.objects.update_or_create(
            listing=listing,
            buyer=request.user,
            defaults={"rating": rating, "comment": comment},
        )

        messages.success(request, "Merci pour votre avis !")
    return redirect("listing_detail", pk=pk)


# -------------------------
# PANIER (Phase A)
# -------------------------

@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related("listing").all()
    subtotal = sum(it.listing.price_fcfa * it.quantity for it in items)
    return render(request, "marketplace/cart.html", {"items": items, "subtotal": subtotal})


@login_required
def cart_add(request, pk):
    if request.method != "POST":
        return redirect("listing_detail", pk=pk)

    listing = get_object_or_404(Listing, pk=pk)
    cart, _ = Cart.objects.get_or_create(user=request.user)

    qty = int(request.POST.get("quantity", "1") or "1")
    qty = max(1, qty)

    item, created = CartItem.objects.get_or_create(
        cart=cart, listing=listing, defaults={"quantity": qty}
    )
    if not created:
        item.quantity += qty
        item.save()

    messages.success(request, "Ajouté au panier ✅")
    return redirect("cart_view")


@login_required
def cart_remove(request, pk):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    CartItem.objects.filter(cart=cart, listing_id=pk).delete()
    messages.info(request, "Article retiré du panier.")
    return redirect("cart_view")


# -------------------------
# CHECKOUT + COMMANDES (Phase A)
# -------------------------

@login_required
@transaction.atomic
def checkout(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related("listing", "listing__breeder").all()

    if not items:
        messages.error(request, "Ton panier est vide.")
        return redirect("cart_view")

    subtotal = sum(it.listing.price_fcfa * it.quantity for it in items)

    if request.method == "POST":
        delivery_city = request.POST.get("delivery_city", "").strip()
        delivery_address = request.POST.get("delivery_address", "").strip()
        delivery_phone = request.POST.get("delivery_phone", "").strip()
        note = request.POST.get("note", "").strip()

        payment_method = request.POST.get("payment_method", "COD")  # COD / MTN_MOMO / ORANGE_OM

        if not delivery_city or not delivery_address or not delivery_phone:
            messages.error(request, "Ville, adresse et téléphone sont obligatoires.")
            return redirect("checkout")

        order = Order.objects.create(
            buyer=request.user,
            status="CREATED",
            total_fcfa=subtotal,
            delivery_city=delivery_city,
            delivery_address=delivery_address,
            delivery_phone=delivery_phone,
            note=note,
        )

        for it in items:
            OrderItem.objects.create(
                order=order,
                listing=it.listing,
                breeder=it.listing.breeder,
                unit_price_fcfa=it.listing.price_fcfa,
                quantity=it.quantity,
                status="PENDING",
            )

        cart.items.all().delete()

        if payment_method == "COD":
            order.status = "CONFIRMED"
            order.save(update_fields=["status"])
            messages.success(request, f"Commande créée ✅ (N°{order.id}). Paiement à la livraison/WhatsApp.")
            return redirect("order_detail", pk=order.id)

        # Paiement en ligne (Phase 2)
        return redirect("payment_start_order", order_id=order.id)

    return render(request, "marketplace/checkout.html", {"items": items, "subtotal": subtotal})


@login_required
def orders_list(request):
    orders = Order.objects.filter(buyer=request.user).order_by("-created_at")
    return render(request, "marketplace/orders_list.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, buyer=request.user)
    items = order.items.select_related("listing", "breeder").all()
    return render(request, "marketplace/order_detail.html", {"order": order, "items": items})


# -------------------------
# COMMANDES REÇUES (ÉLEVEUR)
# -------------------------

@login_required
def breeder_orders(request):
    profile = Profile.objects.get(user=request.user)
    if profile.role != "BREEDER":
        messages.error(request, "Accès réservé aux éleveurs.")
        return redirect("dashboard")

    items = (
        OrderItem.objects
        .select_related("order", "listing", "order__buyer")
        .filter(breeder=request.user)
        .order_by("-order__created_at")
    )

    # Group par commande
    orders_map = {}
    for it in items:
        orders_map.setdefault(it.order_id, {"order": it.order, "items": []})
        orders_map[it.order_id]["items"].append(it)

    grouped = list(orders_map.values())
    grouped.sort(key=lambda x: x["order"].created_at, reverse=True)

    return render(request, "marketplace/breeder_orders.html", {"grouped": grouped})


@login_required
def breeder_order_detail(request, order_id: int):
    profile = Profile.objects.get(user=request.user)
    if profile.role != "BREEDER":
        messages.error(request, "Accès réservé aux éleveurs.")
        return redirect("dashboard")

    order = get_object_or_404(Order, pk=order_id)
    items = (
        OrderItem.objects
        .select_related("listing", "order__buyer")
        .filter(order=order, breeder=request.user)
        .order_by("-id")
    )

    buyer_whatsapp = _wa(order.delivery_phone)

    return render(
        request,
        "marketplace/breeder_order_detail.html",
        {"order": order, "items": items, "buyer_whatsapp": buyer_whatsapp},
    )


@login_required
def breeder_item_set_status(request, item_id: int, status: str):
    profile = Profile.objects.get(user=request.user)
    if profile.role != "BREEDER":
        messages.error(request, "Accès réservé aux éleveurs.")
        return redirect("dashboard")

    if request.method != "POST":
        return redirect("breeder_orders")

    if status not in ["FULFILLED", "CANCELLED", "PENDING"]:
        messages.error(request, "Statut invalide.")
        return redirect("breeder_orders")

    it = get_object_or_404(OrderItem, pk=item_id, breeder=request.user)
    it.status = status
    it.save(update_fields=["status", "updated_at"])

    # Auto-update statut global commande si possible
    order = it.order
    all_items = list(order.items.all())
    if all_items and all(x.status == "FULFILLED" for x in all_items):
        order.status = "FULFILLED"
        order.save(update_fields=["status"])
    elif all_items and all(x.status == "CANCELLED" for x in all_items):
        order.status = "CANCELLED"
        order.save(update_fields=["status"])

    messages.success(request, f"Article mis à jour ✅ ({it.get_status_display()})")
    return redirect("breeder_order_detail", order_id=it.order_id)


# -------------------------
# Paiements (Phase 2 — démo)
# -------------------------

@login_required
def payment_start(request):
    if request.method == "POST":
        provider = request.POST.get("provider", "MTN_MOMO")
        amount_fcfa = int(request.POST.get("amount_fcfa", "0") or "0")

        if amount_fcfa <= 0:
            messages.error(request, "Montant invalide.")
            return redirect("dashboard")

        tx = initiate_payment(request.user, amount_fcfa, provider)
        messages.info(request, f"Transaction créée (DEMO) ref={tx.reference} status={tx.status}")
    return redirect("dashboard")


@login_required
def payment_simulate_success(request, reference):
    tx = webhook_simulator(reference, success=True)
    messages.success(request, f"Paiement simulé: {tx.status} (ref={tx.reference})")
    return redirect("dashboard")


@login_required
def payment_start_order(request, order_id: int):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status != "CREATED":
        messages.info(request, "Cette commande n’est plus en attente de paiement.")
        return redirect("order_detail", pk=order.id)

    if request.method == "POST":
        provider = request.POST.get("provider", "MTN_MOMO")
        payer_msisdn = request.POST.get("payer_msisdn", "").strip()
        otp_or_pin = request.POST.get("otp_or_pin", "").strip()  # utilisé seulement pour Orange (si requis)

        if not payer_msisdn:
            messages.error(request, "Numéro du payeur obligatoire.")
            return redirect("payment_start_order", order_id=order.id)

        # Crée transaction
        tx = PaymentTransaction.objects.create(
            user=request.user,
            order=order,
            amount_fcfa=order.total_fcfa,
            currency="XAF",
            provider=provider,
            status="PENDING",
            reference=str(uuid.uuid4()),  # provisoire, sera remplacée par vraie ref
            payer_msisdn=payer_msisdn,
        )

        try:
            if provider == "MTN_MOMO":
                momo = MtnMomoProvider(
                    base_url=os.getenv("MKZ_MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com"),
                    subscription_key=os.getenv("MKZ_MOMO_SUBSCRIPTION_KEY", ""),
                    api_user=os.getenv("MKZ_MOMO_API_USER", ""),
                    api_key=os.getenv("MKZ_MOMO_API_KEY", ""),
                    target_env=os.getenv("MKZ_MOMO_TARGET_ENV", "sandbox"),
                )
                callback_url = os.getenv("MKZ_MOMO_CALLBACK_URL", "") or None

                resp = momo.request_to_pay(
                    amount=order.total_fcfa,
                    currency="XAF",
                    external_id=f"MKZ-ORDER-{order.id}",
                    payer_msisdn=payer_msisdn,
                    payer_message=f"Paiement MKZ commande #{order.id}",
                    payee_note="Merci pour votre achat MKZ",
                    callback_url=callback_url,
                )

                # La vraie référence MoMo = X-Reference-Id (UUID) :contentReference[oaicite:10]{index=10}
                tx.reference = resp["reference"]
                tx.raw_request = resp["request"]
                tx.raw_response = {"status": resp["response_status"], "text": resp["response_text"]}
                tx.save(update_fields=["reference", "raw_request", "raw_response"])

            elif provider == "ORANGE_OM":
                orange = OrangeMoneyProvider(
                    base_url=os.getenv("MKZ_ORANGE_BASE_URL", "https://api-s1.orange.cm/omcoreapis/1.0.0"),
                    bearer_token=os.getenv("MKZ_ORANGE_BEARER_TOKEN", ""),
                    x_auth_token=os.getenv("MKZ_ORANGE_X_AUTH_TOKEN", ""),
                    channel_msisdn=os.getenv("MKZ_ORANGE_CHANNEL_MSISDN", ""),
                )
                notif_url = os.getenv("MKZ_ORANGE_CALLBACK_URL", "") or None

                init_data = orange.mp_init()
                pay_token = init_data.get("data", {}).get("payToken") or init_data.get("payToken")
                if not pay_token:
                    raise RuntimeError(f"Orange mp/init: payToken introuvable: {init_data}")

                pay_resp = orange.mp_pay(
                    pay_token=pay_token,
                    subscriber_msisdn=payer_msisdn,
                    amount=order.total_fcfa,
                    order_id=str(order.id),
                    description=f"Paiement MKZ commande #{order.id}",
                    otp_or_pin=otp_or_pin,
                    notif_url=notif_url,
                )

                # Référence Orange = payToken :contentReference[oaicite:11]{index=11}
                tx.reference = str(pay_token)
                tx.raw_request = {"init": init_data, "pay": pay_resp["request"]}
                tx.raw_response = pay_resp["response"]
                tx.save(update_fields=["reference", "raw_request", "raw_response"])

            else:
                raise RuntimeError("Provider invalide")

        except Exception as e:
            tx.status = "FAILED"
            tx.raw_response = {"error": str(e)}
            tx.save(update_fields=["status", "raw_response"])
            messages.error(request, f"Paiement échoué: {e}")
            return redirect("payment_start_order", order_id=order.id)

        return redirect("payment_status", tx_id=tx.id)

    return render(request, "marketplace/payment_start.html", {"order": order})


@login_required
def payment_status(request, tx_id: int):
    tx = get_object_or_404(PaymentTransaction, pk=tx_id, user=request.user)
    order = tx.order

    # Rafraîchir statut
    if request.method == "POST":
        try:
            if tx.provider == "MTN_MOMO":
                momo = MtnMomoProvider(
                    base_url=os.getenv("MKZ_MOMO_BASE_URL", "https://sandbox.momodeveloper.mtn.com"),
                    subscription_key=os.getenv("MKZ_MOMO_SUBSCRIPTION_KEY", ""),
                    api_user=os.getenv("MKZ_MOMO_API_USER", ""),
                    api_key=os.getenv("MKZ_MOMO_API_KEY", ""),
                    target_env=os.getenv("MKZ_MOMO_TARGET_ENV", "sandbox"),
                )
                st = momo.get_status(tx.reference)
                tx.raw_response = {"status_check": st}

                # Heuristique: si on reçoit un status "SUCCESSFUL"/"SUCCESS" etc.
                status_text = str(st.get("data") or st.get("text") or "").upper()
                if "SUCCESS" in status_text:
                    tx.status = "SUCCESS"
                elif "FAIL" in status_text or "REJECT" in status_text:
                    tx.status = "FAILED"

                tx.save(update_fields=["status", "raw_response"])

            elif tx.provider == "ORANGE_OM":
                orange = OrangeMoneyProvider(
                    base_url=os.getenv("MKZ_ORANGE_BASE_URL", "https://api-s1.orange.cm/omcoreapis/1.0.0"),
                    bearer_token=os.getenv("MKZ_ORANGE_BEARER_TOKEN", ""),
                    x_auth_token=os.getenv("MKZ_ORANGE_X_AUTH_TOKEN", ""),
                    channel_msisdn=os.getenv("MKZ_ORANGE_CHANNEL_MSISDN", ""),
                )
                st = orange.mp_status(tx.reference)
                tx.raw_response = {"status_check": st}

                status_text = str(st.get("data") or st.get("text") or "").upper()
                if "SUCCESS" in status_text:
                    tx.status = "SUCCESS"
                elif "FAIL" in status_text or "CANCEL" in status_text:
                    tx.status = "FAILED"

                tx.save(update_fields=["status", "raw_response"])

        except Exception as e:
            messages.error(request, f"Erreur statut: {e}")

    # Si paiement OK -> commande confirmée
    if order and tx.status == "SUCCESS" and order.status == "CREATED":
        order.status = "CONFIRMED"
        order.save(update_fields=["status"])

    return render(request, "marketplace/payment_status.html", {"tx": tx, "order": order})