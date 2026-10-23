from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0012_alter_teacherremark_lesson_iteration"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedlesson",
            name="material_pages",
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
    ]
