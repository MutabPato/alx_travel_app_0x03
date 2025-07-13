import uuid
import requests
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.decorators import action, api_view, permission_classes
from .models import Listing, Booking, Review, Payment
from .serializers import (
    UserSerializer,
    ListingSerializer,
    ListingDetailSerializer,
    BookingSerializer,
    ReviewSerializer,
    PaymentSerializer
    )
from .permissions import IsOwnerOrReadOnly
from .tasks import send_booking_confirmation_email

User = get_user_model()

class UserViewset(viewsets.ModelViewSet):
    """
    Simple viewset for viewing user accounts.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


class ListingViewset(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    lookup_field = 'slug'

    def get_serializer_class(self):
        """
        Returns the appropriate serializer class based on the action.
        - 'ListingDetailSerializer' for retrieve (detail) view.
        - 'ListingSerializer' for all other actions (list, create, etc.).
        """
        if self.action == 'retrieve':
            return ListingDetailSerializer
        return ListingSerializer
    
    def get_permissions(self):
        """
        Assigns permission based on the action.
        - 'AllowAny' for safe methods (list, retrieve).
        - 'IsAuthenticated' and 'IsOwnerOrReadOnly' for other actions.
        """
        if self.action in ['list', 'retrieve']:
            self.permission_classes = [AllowAny]
        else:
            self.permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
        return super().get_permissions()

    def perform_create(self, serializer):
        """Sets the owner of the listing to the current authenticated user."""
        serializer.save(owner=self.request.user)


class BookingViewset(viewsets.ModelViewSet):
    """
    ViewSet for handling Bookings.
    - Users can only see their own bookings.
    - Users can create bookings.
    - Users can cancel their bookings.
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        """This view returns a list of all the bookings for current authenticated user"""
        return Booking.objects.filter(guest=self.request.user)
    
    def perform_create(self, serializer):
        """Passes the request context to the serializer for validation and creation."""
        # serializer.save(guest=self.request.user) returns the created model instance
        booking = serializer.save(guest=self.request.user)
        send_booking_confirmation_email.delay(booking.id)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Custom action to cancel a ooking."""
        booking = self.get_object()
        if booking.status in [Booking.BookingStatus.CONFIRMED, Booking.BookingStatus.PENDING]:
            booking.status = Booking.BookingStatus.CANCELLED
            booking.save()
            return Response({'status': 'Booking cancelled'}, status=status.HTTP_200_OK)
        return Response({'error': f'Booking in {booking.status} and cannot be cancelled'}, status=status.HTTP_400_BAD_REQUEST)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling reviews for a specific listing.
    - 'api/listings/{slug}/reviews'
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        """Returns all reviews for a specific listing, identified by 'listing_slug' from the url."""
        return Review.objects.filter(listing__slug=self.kwargs['listing_slug'])
    
    def perform_create(self, serializer):
        """Creates a review and associates it with the listing from the url and the authenticated user."""
        listing = Listing.objects.get(slug=self.kwargs['listing_slug'])
        serializer.save(author=self.request.user, listing=listing)


@api_view(['POST'])
@permission_classes([AllowAny])
def initialize_payment(request):
    data = request.data
    tx_ref = str(uuid.uuid4())

    try:
        booking = Booking.objects.get(id=data['booking_id'])
    except Booking.DoesNotExist:
        return Response({"error": "Booking not found."}, status=404)

    payload = {
        "amount": str(booking.total_price),
        "currency": "ETB",
        "email": data.get("email"),
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "tx_ref": tx_ref,
        "callback_url": f"http://127.0.0.1:8000/payments/verify-payment/{tx_ref}/",
        "return_url": "http://localhost:8000/payment-success/"
    }

    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers)

    if response.status_code != 200:
        return Response(
            {"error": "Failed to initialize payment.", "details": response.json()},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    result = response.json()
    if result.get("status") == "success":
        Payment.objects.create(
            booking=booking,
            tx_ref=tx_ref,
            amount=booking.total_price,
            email=data.get("email"),
            status="Pending"
        )
        return Response({"checkout_url": result['data']['checkout_url'], "tx_ref": tx_ref})

    return Response(
        {"error": "Failed to initialize payment.", "details": result},
        status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_payment(request, tx_ref):
    headers = {
        "Authorization": f"Bearer {settings.CHAPA_SECRET_KEY}"
    }

    chapa_url = f"https://api.chapa.co/v1/transaction/verify/{tx_ref}"
    response = requests.get(chapa_url, headers=headers)
    result = response.json()

    if response.status_code != 200:
        return Response({"error": "Verification request failed.", "details": response.json()}, status=400)

    result = response.json()
    if result.get("status") == "success":
        try:
            payment = Payment.objects.get(tx_ref=tx_ref)
            if result.get("data", {}).get("status") == "success":
                payment.status = "Completed"
                payment.booking.status = Booking.BookingStatus.CONFIRMED
                payment.booking.save()
                payment.save()
                # send_booking_confirmation_email.delay(payment.booking.id)
                return Response({"message": "Payment verified and completed."})
            else:
                payment.status = "Failed"
                payment.save()
                return Response({"message": f"Payment failed or was not completed."})
        except Payment.DoesNotExist:
            return Response({"error": "Payment record not found."}, status=404)
    else:
        return Response({"error": "Verification failed.", "details": result}, status=400)
