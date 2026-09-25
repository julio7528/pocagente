"""Browser input validation for portal-owned client turns."""

from __future__ import annotations

from django import forms


class ClientMessageForm(forms.Form):
    body = forms.CharField(
        label="Mensagem",
        strip=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Escreva sua mensagem…"}),
    )
    client_turn_key = forms.UUIDField(widget=forms.HiddenInput)

    def clean_body(self) -> str:
        body = self.cleaned_data["body"]
        if not body.strip():
            raise forms.ValidationError("Escreva uma mensagem antes de enviar.")
        return body
