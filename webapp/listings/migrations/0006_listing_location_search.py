from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0005_listing_operation_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="location_search",
            field=models.CharField(blank=True, db_index=True, default="", max_length=300),
        ),
    ]
