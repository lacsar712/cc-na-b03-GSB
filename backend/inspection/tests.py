from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from inspection.models import FilterScheme, Inspection


class FilterSchemeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.group = Group.objects.create(name="inspector")
        cls.keeper = User.objects.create_user("keeper", password="x")
        cls.keeper.groups.add(cls.group)
        cls.watch = User.objects.create_user("watch", password="x")
        cls.lh01 = Inspection.objects.create(
            aid_code="LH-01", measured_cd=1400, required_cd=1200,
            bearing_error_deg=0.4, verdict="合格", note="光强与方位均在限内",
            created_by="keeper",
        )
        cls.lh09 = Inspection.objects.create(
            aid_code="LH-09", measured_cd=800, required_cd=1200,
            bearing_error_deg=0.2, verdict="不合格", note="光强不足",
            created_by="keeper",
        )

    def _scheme(self, name="s", verdicts=("不合格",), aid_text=""):
        return FilterScheme.objects.create(
            name=name, verdicts=",".join(verdicts), aid_text=aid_text,
            created_by="keeper",
        )

    def test_and_narrowing_zero_hits_shows_no_match_message(self):
        # 判词与灯号文字同时满足；一个都不中时不许把全部行铺回来
        scheme = self._scheme(name="零命中", verdicts=("不合格",), aid_text="XX")
        self.client.force_login(self.watch)
        resp = self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        self.assertRedirects(resp, reverse("list"))
        resp = self.client.get(reverse("list"))
        self.assertContains(resp, "没有相符灯")
        self.assertNotContains(resp, "LH-01")
        self.assertNotContains(resp, "LH-09")
        self.assertNotContains(resp, "还没有记录")

    def test_apply_filters_and_refresh_stays(self):
        scheme = self._scheme(name="不合格-09", verdicts=("不合格",), aid_text="09")
        self.client.force_login(self.watch)
        self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        # 刷新（再次 GET）仍停在同一方案上
        for _ in range(2):
            resp = self.client.get(reverse("list"))
            self.assertContains(resp, "LH-09")
            self.assertNotContains(resp, "LH-01")
            self.assertIn(str(scheme.pk), str(self.client.session["active_scheme_id"]))

    def test_seeded_scheme_leaves_only_dim_lamp(self):
        from django.core.management import call_command

        call_command("seed_demo")
        scheme = FilterScheme.objects.get(name="不合格-09")
        self.assertEqual(scheme.verdict_list, ["不合格"])
        self.assertEqual(scheme.aid_text, "09")
        # seed_demo 会重置 keeper 密码哈希，刷新实例后再登录以免会话被登出
        self.keeper.refresh_from_db()
        self.client.force_login(self.keeper)
        self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        resp = self.client.get(reverse("list"))
        self.assertContains(resp, "LH-09")
        self.assertNotContains(resp, "LH-01")

    def test_readonly_can_apply_but_not_create_rename_delete(self):
        scheme = self._scheme()
        other = self._scheme(name="另一个", verdicts=("合格",), aid_text="")
        self.client.force_login(self.watch)
        # 只读账号能套用已有方案
        resp = self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        self.assertRedirects(resp, reverse("list"))
        # 不能新建
        resp = self.client.post(reverse("scheme_create"), {
            "name": "偷建", "verdicts": ["不合格"], "aid_text": "09"})
        self.assertEqual(resp.status_code, 403)
        # 不能改名
        resp = self.client.post(reverse("scheme_rename", args=[scheme.pk]),
                                {"name": "偷改"})
        self.assertEqual(resp.status_code, 403)
        # 不能删除
        resp = self.client.post(reverse("scheme_delete", args=[other.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(FilterScheme.objects.filter(pk=other.pk).exists())
        # 只读账号页面不出现新建、改名、删除入口
        resp = self.client.get(reverse("list"))
        self.assertNotContains(resp, "新建方案")
        self.assertNotContains(resp, "改名")
        self.assertNotContains(resp, "删除")
        self.assertContains(resp, "套用")

    def test_keeper_create_rename_delete(self):
        self.client.force_login(self.keeper)
        resp = self.client.post(reverse("scheme_create"), {
            "name": "双判词", "verdicts": ["合格", "不合格"]})
        self.assertRedirects(resp, reverse("list"))
        scheme = FilterScheme.objects.get(name="双判词")
        self.assertEqual(set(scheme.verdict_list), {"合格", "不合格"})
        # 两个判词都选时两行都在
        self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        resp = self.client.get(reverse("list"))
        self.assertContains(resp, "LH-01")
        self.assertContains(resp, "LH-09")
        # 改名
        resp = self.client.post(reverse("scheme_rename", args=[scheme.pk]),
                                {"name": "改过名"})
        self.assertRedirects(resp, reverse("list"))
        self.assertTrue(FilterScheme.objects.filter(name="改过名").exists())
        # 删除正套用的方案后总表恢复可看全部
        resp = self.client.post(reverse("scheme_delete", args=[scheme.pk]))
        self.assertRedirects(resp, reverse("list"))
        self.assertNotIn("active_scheme_id", self.client.session)
        resp = self.client.get(reverse("list"))
        self.assertContains(resp, "LH-01")
        self.assertContains(resp, "LH-09")
        self.assertNotContains(resp, "没有相符灯")

    def test_clear_returns_all_rows(self):
        scheme = self._scheme(verdicts=("不合格",), aid_text="09")
        self.client.force_login(self.keeper)
        self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        resp = self.client.post(reverse("scheme_clear"))
        self.assertRedirects(resp, reverse("list"))
        resp = self.client.get(reverse("list"))
        self.assertContains(resp, "LH-01")
        self.assertContains(resp, "LH-09")

    def test_create_requires_at_leat_one_condition(self):
        self.client.force_login(self.keeper)
        resp = self.client.post(reverse("scheme_create"), {"name": "空方案"})
        self.assertRedirects(resp, reverse("list"))
        self.assertFalse(FilterScheme.objects.filter(name="空方案").exists())

    def test_stale_session_scheme_falls_back_to_all(self):
        scheme = self._scheme()
        self.client.force_login(self.watch)
        self.client.post(reverse("scheme_apply", args=[scheme.pk]))
        scheme.delete()
        resp = self.client.get(reverse("list"))
        self.assertContains(resp, "LH-01")
        self.assertNotIn("active_scheme_id", self.client.session)
