from __future__ import annotations

import getpass

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from apps.web_portal.accounts.services import (
    AccountPolicyError,
    AdminAlreadyBootstrappedError,
    bootstrap_first_admin,
)


class Command(BaseCommand):
    help = "Interactively create the first active portal ADMIN identity."

    def handle(self, *args, **options):
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise CommandError("Password confirmation did not match; no account was created.")
        try:
            result = bootstrap_first_admin(username=username, password=password)
        except (AccountPolicyError, AdminAlreadyBootstrappedError, ValidationError) as exc:
            # Exception messages are policy-level and contain no credentials.
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(f"Initial ADMIN account created for {result.user.username}.")
        )
