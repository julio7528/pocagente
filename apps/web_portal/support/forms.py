from django import forms


class SupportMessageForm(forms.Form):
    support_turn_key = forms.UUIDField(widget=forms.HiddenInput)
    body = forms.CharField(
        label="Mensagem para o cliente",
        max_length=4000,
        strip=False,
        widget=forms.Textarea(attrs={"rows": 4, "autocomplete": "off"}),
    )


class FinalizeHandoffForm(forms.Form):
    confirm_finalization = forms.BooleanField(
        label="Entendo que esta conversa ficará somente para leitura.",
        required=True,
    )
