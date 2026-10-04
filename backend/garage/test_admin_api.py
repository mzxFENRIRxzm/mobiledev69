from unittest.mock import MagicMock, patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from oidc_provider.models import Client as OidcClient, Token as OidcToken

from .models import (AdminAuditEvent, AiConversation, AiEmbeddingCredential, Booking, BookingEvent,
                     KnowledgeChunk, Motorcycle, MotorcycleKnowledge, Notification,
                     Shop, ShopConversation, ShopMessage, UserProfile)


class AdminApiTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_superuser(username="admin_api", password="test-password-123")
        self.customer = users.objects.create_user(username="customer_api", password="test-password-123")
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_only_admin_can_read_and_modify(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/admin/overview/").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/database/").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/ai-vectors/").status_code, 403)
        self.assertEqual(self.client.patch(
            "/api/admin/ai-vectors/00000000-0000-0000-0000-000000000001/",
            {"content": "Changed"}, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/database/auth_user/").status_code, 403)
        self.assertEqual(self.client.post(
            "/api/admin/database/garage_notification/1/action/",
            {"action": "hide", "reason": "No access"}, format="json").status_code, 403)
        self.assertEqual(self.client.post("/api/admin/knowledge/", {
            "brand": "Honda", "model": "CB", "section": "Engine",
            "content": "Test fact", "source_url": "https://example.test/spec",
        }).status_code, 403)
        self.assertEqual(self.client.put("/api/admin/embedding-key/", {
            "api_key": "test-api-key-without-live-secret",
        }).status_code, 403)

    @patch("garage.admin_vectors.vector_connection")
    def test_vector_list_is_paginated_and_searchable(self, connect):
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (95,)
        cursor.fetchall.return_value = [(
            "00000000-0000-0000-0000-000000000001", "Honda engine specification",
            {"model": "GB350C", "source_url": "https://example.test/spec"})]
        response = self.client.get("/api/admin/ai-vectors/?page=2&q=Honda")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 95)
        self.assertEqual(response.data["page"], 2)
        self.assertEqual(response.data["results"][0]["metadata"]["model"], "GB350C")
        self.assertEqual(cursor.execute.call_args_list[-1].args[1][-1], 20)
        self.assertEqual(self.client.get("/api/admin/ai-vectors/?page=0").status_code, 400)

    @patch("garage.admin_vectors.vector_connection")
    @patch("garage.admin_vectors.embed_content")
    @patch("garage.admin_vectors.embedding_key", return_value="test-key")
    def test_vector_edit_reembeds_and_delete_archives(self, key, embed, connect):
        embed.return_value = [0.1] * 3072
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        vector_id = "00000000-0000-0000-0000-000000000001"
        cursor.fetchone.return_value = (vector_id, "old Honda fact", {
            "model": "GB350C", "title": "Honda GB350C", "section": "Engine",
            "source_url": "https://example.test/spec"})
        edited = self.client.patch(f"/api/admin/ai-vectors/{vector_id}/", {
            "content": "corrected Honda fact"}, format="json")
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.data["metadata"]["review_level"], "admin_reviewed")
        embed.assert_called_once_with("test-key", "corrected Honda fact")
        removed = self.client.delete(f"/api/admin/ai-vectors/{vector_id}/",
            {"reason": "Obsolete information"}, format="json")
        self.assertEqual(removed.status_code, 200)
        self.assertTrue(removed.data["deleted"])
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("the_x_manual_vector_history" in sql for sql in statements))
        self.assertTrue(any("DELETE FROM the_x_manual_vectors" in sql for sql in statements))
        self.assertEqual(AdminAuditEvent.objects.filter(target_type="ai_vector").count(), 2)

    def test_role_change_and_last_admin_guard(self):
        response = self.client.patch(f"/api/admin/users/{self.customer.pk}/",
                                     {"role": "mechanic"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(response.data["role"], "mechanic")
        self.assertTrue(self.customer.groups.filter(name="mechanics").exists())
        response = self.client.patch(f"/api/admin/users/{self.admin.pk}/",
                                     {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_shop_membership_requires_mechanic_and_preserves_active_job(self):
        shop = Shop.objects.create(name="Service", address="Road", phone="01234")
        self.assertEqual(self.client.patch(f"/api/admin/shops/{shop.pk}/",
            {"mechanic_ids": [self.customer.pk]}, format="json").status_code, 400)
        self.client.patch(f"/api/admin/users/{self.customer.pk}/",
                          {"role": "mechanic"}, format="json")
        self.assertEqual(self.client.patch(f"/api/admin/shops/{shop.pk}/",
            {"mechanic_ids": [self.customer.pk]}, format="json").status_code, 200)
        self.assertTrue(shop.mechanics.filter(pk=self.customer.pk).exists())
        owner = get_user_model().objects.create_user(username="bike_owner")
        bike = Motorcycle.objects.create(owner=owner, brand="Honda", model="CB",
                                          license_plate="TEST", year=2026)
        Booking.objects.create(customer=owner, shop=shop, motorcycle=bike,
            mechanic=self.customer, motorcycle_label="Honda CB", problem="Test",
            appointment_at=timezone.now() + timedelta(days=1), status="accepted")
        self.assertEqual(self.client.patch(f"/api/admin/shops/{shop.pk}/",
            {"mechanic_ids": []}, format="json").status_code, 400)
        self.assertTrue(shop.mechanics.filter(pk=self.customer.pk).exists())

    def test_admin_edits_customer_profile_and_garage(self):
        bike = Motorcycle.objects.create(owner=self.customer, brand="Honda", model="CB",
            license_plate="OLD", year=2024)
        response = self.client.patch(f"/api/admin/users/{self.customer.pk}/", {
            "first_name": "Test", "last_name": "Customer", "email": "test@example.com",
            "phone": "0812345678", "role": "customer"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Test")
        self.assertEqual(UserProfile.objects.get(user=self.customer).phone, "0812345678")
        response = self.client.patch(
            f"/api/admin/users/{self.customer.pk}/motorcycles/{bike.pk}/",
            {"model": "CBR", "license_plate": "NEW", "mileage": 1234}, format="json")
        self.assertEqual(response.status_code, 200)
        bike.refresh_from_db()
        self.assertEqual((bike.model, bike.license_plate, bike.mileage), ("CBR", "NEW", 1234))
        self.assertEqual(self.client.patch(
            f"/api/admin/users/{self.customer.pk}/motorcycles/{bike.pk}/",
            {"year": 1800}, format="json").status_code, 400)

    def test_shop_suspension_expiry_and_soft_delete_preserve_history(self):
        shop = Shop.objects.create(name="Service", address="Old Road", phone="01234")
        bike = Motorcycle.objects.create(owner=self.customer, brand="Honda", model="CB",
            license_plate="HIST", year=2024)
        booking = Booking.objects.create(customer=self.customer, shop=shop, motorcycle=bike,
            motorcycle_label="Honda CB", problem="Repair", appointment_at=timezone.now() + timedelta(days=1))
        room = ShopConversation.objects.create(shop=shop, customer=self.customer)
        message = ShopMessage.objects.create(conversation=room, sender=self.customer, body="Hello")
        details = self.client.patch(f"/api/admin/shops/{shop.pk}/details/",
            {"name": "Updated Service", "address": "New Road",
             "latitude": "13.756300", "longitude": "100.501800"}, format="json")
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.data["name"], "Updated Service")
        until = timezone.now() + timedelta(days=1)
        response = self.client.post(f"/api/admin/shops/{shop.pk}/moderate/",
            {"action": "suspend", "reason": "Review", "suspended_until": until.isoformat()}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["available"])
        self.client.force_authenticate(self.customer)
        self.assertFalse(any(row["id"] == shop.pk for row in self.client.get("/api/shops/").data["results"]))
        self.assertEqual(self.client.get(f"/api/bookings/{booking.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/conversations/{room.pk}/messages/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/conversations/{room.pk}/messages/",
            {"body": "Blocked"}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        Shop.objects.filter(pk=shop.pk).update(suspended_until=timezone.now() - timedelta(minutes=1))
        self.client.force_authenticate(self.customer)
        self.assertTrue(any(row["id"] == shop.pk for row in self.client.get("/api/shops/").data["results"]))
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"/api/admin/shops/{shop.pk}/moderate/",
            {"action": "delete", "reason": "Permanent removal"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["available"])
        self.assertEqual(self.client.patch(f"/api/admin/shops/{shop.pk}/details/",
            {"name": "Changed"}, format="json").status_code, 400)
        self.assertEqual(Booking.objects.get(pk=booking.pk).shop_id, shop.pk)
        self.assertEqual(ShopMessage.objects.get(pk=message.pk).body, "Hello")
        self.client.force_authenticate(self.customer)
        self.assertFalse(any(row["id"] == shop.pk for row in self.client.get("/api/shops/").data["results"]))
        self.assertEqual(self.client.get(f"/api/bookings/{booking.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/conversations/{room.pk}/messages/").status_code, 200)

    def test_key_is_encrypted_and_never_returned(self):
        key = "test-api-key-without-live-secret"
        response = self.client.put("/api/admin/embedding-key/", {"api_key": key}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(key, str(response.data))
        self.assertNotIn(key, AiEmbeddingCredential.objects.get().encrypted_key)
        self.assertTrue(response.data["configured"])
        self.assertEqual(response.data["hint"], key[-4:])
        self.assertNotIn(key, str(self.client.get("/api/admin/overview/").data))

    def test_database_catalog_redacts_credentials_and_limits_tables(self):
        catalog = self.client.get("/api/admin/database/")
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(any(row["table"] == "auth_user" for row in catalog.data))
        rows = self.client.get("/api/admin/database/auth_user/")
        self.assertEqual(rows.status_code, 200)
        self.assertEqual(rows.data["page"], 1)
        self.assertTrue(all(row["password"] == "[redacted]" for row in rows.data["rows"]))
        self.assertEqual(self.client.get("/api/admin/database/not_a_table/").status_code, 400)
        self.assertEqual(self.client.get("/api/admin/database/auth_user/?page=-1").status_code, 400)
        self.assertEqual(self.client.post("/api/admin/database/auth_user/1/action/",
            {"action": "hide", "reason": "invalid"}, format="json").status_code, 400)
        oidc = OidcClient.objects.create(client_id="test-public", client_type="public")
        token = OidcToken.objects.create(user=self.customer, client=oidc,
            access_token="test-access-token", refresh_token="test-refresh-token",
            expires_at=timezone.now() + timedelta(hours=1), _scope="openid")
        listed = self.client.get("/api/admin/database/oidc_provider_token/")
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn("test-access-token", str(listed.data))
        self.assertNotIn("test-refresh-token", str(listed.data))
        self.assertEqual(self.client.post(
            f"/api/admin/database/oidc_provider_token/{token.pk}/action/",
            {"action": "revoke", "reason": "Account review"}, format="json").status_code, 200)
        self.assertFalse(OidcToken.objects.filter(pk=token.pk).exists())

    def test_database_actions_hide_domain_records_without_deleting_history(self):
        shop = Shop.objects.create(name="Service", address="Road", phone="01234")
        bike = Motorcycle.objects.create(owner=self.customer, brand="Honda", model="CB",
            license_plate="KEEP", year=2024)
        room = ShopConversation.objects.create(shop=shop, customer=self.customer)
        message = ShopMessage.objects.create(conversation=room, sender=self.customer,
            body="Private message")
        notice = Notification.objects.create(recipient=self.customer,
            conversation=room, message=message, title="Message")
        ai_room = AiConversation.objects.create(owner=self.customer, title="Motorcycle")
        chunk = KnowledgeChunk.objects.create(title="Manual", source_url="https://example.test",
            locator="p1", keywords=["engine"], content="Text", is_active=True)
        root = "/api/admin/database"
        self.assertEqual(self.client.post(f"{root}/garage_shopmessage/{message.pk}/action/",
            {"action": "redact", "reason": "Privacy"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{root}/garage_notification/{notice.pk}/action/",
            {"action": "hide", "reason": "Privacy"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{root}/garage_shopconversation/{room.pk}/action/",
            {"action": "archive", "reason": "Privacy"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{root}/garage_aiconversation/{ai_room.pk}/action/",
            {"action": "archive", "reason": "Privacy"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{root}/garage_knowledgechunk/{chunk.pk}/action/",
            {"action": "disable", "reason": "Outdated"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"{root}/garage_knowledgechunk/{chunk.pk}/",
            {"content": "Corrected text"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"{root}/garage_aiconversation/{ai_room.pk}/",
            {"title": "Updated title"}, format="json").status_code, 200)
        self.assertEqual(self.client.post(
            f"/api/admin/users/{self.customer.pk}/motorcycles/{bike.pk}/archive/",
            {"action": "archive", "reason": "Duplicate"}, format="json").status_code, 200)
        self.assertEqual(ShopMessage.objects.get(pk=message.pk).body, "Private message")
        self.assertFalse(KnowledgeChunk.objects.get(pk=chunk.pk).is_active)
        self.assertEqual(AiConversation.objects.get(pk=ai_room.pk).title, "Updated title")
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get("/api/motorcycles/").data["count"], 0)
        self.assertEqual(self.client.get("/api/conversations/").data, [])
        self.assertEqual(self.client.get("/api/ai-conversations/").data, [])
        self.assertEqual(self.client.get("/api/notifications/").data["unread_count"], 0)
        self.client.force_authenticate(self.admin)
        self.assertEqual(ShopMessage.objects.get(pk=message.pk).body, "Private message")
        self.assertTrue(self.client.get(f"{root}/garage_shopmessage/").data["rows"])

    def test_redacted_message_is_masked_in_existing_chat(self):
        shop = Shop.objects.create(name="Service", address="Road", phone="01234")
        room = ShopConversation.objects.create(shop=shop, customer=self.customer)
        message = ShopMessage.objects.create(conversation=room, sender=self.customer,
            body="Private message")
        response = self.client.post(
            f"/api/admin/database/garage_shopmessage/{message.pk}/action/",
            {"action": "redact", "reason": "Privacy"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.customer)
        history = self.client.get(f"/api/conversations/{room.pk}/messages/")
        self.assertEqual(history.status_code, 200)
        self.assertNotIn("Private message", str(history.data))
        inbox = self.client.get("/api/conversations/")
        self.assertNotIn("Private message", str(inbox.data))

    def test_booking_detail_correction_cancel_and_archive_preserve_events(self):
        shop = Shop.objects.create(name="Service", address="Road", phone="01234")
        bike = Motorcycle.objects.create(owner=self.customer, brand="Honda", model="CB",
            license_plate="BOOK", year=2024)
        booking = Booking.objects.create(customer=self.customer, shop=shop,
            motorcycle=bike, motorcycle_label="Honda CB", problem="Old problem",
            appointment_at=timezone.now() + timedelta(days=1))
        self.assertEqual(self.client.post(
            f"/api/admin/users/{self.customer.pk}/motorcycles/{bike.pk}/archive/",
            {"action": "archive", "reason": "Too early"}, format="json").status_code, 400)
        detail_url = f"/api/admin/bookings/{booking.pk}/"
        detail = self.client.get(detail_url)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["motorcycle"]["license_plate"], "BOOK")
        self.assertEqual(detail.data["customer"]["username"], self.customer.username)
        self.assertEqual(self.client.patch(detail_url, {"problem": "Corrected problem"},
            format="json").status_code, 200)
        self.assertEqual(self.client.post(f"{detail_url}action/",
            {"action": "archive", "reason": "Too early"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(f"{detail_url}action/",
            {"action": "cancel", "reason": "Customer request"}, format="json").status_code, 200)
        self.assertEqual(BookingEvent.objects.filter(booking=booking,
            status=Booking.Status.CANCELLED).count(), 1)
        self.assertEqual(self.client.post(f"{detail_url}action/",
            {"action": "archive", "reason": "Admin cleanup"}, format="json").status_code, 200)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.archived_at)
        self.assertEqual(booking.problem, "Corrected problem")
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get(f"/api/bookings/{booking.pk}/").status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_reviewed_knowledge_requires_embedding_key(self):
        created = self.client.post("/api/admin/knowledge/", {
            "brand": "Honda", "model": "CB", "section": "Engine",
            "content": "Test specification", "source_url": "https://example.test/spec",
            "reviewed": True,
        }, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.post(
            f"/api/admin/knowledge/{created.data['id']}/embed/").status_code, 503)

    def test_admin_knowledge_lists_all_pages(self):
        MotorcycleKnowledge.objects.bulk_create([
            MotorcycleKnowledge(brand="Honda", model=f"Model {index}",
                section="Engine", content="Reviewed specification",
                source_url="https://example.test/spec")
            for index in range(21)
        ])
        first = self.client.get("/api/admin/knowledge/")
        second = self.client.get("/api/admin/knowledge/?page=2")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["count"], 21)
        self.assertEqual(len(first.data["results"]), 20)
        self.assertTrue(first.data["has_more"])
        self.assertEqual(len(second.data["results"]), 1)
        self.assertFalse(second.data["has_more"])

    @patch("garage.admin_api.vector_connection")
    def test_admin_knowledge_archive_hides_row_and_removes_embedding(self, connect):
        row = MotorcycleKnowledge.objects.create(brand="Honda", model="CB",
            section="Engine", content="Old fact", source_url="https://example.test/spec",
            reviewed=True, embedding_status="ready")
        response = self.client.delete(f"/api/admin/knowledge/{row.pk}/",
            {"reason": "Incorrect specification"}, format="json")
        self.assertEqual(response.status_code, 200)
        row.refresh_from_db()
        self.assertIsNotNone(row.archived_at)
        self.assertEqual(self.client.get("/api/admin/knowledge/").data["count"], 0)
        self.assertEqual(self.client.post(f"/api/admin/knowledge/{row.pk}/embed/").status_code, 404)
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        self.assertTrue(any("DELETE FROM the_x_manual_vectors" in call.args[0]
                            for call in cursor.execute.call_args_list))

    @patch("garage.admin_api.vector_connection")
    @patch("garage.admin_api.embed_content")
    def test_reviewed_knowledge_embeds_and_edit_removes_stale_vector(self, embed, connect):
        embed.return_value = [0.1] * 3072
        connection = MagicMock()
        connect.return_value.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = MagicMock()
        created = self.client.post("/api/admin/knowledge/", {
            "brand": "Honda", "model": "CB", "year": 2026,
            "section": "Engine", "content": "Test specification",
            "source_url": "https://example.test/spec", "reviewed": False,
        }, format="json")
        self.assertEqual(created.status_code, 201)
        pk = created.data["id"]
        self.assertEqual(self.client.post(f"/api/admin/knowledge/{pk}/embed/").status_code, 400)
        self.client.put("/api/admin/embedding-key/",
                        {"api_key": "test-api-key-without-live-secret"}, format="json")
        self.assertEqual(self.client.patch(f"/api/admin/knowledge/{pk}/",
                                           {"reviewed": True}, format="json").status_code, 200)
        response = self.client.post(f"/api/admin/knowledge/{pk}/embed/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["embedding_status"], "ready")
        self.assertEqual(self.client.post(f"/api/admin/knowledge/{pk}/embed/").status_code, 200)
        self.assertEqual(embed.call_count, 1)
        self.assertEqual(self.client.patch(f"/api/admin/knowledge/{pk}/",
            {"content": "Corrected specification"}, format="json").status_code, 200)
        self.assertEqual(MotorcycleKnowledge.objects.get(pk=pk).embedding_status, "pending")
        statements = [call.args[0] for call in
                      connection.cursor.return_value.__enter__.return_value.execute.call_args_list]
        self.assertTrue(any("DELETE FROM the_x_manual_vectors" in sql for sql in statements))
