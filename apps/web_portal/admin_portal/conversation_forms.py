from __future__ import annotations

from datetime import timedelta

from django import forms

from apps.web_portal.conversations.models import Conversation


class ConversationAdminFiltersForm(forms.Form):
    query = forms.CharField(
        label="Título ou titular",
        required=False,
        max_length=100,
        strip=True,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    owner_username = forms.CharField(
        label="Titular",
        required=False,
        max_length=150,
        strip=True,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    status = forms.ChoiceField(
        label="Estado",
        required=False,
        choices=(
            ("", "Todos os estados"),
            (Conversation.Status.ACTIVE, "Ativa"),
            (Conversation.Status.WAITING_HUMAN, "Aguardando atendimento"),
            (Conversation.Status.HUMAN, "Atendimento humano"),
            (Conversation.Status.CLOSED, "Finalizada"),
            (Conversation.Status.BLOCKED, "Bloqueada"),
            (Conversation.Status.DELETED, "Apagada"),
        ),
    )
    date_from = forms.DateField(
        label="Criada a partir de",
        required=False,
        input_formats=("%Y-%m-%d",),
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    date_to = forms.DateField(
        label="Criada até",
        required=False,
        input_formats=("%Y-%m-%d",),
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if bool(date_from) != bool(date_to):
            self.add_error(None, "Informe as duas datas para aplicar o período.")
        elif date_from and date_to:
            if date_from > date_to:
                self.add_error("date_to", "A data final deve ser igual ou posterior à inicial.")
            elif date_to - date_from > timedelta(days=365):
                self.add_error("date_to", "O período máximo permitido é de 365 dias.")
        return cleaned


class ConversationConfirmationForm(forms.Form):
    confirm = forms.BooleanField(
        label="Confirmo esta alteração",
        required=True,
    )
