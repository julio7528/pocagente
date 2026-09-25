"""Isolated browser-route checks for the Phase 12.10 Security Dashboard."""

from datetime import date, datetime, UTC

from django.test import Client, TestCase
from django.urls import reverse

from apps.web_portal.accounts.models import User
from apps.web_portal.integrations.audit_dashboard import (
    AuditBreakdownRow,
    AuditBreakdowns,
    AuditDashboardFilters,
    AuditDashboardSnapshot,
    AuditDay,
    AuditEventPage,
    AuditEventRow,
    AuditSummary,
)
from apps.web_portal.integrations import audit_dashboard


PASSWORD = "Test-only-Security-Portal-87!"


def _snapshot(filters: AuditDashboardFilters) -> AuditDashboardSnapshot:
    event = AuditEventRow(
        event_id=18,
        occurred_at="2026-01-02T12:00:00+00:00",
        event_type="PROMPT_INJECTION",
        source_component="<svg onload=alert(1)>",
        user_identifier="audit-user-1",
        resource_category="API_KEY",
        action_taken="BLOCK",
        result="SUCCESS",
        review_status="UNREVIEWED",
    )
    return AuditDashboardSnapshot(
        summary=AuditSummary(
            total_events=1,
            distinct_users=1,
            distinct_event_types=1,
            distinct_source_components=1,
        ),
        timeseries=(AuditDay(date=date(2026, 1, 2), count=1),),
        breakdowns=AuditBreakdowns(
            event_types=(AuditBreakdownRow(value="PROMPT_INJECTION", count=1),),
            source_components=(AuditBreakdownRow(value=event.source_component, count=1),),
            users=(AuditBreakdownRow(value="audit-user-1", count=1),),
        ),
        events=AuditEventPage(page=1, page_size=25, total=1, items=(event,)),
        filters=filters,
    )


class SecurityDashboardBrowserTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="security.admin",
            password=PASSWORD,
            role=User.Role.ADMIN,
        )
        self.client_user = User.objects.create_user(
            username="security.client",
            password=PASSWORD,
            role=User.Role.CLIENT,
        )
        self.support_user = User.objects.create_user(
            username="security.support",
            password=PASSWORD,
            role=User.Role.SUPPORT_AGENT,
        )

    def test_route_matrix_allows_only_active_admin_and_redirects_anonymous(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(reverse("admin-security")).status_code, 302)
        self.assertIn("/login/", anonymous.get(reverse("admin-security")).url)

        for user in (self.client_user, self.support_user):
            client = Client()
            client.force_login(user)
            self.assertEqual(client.get(reverse("admin-security")).status_code, 403)

        admin_client = Client()
        admin_client.force_login(self.admin)
        with self.subTest("overview dashboard"):
            from unittest.mock import patch

            with patch.object(
                audit_dashboard.AuditDashboardClient,
                "snapshot",
                side_effect=lambda filters, **_kwargs: _snapshot(filters),
            ):
                response = admin_client.get(reverse("admin-security"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel de segurança")

    def test_same_origin_data_route_uses_active_admin_and_canonical_filter(self):
        from unittest.mock import patch

        client = Client()
        client.force_login(self.admin)
        observed = []

        def read(filters, **kwargs):
            observed.append((filters, kwargs))
            return _snapshot(filters)

        with patch.object(audit_dashboard.AuditDashboardClient, "snapshot", side_effect=read):
            response = client.get(
                reverse("admin-security-data"),
                {
                    "date_from": "2026-01-01",
                    "date_to": "2026-01-30",
                    "event_type": "PROMPT_INJECTION",
                    "source_component": "router_security_guardrail",
                    "user_identifier": "audit-user-1",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(observed), 1)
        filters, kwargs = observed[0]
        self.assertEqual(filters.event_type, "PROMPT_INJECTION")
        self.assertEqual(filters.source_component, "router_security_guardrail")
        self.assertEqual(filters.user_identifier, "audit-user-1")
        self.assertEqual(kwargs, {"page": 1, "page_size": 25})
        self.assertEqual(response.json()["filters"]["date_from"], "2026-01-01")
        self.assertNotIn("review_note", response.content.decode("utf-8"))

    def test_dashboard_escapes_html_and_is_read_only(self):
        from unittest.mock import patch

        client = Client()
        client.force_login(self.admin)
        with patch.object(
            audit_dashboard.AuditDashboardClient,
            "snapshot",
            side_effect=lambda filters, **_kwargs: _snapshot(filters),
        ):
            response = client.get(reverse("admin-security"))
        body = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "&lt;svg onload=alert(1)&gt;", html=False)
        self.assertNotIn("<svg onload=alert(1)>", body)
        self.assertContains(response, "somente leitura")
        self.assertNotContains(response, "Marcar como revisado")
        self.assertNotContains(response, "review_note")
        self.assertNotContains(response, "AGENT_API_SERVICE_TOKEN")

    def test_inactive_admin_session_no_longer_opens_security_dashboard(self):
        from unittest.mock import patch

        client = Client()
        client.force_login(self.admin)
        self.admin.is_active = False
        self.admin.save(update_fields=("is_active",))
        with patch.object(audit_dashboard.AuditDashboardClient, "snapshot") as snapshot:
            response = client.get(reverse("admin-security"))
        snapshot.assert_not_called()
        self.assertIn(response.status_code, {302, 403})
