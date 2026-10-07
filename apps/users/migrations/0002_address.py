from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("users", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Address",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)),
                ("label", models.CharField(blank=True, default="", max_length=64)),
                ("full_name", models.CharField(max_length=255)),
                ("phone", models.CharField(max_length=50)),
                ("address_line1", models.CharField(max_length=255)),
                ("address_line2", models.CharField(blank=True, default="", max_length=255)),
                ("city", models.CharField(max_length=100)),
                ("area", models.CharField(blank=True, default="", max_length=100)),
                ("postal_code", models.CharField(blank=True, default="", max_length=20)),
                ("country", models.CharField(default="Bangladesh", max_length=100)),
                ("is_default", models.BooleanField(default=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="users.user")),
            ],
            options={"db_table": "users_address", "ordering": ["-is_default", "-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="address",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_default", True)),
                fields=("user",),
                name="unique_default_address_per_user",
            ),
        ),
    ]
