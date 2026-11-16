
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from requests_app.models import Category, ServiceRequest, WorkOrder


class RequestWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            "workflow_owner", password="pass12345"
        )
        self.other = User.objects.create_user(
            "workflow_other", password="pass12345"
        )
        self.staff = User.objects.create_user(
            "workflow_staff", password="pass12345", is_staff=True
        )
        self.technician = User.objects.create_user(
            "workflow_tech", password="pass12345", is_staff=True
        )

        self.category = Category.objects.create(name="Maintenance")

        self.item = ServiceRequest.objects.create(
            requester=self.owner,
            category=self.category,
            title="Faulty classroom projector",
            description="The projector is not displaying.",
            location="Room A1",
            priority=2,
        )

    def test_nonstaff_cannot_assign(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("requests:assign", args=[self.item.id]),
            {"technician": self.technician.id},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            WorkOrder.objects.filter(service_request=self.item).exists()
        )

    def test_staff_can_assign_technician(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("requests:assign", args=[self.item.id]),
            {"technician": self.technician.id},
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()

        self.assertEqual(self.item.status, ServiceRequest.Status.ASSIGNED)
        self.assertEqual(
            self.item.work_order.technician, self.technician
        )

    def test_cannot_resolve_without_assignment(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("requests:resolve", args=[self.item.id]),
            {"work_notes": "The projector has been repaired."},
        )

        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()

        self.assertEqual(self.item.status, ServiceRequest.Status.OPEN)
        self.assertIsNone(self.item.resolved_at)
        self.assertFalse(
            WorkOrder.objects.filter(service_request=self.item).exists()
        )

    def test_assigned_technician_can_resolve(self):
        WorkOrder.objects.create(
            service_request=self.item,
            technician=self.technician,
        )
        self.item.status = ServiceRequest.Status.ASSIGNED
        self.item.save()

        self.client.force_login(self.technician)

        response = self.client.post(
            reverse("requests:resolve", args=[self.item.id]),
            {"work_notes": "Replaced the faulty projector cable."},
        )

        self.assertEqual(response.status_code, 302)

        self.item.refresh_from_db()
        self.item.work_order.refresh_from_db()

        self.assertEqual(self.item.status, ServiceRequest.Status.RESOLVED)
        self.assertIsNotNone(self.item.resolved_at)
        self.assertEqual(
            self.item.resolution_summary,
            "Replaced the faulty projector cable.",
        )
        self.assertEqual(
            self.item.work_order.work_notes,
            "Replaced the faulty projector cable.",
        )
        self.assertIsNotNone(self.item.work_order.completed_at)

    def test_filtered_pagination_preserves_filters(self):
        for number in range(12):
            ServiceRequest.objects.create(
                requester=self.owner,
                category=self.category,
                title=f"Network problem {number}",
                description="Network connection failure.",
                location="Computer laboratory",
                priority=2,
            )

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("requests:list"),
            {"q": "Network", "status": "open", "page": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertIn("q=Network", response.context["query_params"])
        self.assertIn("status=open", response.context["query_params"])
