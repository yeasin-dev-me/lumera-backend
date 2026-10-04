"""Management command to seed initial development and integration staff user."""
from django.core.management.base import BaseCommand
from apps.users.models import Role, User


class Command(BaseCommand):
    help = "Seed initial staff user and super_admin role for integration tests."

    def handle(self, *args, **options):
        email = "staff@lumera.internal"
        password = "StaffPassword123!"

        role, _ = Role.objects.get_or_create(
            name="super_admin",
            defaults={
                "description": "Full access to all operations",
                "permissions": ["*"],
            },
        )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": "Admin",
                "last_name": "Lumera",
                "is_staff": True,
                "is_active": True,
            },
        )

        user.set_password(password)
        user.is_staff = True
        user.is_active = True
        user.roles.add(role)
        user.save()

        status_text = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{status_text} staff user: {email}"))
