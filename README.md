## Objective

Configure Celery with RabbitMQ to handle background tasks and implement an email notification feature for bookings.

Instructions

- Duplicate Project:
  - Duplicate the project alx_travel_app_0x02 to alx_travel_app_0x03

- Configure Celery:
  - Set up Celery with RabbitMQ as the message broker.
  - Add Celery configurations in settings.py and create a celery.py file in the project root.

- Define Email Task:
  - In listings/tasks.py, create a shared task function to send a booking confirmation email.
  - Ensure the email task uses the Django email backend configured in settings.py.

- Trigger Email Task:
  - Modify the BookingViewSet to trigger the email task upon booking creation using delay().

- Test Background Task:
  - Test the background task to ensure the email is sent asynchronously when a booking is created.
