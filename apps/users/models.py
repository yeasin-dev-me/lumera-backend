"""User and Role models for Lumera authentication and RBAC."""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from apps.common.models import PublicIdModel, TimeStampedModel


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
        """Return the union of all permission strings assigned to this user."""
        if self.is_superuser:
            return ["*"]
        perms = set()
        for role in self.roles.all():
            if isinstance(role.permissions, list):
                perms.update(role.permissions)
        return sorted(list(perms))

    def has_perm_code(self, perm_code: str) -> bool:
        """Check if user has a specific permission code."""
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        user_perms = self.get_permission_codes()
        return ("*" in user_perms) or (perm_code in user_perms)
