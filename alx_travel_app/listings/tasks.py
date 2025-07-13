from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Booking

@shared_task
def send_booking_confirmation_email(booking_id):
    """
    Sends a confirmation email to the user after successful booking.
    """
    try:
        booking = Booking.objects.get(id=booking_id)
        subject = 'Booking Confirmation'
        message = f'Dear {booking.guest.first_name},\n\nYour booking for "{booking.listing.name}" from {booking.start_date} to {booking.end_date} has been confirmed.\n\nThank you for choosing us!'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [booking.guest.email]
        send_mail(subject, message, from_email, recipient_list)
    except Booking.DoesNotExist:
        pass