from django import forms

from apps.web_portal.accounts.models import PortalUserManager


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Usuário",
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "autofocus": True,
                "spellcheck": "false",
            }
        ),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class PasswordResetRequestForm(forms.Form):
    username = forms.CharField(
        label="Usuário",
        max_length=150,
        strip=True,
        widget=forms.TextInput(
            attrs={"autocomplete": "username", "spellcheck": "false"}
        ),
    )

    def clean_username(self):
        return PortalUserManager.normalize_login(self.cleaned_data["username"])


class PasswordResetRequestConfirmationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        strip=False,
        widget=forms.HiddenInput(),
    )
    confirm_request = forms.BooleanField(
        label="Confirmo que desejo encaminhar a solicitação ao administrador.",
        required=True,
    )

    def clean_username(self):
        return PortalUserManager.normalize_login(self.cleaned_data["username"])
