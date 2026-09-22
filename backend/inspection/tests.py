from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from inspection.models import FilterPreset, Inspection
from inspection.rules import judge


def make_inspection(code, measured, required, bearing, by="keeper"):
    verdict, note = judge(measured, required, bearing)
    return Inspection.objects.create(
        aid_code=code,
        measured_cd=measured,
        required_cd=required,
        bearing_error_deg=bearing,
        verdict=verdict,
        note=note,
        created_by=by,
    )


class PresetFlowTests(TestCase):
    def setUp(self):
        group = Group.objects.create(name="inspector")
        self.keeper = User.objects.create_user(username="keeper", password="light123456")
        self.keeper.groups.add(group)
        self.watch = User.objects.create_user(username="watch", password="watch123456")
        self.lh01 = make_inspection("LH-01", 1400, 1200, 0.4)  # 合格
        self.lh09 = make_inspection("LH-09", 800, 1200, 0.2)  # 不合格 · 光强不足

    def login_keeper(self):
        self.client.login(username="keeper", password="light123456")

    def login_watch(self):
        self.client.login(username="watch", password="watch123456")

    def make_preset(self, name="偏暗种子", verdicts=None, code="09"):
        return FilterPreset.objects.create(
            name=name,
            verdicts=verdicts if verdicts is not None else ["不合格"],
            code_contains=code,
            created_by="keeper",
        )

    def listed_codes(self):
        response = self.client.get(reverse("list"))
        return [row.aid_code for row in response.context["rows"]]

    # --- 保存方案 ---

    def test_keeper_saves_preset_and_list_stays_full_until_applied(self):
        self.login_keeper()
        response = self.client.post(
            reverse("preset_create"),
            {"name": "偏暗种子", "verdicts": ["不合格"], "code_contains": "09"},
        )
        self.assertRedirects(response, reverse("list"))
        preset = FilterPreset.objects.get(name="偏暗种子")
        self.assertEqual(preset.verdicts, ["不合格"])
        self.assertEqual(preset.code_contains, "09")
        self.assertEqual(preset.created_by, "keeper")
        # 只保存不套用，总表仍是全部
        self.assertEqual(self.listed_codes(), ["LH-09", "LH-01"])

    def test_create_requires_name_and_at_least_one_verdict(self):
        self.login_keeper()
        self.client.post(reverse("preset_create"), {"name": "", "verdicts": ["合格"]})
        self.client.post(reverse("preset_create"), {"name": "空判词", "code_contains": "09"})
        self.assertFalse(FilterPreset.objects.exists())

    def test_create_rejects_duplicate_name_and_unknown_verdict(self):
        self.login_keeper()
        self.make_preset()
        self.client.post(
            reverse("preset_create"),
            {"name": "偏暗种子", "verdicts": ["合格"]},
        )
        self.assertEqual(FilterPreset.objects.count(), 1)
        # 未登记的判词值被丢弃，剩下的有效判词照常保存
        self.client.post(
            reverse("preset_create"),
            {"name": "混搭", "verdicts": ["合格", "待定"], "code_contains": ""},
        )
        self.assertEqual(FilterPreset.objects.get(name="混搭").verdicts, ["合格"])

    # --- 套用与收窄 ---

    def test_apply_narrows_to_rows_matching_all_conditions(self):
        self.login_keeper()
        preset = self.make_preset()
        response = self.client.get(reverse("list") + f"?apply={preset.pk}")
        self.assertRedirects(response, reverse("list"))
        self.assertEqual(self.listed_codes(), ["LH-09"])

    def test_applied_preset_survives_refresh(self):
        self.login_keeper()
        preset = self.make_preset()
        self.client.get(reverse("list") + f"?apply={preset.pk}")
        self.assertEqual(self.listed_codes(), ["LH-09"])  # 刷新仍停在该方案
        self.assertEqual(self.listed_codes(), ["LH-09"])

    def test_apply_with_multi_verdicts_and_blank_code(self):
        self.login_keeper()
        preset = self.make_preset(name="全部判词", verdicts=["合格", "不合格"], code="")
        self.client.get(reverse("list") + f"?apply={preset.pk}")
        self.assertEqual(self.listed_codes(), ["LH-09", "LH-01"])

    def test_no_match_shows_empty_message_without_fallback(self):
        self.login_keeper()
        preset = self.make_preset(name="合格的09", verdicts=["合格"], code="09")
        self.client.get(reverse("list") + f"?apply={preset.pk}")
        response = self.client.get(reverse("list"))
        self.assertContains(response, "没有相符灯")
        self.assertNotContains(response, "LH-01")
        self.assertNotContains(response, "LH-09")

    def test_apply_unknown_or_bad_id_is_ignored(self):
        self.login_keeper()
        self.client.get(reverse("list") + "?apply=999")
        self.client.get(reverse("list") + "?apply=abc")
        self.assertEqual(self.listed_codes(), ["LH-09", "LH-01"])

    def test_clear_returns_to_full_list(self):
        self.login_keeper()
        preset = self.make_preset()
        self.client.get(reverse("list") + f"?apply={preset.pk}")
        self.client.get(reverse("list") + "?clear=1")
        self.assertEqual(self.listed_codes(), ["LH-09", "LH-01"])

    # --- 权限 ---

    def test_watch_can_apply_but_not_manage_presets(self):
        preset = self.make_preset()
        self.login_watch()
        self.client.get(reverse("list") + f"?apply={preset.pk}")
        self.assertEqual(self.listed_codes(), ["LH-09"])
        for url, data in [
            (reverse("preset_create"), {"name": "x", "verdicts": ["合格"]}),
            (reverse("preset_rename", args=[preset.pk]), {"name": "y"}),
            (reverse("preset_delete", args=[preset.pk]), {}),
        ]:
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(FilterPreset.objects.count(), 1)
        # 只读账号看不到保存方案的表单
        response = self.client.get(reverse("list"))
        self.assertNotContains(response, "保存新方案")

    def test_keeper_sees_create_form(self):
        self.login_keeper()
        response = self.client.get(reverse("list"))
        self.assertContains(response, "保存新方案")

    # --- 改名与删除 ---

    def test_rename_preset(self):
        self.login_keeper()
        preset = self.make_preset()
        self.client.post(reverse("preset_rename", args=[preset.pk]), {"name": "暗灯"})
        preset.refresh_from_db()
        self.assertEqual(preset.name, "暗灯")
        # 改成已占用的名字会被拒绝
        self.make_preset(name="另一个", verdicts=["合格"], code="")
        self.client.post(reverse("preset_rename", args=[preset.pk]), {"name": "另一个"})
        preset.refresh_from_db()
        self.assertEqual(preset.name, "暗灯")

    def test_delete_applied_preset_restores_full_list(self):
        self.login_keeper()
        preset = self.make_preset()
        self.client.get(reverse("list") + f"?apply={preset.pk}")
        self.assertEqual(self.listed_codes(), ["LH-09"])
        self.client.post(reverse("preset_delete", args=[preset.pk]))
        self.assertFalse(FilterPreset.objects.exists())
        self.assertEqual(self.listed_codes(), ["LH-09", "LH-01"])

    def test_delete_other_preset_keeps_active_filter(self):
        self.login_keeper()
        active = self.make_preset()
        other = self.make_preset(name="另一个", verdicts=["合格"], code="")
        self.client.get(reverse("list") + f"?apply={active.pk}")
        self.client.post(reverse("preset_delete", args=[other.pk]))
        self.assertEqual(self.listed_codes(), ["LH-09"])

    # --- 登录门槛 ---

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("list"))
        self.assertRedirects(response, "/login/?next=/")
