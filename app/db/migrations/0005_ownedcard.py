from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0004_alter_card_set_alter_screenshot_set"),
    ]

    operations = [
        migrations.CreateModel(
            name="OwnedCard",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "card",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ownership",
                        to="db.card",
                    ),
                ),
            ],
            options={
                "db_table": "owned_cards",
            },
        ),
    ]
