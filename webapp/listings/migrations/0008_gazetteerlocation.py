from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0007_backfill_location_search"),
    ]

    operations = [
        migrations.CreateModel(
            name="GazetteerLocation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("normalized", models.CharField(db_index=True, max_length=200)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("oblast", "Область"),
                            ("raion", "Район"),
                            ("city", "Місто"),
                            ("town", "Селище"),
                            ("village", "Село"),
                            ("other", "Інше"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                (
                    "parent_path",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Hierarchical chain, e.g. 'Київська обл. > Бучанський р-н'.",
                        max_length=500,
                    ),
                ),
                ("koatuu", models.CharField(blank=True, default="", max_length=20)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
            ],
            options={
                "ordering": ["name"],
                "indexes": [
                    models.Index(
                        fields=["kind", "normalized"],
                        name="listings_ga_kind_d3df50_idx",
                    ),
                ],
                "unique_together": {("name", "kind", "parent_path")},
            },
        ),
    ]
