from django import forms

from apps.web_portal.support.models import PasswordResetRequest


class PasswordResetRequestFilterForm(forms.Form):
    status = forms.ChoiceField(
        label="Situação",
        required=False,
        choices=(
            ("", "Todas"),
            (PasswordResetRequest.Status.OPEN, "Em aberto"),
            (PasswordResetRequest.Status.RESOLVED, "Resolvida"),
            (PasswordResetRequest.Status.REJECTED, "Rejeitada"),
        ),
        initial=PasswordResetRequest.Status.OPEN,
    )
    query = forms.CharField(
        label="Usuário solicitante",
        required=False,
        max_length=150,
        strip=True,
    )


class PasswordResetResolveForm(forms.Form):
    new_password = forms.CharField(
        label="Nova senha",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
    )
    confirm_password = forms.CharField(
        label="Confirme a nova senha",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
    )
    confirm_resolution = forms.BooleanField(
        label="Confirmo que esta senha será comunicada ao usuário pelo canal interno aprovado.",
        required=True,
    )

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get("new_password")
        confirmation = cleaned.get("confirm_password")
        if new_password is not None and confirmation is not None and new_password != confirmation:
            self.add_error("confirm_password", "As senhas não coincidem.")
        return cleaned


class PasswordResetRejectForm(forms.Form):
    confirm_rejection = forms.BooleanField(
        label="Confirmo que desejo rejeitar esta solicitação.",
        required=True,
    )
