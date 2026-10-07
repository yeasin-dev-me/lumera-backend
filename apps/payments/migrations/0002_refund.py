from django.db import migrations, models
import django.db.models.deletion
import uuid
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_courier_order_delivered_at_order_shipped_at_and_more"),
        ("payments", "0001_initial"),
        ("users", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="Refund",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="pending", max_length=32)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("provider_reference", models.CharField(blank=True, default="", max_length=255)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="orders.order")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="payments.payment")),
                ("processed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="processed_refunds", to="users.user")),
            ],
            options={"db_table": "payments_refund", "ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="refund",
            constraint=models.CheckConstraint(check=models.Q(("amount__gt", Decimal("0.00"))), name="check_refund_amount_positive"),
        ),
    ]
