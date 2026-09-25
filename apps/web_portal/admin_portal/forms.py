from django import forms

from apps.web_portal.accounts.models import PortalUserManager, User


class UserCreateForm(forms.Form):
    username = forms.CharField(
        label="Nome de usuário",
        max_length=150,
        strip=True,
        widget=forms.TextInput(attrs={"autocomplete": "username"}),
    )
    role = forms.ChoiceField(label="Perfil", choices=User.Role.choices)
    is_active = forms.BooleanField(label="Conta ativa", required=False, initial=True)
    password = forms.CharField(
        label="Senha inicial",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
    )
    password_confirmation = forms.CharField(
        label="Confirme a senha",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
    )

    def clean_username(self):
        return PortalUserManager.normalize_login(self.cleaned_data["username"])

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirmation = cleaned.get("password_confirmation")
        if password is not None and confirmation is not None and password != confirmation:
            self.add_error("password_confirmation", "As senhas não coincidem.")
        return cleaned


class RoleChangeForm(forms.Form):
    role = forms.ChoiceField(label="Perfil", choices=User.Role.choices)


class AdminSetPasswordForm(forms.Form):
    new_password = forms.CharField(
        label="Nova senha",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
    )
    password_confirmation = forms.CharField(
        label="Confirme a nova senha",
        strip=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"autocomplete": "new-password"},
        ),
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("new_password")
        confirmation = cleaned.get("password_confirmation")
        if password is not None and confirmation is not None and password != confirmation:
            self.add_error("password_confirmation", "As senhas não coincidem.")
        return cleaned
