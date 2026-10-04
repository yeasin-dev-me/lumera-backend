import re
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from apps.common.models import PublicIdModel, TimeStampedModel

PERMISSION_PATTERN = re.compile(r"^[a-z_]+\.[a-z_]+$")


def validate_permission_code(code: str) -> str:
    """Validate a single permission code string (canonical module.action or '*')."""
    if not isinstance(code, str):
        raise ValidationError("Permission code must be a string.")
    code = code.strip()
    if not code:
        raise ValidationError("Permission code cannot be empty.")
    if code == "*":
        return code
    if not PERMISSION_PATTERN.match(code):
        raise ValidationError(
            f"Invalid permission format '{code}'. Must be in canonical 'module.action' format (e.g. 'products.read')."
        )
    return code


def validate_permissions_list(permissions) -> list:
    """Validate a collection of permissions, rejecting invalid types or formats."""
    if not isinstance(permissions, list):
        raise ValidationError("Permissions must be a list of permission strings.")
    validated = []
    for perm in permissions:
        valid_perm = validate_permission_code(perm)
        if valid_perm not in validated:
            validated.append(valid_perm)
    return validated


class Role(TimeStampedModel):
    """Named role aggregating permission codes (e.g., 'super_admin', 'order_manager')."""
    name = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True, default="")
    permissions = models.JSONField(
        default=list,
        help_text="List of permission codes (e.g. ['products.read', 'orders.update'])",
    )

    class Meta:
        db_table = "users_role"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.permissions = validate_permissions_list(self.permissions)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class UserManager(BaseUserManager):
    """Custom manager using email as unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, PublicIdModel, TimeStampedModel):
    """Custom user model for both Storefront customers and CMS staff."""
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Designates if user can access CMS.")
    roles = models.ManyToManyField(Role, blank=True, related_name="users")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users_user"
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

    def get_permission_codes(self):
        """Return the union of all validated permission strings assigned to this user."""
        if not self.is_active:
            return []
        if self.is_superuser:
            return ["*"]
        perms = set()
        for role in self.roles.all():
            if isinstance(role.permissions, list):
                for p in role.permissions:
                    if isinstance(p, str) and (PERMISSION_PATTERN.match(p) or p == "*"):
                        perms.add(p)
        return sorted(list(perms))

    def has_perm_code(self, perm_code: str) -> bool:
        """Check if user has a specific permission code."""
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        if not perm_code or not isinstance(perm_code, str):
            return False
        user_perms = self.get_permission_codes()
        return ("*" in user_perms) or (perm_code in user_perms)
