from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Trim


class ApplicationRole(models.TextChoices):
    ADMIN = "ADMIN", "Admin"
    CLIENT = "CLIENT", "Client"
    SUPPORT_AGENT = "SUPPORT_AGENT", "Support agent"


ROLE_VALUES = tuple(ApplicationRole.values)


class PortalUserQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError("User identities are deactivated, not physically deleted.")


class PortalUserManager(UserManager.from_queryset(PortalUserQuerySet)):
    """Create users with a deterministic canonical login."""

    @staticmethod
    def normalize_login(username: str) -> str:
        return username.strip().lower()

    def get_by_natural_key(self, username):
        return self.get(username=self.normalize_login(username))

    def _create_user(self, username, email=None, password=None, **extra_fields):
        if not username or not username.strip():
            raise ValueError("A non-empty username is required.")
        role = extra_fields.get("role")
        if role not in ROLE_VALUES:
            raise ValueError("An approved application role is required.")
        username = self.normalize_login(username)
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        raise ValueError("Use the protected bootstrap_admin command or ADMIN service.")


class User(AbstractUser):
    Role = ApplicationRole

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, unique=True)
    role = models.CharField(max_length=20, choices=ApplicationRole.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PortalUserManager()
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["role"]

    class Meta:
        db_table = "users"
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("username")),
                name="uq_portal_users__username_normalized",
            ),
            models.CheckConstraint(
                condition=Q(username=Lower(Trim("username"))) & ~Q(username=""),
                name="ck_portal_users__username_normalized",
            ),
            models.CheckConstraint(
                condition=Q(role__in=ROLE_VALUES),
                name="ck_portal_users__role_allowed",
            ),
        ]

    def save(self, *args, **kwargs):
        self.username = PortalUserManager.normalize_login(self.username)
        # Framework flags follow the closed application role. They are not a
        # second authorization system and can never create another role.
        self.is_staff = self.role == self.Role.ADMIN
        self.is_superuser = False
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"is_staff", "is_superuser"}
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("User identities are deactivated, not physically deleted.")
