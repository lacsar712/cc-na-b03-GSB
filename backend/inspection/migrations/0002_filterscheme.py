from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inspection", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="FilterScheme",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=40, unique=True, verbose_name="方案名称")),
                ("verdicts", models.CharField(
                    default="", max_length=60, verbose_name="判词多选")),
                ("aid_text", models.CharField(
                    blank=True, default="", max_length=40, verbose_name="灯号文字")),
                ("created_by", models.CharField(max_length=64, verbose_name="创建人")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
