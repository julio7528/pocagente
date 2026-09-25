"""Validated, bounded filter controls for the Security Dashboard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from django import forms

from apps.web_portal.integrations.audit_dashboard import AuditDashboardFilters


APPROVED_SECURITY_EVENT_TYPES = (
    ("CREDENTIAL_REQUEST", "CREDENTIAL_REQUEST"),
    ("SECRET_REQUEST", "SECRET_REQUEST"),
    ("DATABASE_ACCESS_REQUEST", "DATABASE_ACCESS_REQUEST"),
    ("SENSITIVE_INFRASTRUCTURE_REQUEST", "SENSITIVE_INFRASTRUCTURE_REQUEST"),
    ("PROMPT_INJECTION", "PROMPT_INJECTION"),
    ("AUTHORIZATION_BYPASS_ATTEMPT", "AUTHORIZATION_BYPASS_ATTEMPT"),
    ("SECURITY_POLICY_PROBE", "SECURITY_POLICY_PROBE"),
)
APPROVED_SECURITY_EVENT_TYPE_VALUES = frozenset(value for value, _ in APPROVED_SECURITY_EVENT_TYPES)


class SecurityDashboardFilterForm(forms.Form):
    date_from = forms.DateField(
        label="Data inicial",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Data final",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    event_type = forms.ChoiceField(
        label="Tipo de evento",
        choices=(("", "Todos os tipos"), *APPROVED_SECURITY_EVENT_TYPES),
        required=False,
    )
    source_component = forms.CharField(
        label="Componente de origem",
        required=False,
        strip=False,
        max_length=128,
        widget=forms.TextInput(attrs={"list": "audit-sources", "autocomplete": "off"}),
    )
    user_identifier = forms.CharField(
        label="Identificador registrado",
        required=False,
        strip=False,
        max_length=128,
        widget=forms.TextInput(attrs={"list": "audit-users", "autocomplete": "off"}),
    )
    page = forms.IntegerField(label="Página", required=False, min_value=1, max_value=1000, initial=1)

    def __init__(self, data=None, *, today: date | None = None, **kwargs):
        self._today = today or datetime.now(UTC).date()
        super().__init__(data, **kwargs)
        self.fields["date_to"].initial = self._today
        self.fields["date_from"].initial = self._today - timedelta(days=29)
        if not self.is_bound:
            self.initial.setdefault("date_to", self._today)
            self.initial.setdefault("date_from", self._today - timedelta(days=29))

    def clean_source_component(self) -> str:
        raw_value = self.cleaned_data["source_component"]
        value = raw_value.strip()
        if raw_value and not value:
            raise forms.ValidationError("Informe um componente de origem válido.")
        return value

    def clean_user_identifier(self) -> str:
        raw_value = self.cleaned_data["user_identifier"]
        value = raw_value.strip()
        if raw_value and not value:
            raise forms.ValidationError("Informe um identificador válido.")
        return value

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        today = self._today
        end = cleaned.get("date_to") or today
        start = cleaned.get("date_from") or (end - timedelta(days=29))
        if start > end:
            self.add_error("date_to", "A data final deve ser igual ou posterior à data inicial.")
        elif (end - start).days + 1 > 90:
            self.add_error(None, "O período máximo permitido é de 90 dias.")
        else:
            cleaned["date_from"] = start
            cleaned["date_to"] = end
            cleaned["page"] = cleaned.get("page") or 1
        return cleaned

    def dashboard_filters(self) -> AuditDashboardFilters:
        if not self.is_valid():
            raise ValueError("Dashboard filters are invalid")
        cleaned = self.cleaned_data
        return AuditDashboardFilters(
            date_from=cleaned["date_from"],
            date_to=cleaned["date_to"],
            event_type=cleaned.get("event_type", ""),
            source_component=cleaned.get("source_component", ""),
            user_identifier=cleaned.get("user_identifier", ""),
        )

    @property
    def page_number(self) -> int:
        if not self.is_valid():
            return 1
        return self.cleaned_data.get("page", 1)
