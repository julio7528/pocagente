from django.test import SimpleTestCase, TestCase
from django.db import IntegrityError, transaction

from apps.web_portal.accounts.models import ROLE_VALUES, User


class UserModelContractTests(SimpleTestCase):
    def test_user_identity_roles_and_password_hash_are_defined(self):
        self.assertEqual(User._meta.pk.get_internal_type(), "UUIDField")
        self.assertEqual(User._meta.db_table, "users")
        self.assertEqual(tuple(User.Role.values), ROLE_VALUES)
        user = User(username="client", role=User.Role.CLIENT)
        user.set_password("synthetic-test-password")
        self.assertNotEqual(user.password, "synthetic-test-password")
        self.assertTrue(user.check_password("synthetic-test-password"))

    def test_username_normalizer_trims_and_lowercases(self):
        self.assertEqual(User.objects.normalize_login("  Client.Name  "), "client.name")


class UserPersistenceTests(TestCase):
    def test_username_is_canonical_and_case_whitespace_unique(self):
        user = User.objects.create_user(
            username="  Client.Name ", password="synthetic-test-password", role=User.Role.CLIENT
        )
        self.assertEqual(user.username, "client.name")
        self.assertTrue(user.check_password("synthetic-test-password"))
        self.assertFalse(User.objects.filter(username="Client.Name").exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username=" CLIENT.NAME ", password="another-synthetic-password", role=User.Role.CLIENT
            )
