from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_courier_order_delivered_at_order_shipped_at_and_more"),
        ("users", "0001_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="ReturnRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)),
                ("reason", models.TextField(max_length=1000)),
                ("status", models.CharField(choices=[("requested", "Requested"), ("approved", "Approved"), ("rejected", "Rejected"), ("completed", "Completed")], default="requested", max_length=32)),
                ("staff_note", models.TextField(blank=True, default="")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_requests", to="orders.order")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_requests", to="users.user")),
            ],
            options={"db_table": "orders_returnrequest", "ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="returnrequest",
            constraint=models.UniqueConstraint(condition=models.Q(("status__in", ["requested", "approved"])), fields=("order", "user"), name="one_active_return_per_order"),
        ),
    ]
