from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Booking, Motorcycle, Shop


class BookingSetup:
    def setUp(self):
        users = get_user_model()
        self.customer = users.objects.create_user(username="customer")
        self.other = users.objects.create_user(username="other")
        self.mechanic = users.objects.create_user(username="mechanic")
        self.mechanic2 = users.objects.create_user(username="mechanic2")
        group = Group.objects.create(name="mechanics")
        self.mechanic.groups.add(group)
        self.mechanic2.groups.add(group)
        self.shop = Shop.objects.create(name="Shop A", address="Bangkok", phone="contact")
        self.shop.mechanics.add(self.mechanic, self.mechanic2)
        self.bike = Motorcycle.objects.create(owner=self.customer, brand="Honda", model="PCX", license_plate="TEST", year=2024)
        self.api = self.client_for(self.customer)
        self.payload = {"motorcycle": self.bike.pk, "problem": "เครื่องสตาร์ตยาก", "appointment_at": (timezone.now() + timedelta(days=1)).isoformat()}
        self.payload["shop"] = self.shop.pk

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def create(self):
        response = self.api.post("/api/bookings/", self.payload)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def transition(self, user, pk, action, **extra):
        return self.client_for(user).post(f"/api/bookings/{pk}/transition/", {"action": action, **extra})


class BookingTests(BookingSetup, TestCase):
    def test_complete_workflow_and_history(self):
        pk = self.create()
        for command, status in [("accept", "accepted"), ("start", "in_progress"), ("complete", "completed")]:
            response = self.transition(self.mechanic, pk, command, repair_notes="เปลี่ยนหัวเทียน")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["status"], status)
        detail = self.api.get(f"/api/bookings/{pk}/").data
        self.assertEqual(len(detail["events"]), 4)
        self.assertEqual(detail["repair_notes"], "เปลี่ยนหัวเทียน")
        self.assertEqual(detail["mechanic_name"], "mechanic")

    def test_cannot_book_other_users_motorcycle(self):
        self.assertEqual(self.client_for(self.other).post("/api/bookings/", self.payload).status_code, 400)

    def test_past_time_and_blank_problem_rejected(self):
        self.assertEqual(self.api.post("/api/bookings/", {**self.payload, "problem": " "}).status_code, 400)
        self.assertEqual(self.api.post("/api/bookings/", {**self.payload, "appointment_at": timezone.now().isoformat()}).status_code, 400)

    def test_duplicate_active_booking_then_rebook_after_cancel(self):
        pk = self.create()
        self.assertEqual(self.api.post("/api/bookings/", self.payload).status_code, 409)
        self.assertEqual(self.transition(self.customer, pk, "cancel").status_code, 200)
        self.create()

    def test_customer_cannot_assign_or_skip_status(self):
        response = self.api.post("/api/bookings/", {**self.payload, "status": "completed", "mechanic": self.mechanic.pk})
        self.assertEqual(response.data["status"], "pending")
        self.assertIsNone(response.data["mechanic_name"])
        self.assertEqual(self.transition(self.customer, response.data["id"], "accept").status_code, 403)
        self.assertEqual(self.api.patch(f"/api/bookings/{response.data['id']}/", {"status": "completed"}).status_code, 405)

    def test_other_customer_cannot_read_or_cancel(self):
        pk = self.create()
        other = self.client_for(self.other)
        self.assertEqual(other.get("/api/bookings/").data["count"], 0)
        self.assertEqual(other.get(f"/api/bookings/{pk}/").status_code, 404)
        self.assertEqual(self.transition(self.other, pk, "cancel").status_code, 404)

    def test_only_assigned_mechanic_can_progress_and_cannot_skip(self):
        pk = self.create()
        self.transition(self.mechanic, pk, "accept")
        self.assertEqual(self.transition(self.mechanic2, pk, "accept").status_code, 409)
        self.assertEqual(self.transition(self.mechanic2, pk, "start").status_code, 403)
        self.assertEqual(self.transition(self.mechanic, pk, "complete", repair_notes="done").status_code, 409)
        self.assertEqual(self.client_for(self.mechanic2).get(f"/api/bookings/{pk}/").status_code, 200)

    def test_cannot_cancel_started_job_or_complete_without_notes(self):
        pk = self.create()
        self.transition(self.mechanic, pk, "accept")
        self.transition(self.mechanic, pk, "start")
        self.assertEqual(self.transition(self.customer, pk, "cancel").status_code, 409)
        self.assertEqual(self.transition(self.mechanic, pk, "complete").status_code, 400)

    def test_motorcycle_history_is_protected_and_snapshot_preserved(self):
        pk = self.create()
        self.assertEqual(self.api.delete(f"/api/motorcycles/{self.bike.pk}/").status_code, 400)
        self.api.patch(f"/api/motorcycles/{self.bike.pk}/", {"model": "New"})
        self.assertIn("PCX", self.api.get(f"/api/bookings/{pk}/").data["motorcycle_label"])

    def test_role_is_server_controlled(self):
        self.assertEqual(self.api.get("/api/me/").data["role"], "customer")
        self.assertEqual(self.client_for(self.mechanic).get("/api/me/").data["role"], "mechanic")
        self.assertEqual(APIClient().get("/api/bookings/").status_code, 401)


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class ConcurrentAcceptanceTests(BookingSetup, TransactionTestCase):
    def test_two_mechanics_only_one_accepts(self):
        pk = self.create()
        barrier = Barrier(2)
        def accept(user_id):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=user_id)
                barrier.wait(timeout=5)
                return self.transition(user, pk, "accept").status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(accept, [self.mechanic.pk, self.mechanic2.pk]))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(Booking.objects.get(pk=pk).events.filter(status="accepted").count(), 1)
