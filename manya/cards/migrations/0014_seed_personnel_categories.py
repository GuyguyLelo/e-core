from django.db import migrations

PERSONNEL_CATEGORIES = [
    "Enseignant",
    "Personnel Administratif",
    "Personnel technique",
    "Autres",
]


def seed_personnel_categories(apps, schema_editor):
    Category = apps.get_model("cards", "Category")
    for name in PERSONNEL_CATEGORIES:
        Category.objects.get_or_create(name=name)


def unseed_personnel_categories(apps, schema_editor):
    Category = apps.get_model("cards", "Category")
    Category.objects.filter(name__in=PERSONNEL_CATEGORIES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cards", "0013_backfill_missing_personnel_columns"),
    ]

    operations = [
        migrations.RunPython(seed_personnel_categories, unseed_personnel_categories),
    ]
