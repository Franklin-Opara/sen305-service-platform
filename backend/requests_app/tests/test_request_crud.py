from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from requests_app.models import Category, ServiceRequest


class ServiceRequestCrudTests(TestCase):

    def setUp(self):
        User = get_user_model()

        self.owner = User.objects.create_user(
            "owner", password="pass12345"
        )
        self.other = User.objects.create_user(
            "other", password="pass12345"
        )

        self.category = Category.objects.create(name="Facilities")

        self.item = ServiceRequest.objects.create(
            requester=self.owner,
            category=self.category,
            title="Projector does not display",
            description="The projector reports no HDMI signal.",
            location="Room B12",
            priority=3,
        )

    def test_list_requires_login(self):
        response = self.client.get(reverse("requests:list"))
        self.assertEqual(response.status_code, 302)

    def test_owner_can_open_detail(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("requests:detail", args=[self.item.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_other_requester_receives_404(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("requests:detail", args=[self.item.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_valid_post_creates_request(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("requests:create"),
            {
                "category": self.category.id,
                "title": "Laboratory network failure",
                "description": "The network is unavailable.",
                "location": "Laboratory",
                "priority": 1,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ServiceRequest.objects.filter(
                title="Laboratory network failure",
                requester=self.owner,
            ).exists()
        )

    def test_invalid_post_does_not_create_request(self):
        self.client.force_login(self.owner)
        initial_count = ServiceRequest.objects.count()

        response = self.client.post(
            reverse("requests:create"),
            {
                "category": self.category.id,
                "title": "PC",
                "description": "",
                "location": "",
                "priority": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceRequest.objects.count(), initial_count)
        self.assertContains(response, "Use at least 8 characters.")