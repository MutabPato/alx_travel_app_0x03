from django.contrib import admin
from django.urls import path, include
from rest_framework_nested import routers
from .views import (
    UserViewset,
    ListingViewset,
    BookingViewset,
    ReviewViewSet,
    initialize_payment,
    verify_payment
    )

# Main router for top-level resources
router = routers.DefaultRouter()
router.register(r'users', UserViewset, basename='users')
router.register(r'listings', ListingViewset, basename='listings')
router.register(r'bookings', BookingViewset, basename='bookings')

# Nested router for reviews under listings, will create URLS like: /api/listings/{listing_slug}/reviews

listings_router = routers.NestedSimpleRouter(router, r'listings', lookup='listing')
listings_router.register(r'reviews', ReviewViewSet, basename='listing-reviews')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(listings_router.urls)),
    path('api-auth', include('rest_framework.urls', namespace='rest_framework')),
    path('payments/initialize-payment/', initialize_payment, name='initialize-payment'),
    path('payments/verify-payment/<str:tx_ref>/', verify_payment, name='verify-payment'),
]
