from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from inspection.models import FilterScheme, Inspection
from inspection.rules import judge


class Command(BaseCommand):
    help = "seed two inspections, two accounts and one filter scheme"

    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name="inspector")
        keeper, created = User.objects.get_or_create(username="keeper")
        if created or not keeper.check_password("light123456"):
            keeper.set_password("light123456")
            keeper.save()
        keeper.groups.add(group)
        watch, created = User.objects.get_or_create(username="watch")
        if created or not watch.check_password("watch123456"):
            watch.set_password("watch123456")
            watch.save()
        watch.groups.remove(group)
        if not Inspection.objects.exists():
            samples = [
                ("LH-01", 1400, 1200, 0.4),
                ("LH-09", 800, 1200, 0.2),
            ]
            for code, measured, required, bearing in samples:
                verdict, note = judge(measured, required, bearing)
                Inspection.objects.create(
                    aid_code=code,
                    measured_cd=measured,
                    required_cd=required,
                    bearing_error_deg=bearing,
                    verdict=verdict,
                    note=note,
                    created_by="keeper",
                )
        # 交卷方案：只含不合格，灯号文字为 09；一键套上后只剩偏暗种子 LH-09
        _, scheme_created = FilterScheme.objects.get_or_create(
            name="不合格-09",
            defaults={
                "verdicts": "不合格",
                "aid_text": "09",
                "created_by": "keeper",
            },
        )
        self.stdout.write("seeded" if scheme_created else "scheme already exists")
