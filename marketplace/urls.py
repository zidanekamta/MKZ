from django.urls import path
from .views import (
    home, listing_list, listing_detail,
    dashboard, listing_create, listing_delete, add_review,
    cart_view, cart_add, cart_remove,
    checkout, orders_list, order_detail,
    breeder_orders, breeder_order_detail, breeder_item_set_status,
    payment_start, payment_simulate_success,
    payment_start_order, payment_status,
)

urlpatterns = [
    path("", home, name="home"),
    path("annonces/", listing_list, name="listing_list"),
    path("annonces/<int:pk>/", listing_detail, name="listing_detail"),
    path("annonces/<int:pk>/review/", add_review, name="add_review"),

    path("dashboard/", dashboard, name="dashboard"),
    path("dashboard/annonces/new/", listing_create, name="listing_create"),
    path("dashboard/annonces/<int:pk>/delete/", listing_delete, name="listing_delete"),

    # Panier + Commandes (Phase A)
    path("cart/", cart_view, name="cart_view"),
    path("cart/add/<int:pk>/", cart_add, name="cart_add"),
    path("cart/remove/<int:pk>/", cart_remove, name="cart_remove"),

    path("checkout/", checkout, name="checkout"),
    path("orders/", orders_list, name="orders_list"),
    path("orders/<int:pk>/", order_detail, name="order_detail"),

    # ✅ Commandes reçues (Éleveur)
    path("dashboard/orders/", breeder_orders, name="breeder_orders"),
    path("dashboard/orders/<int:order_id>/", breeder_order_detail, name="breeder_order_detail"),
    path("dashboard/orders/item/<int:item_id>/<str:status>/", breeder_item_set_status, name="breeder_item_set_status"),

    # Phase 2 payments (demo)
    path("dashboard/payment/start/", payment_start, name="payment_start"),
    path("dashboard/payment/simulate/<str:reference>/", payment_simulate_success, name="payment_simulate_success"),

    path("payments/start/<int:order_id>/", payment_start_order, name="payment_start_order"),
    path("payments/status/<int:tx_id>/", payment_status, name="payment_status"),
]