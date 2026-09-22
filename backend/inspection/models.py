from django.db import models


class Inspection(models.Model):
    aid_code = models.CharField("航标编号", max_length=40)
    measured_cd = models.FloatField("实测光强")
    required_cd = models.FloatField("要求光强")
    bearing_error_deg = models.FloatField("方位偏差")
    verdict = models.CharField("结论", max_length=20)
    note = models.CharField("说明", max_length=200)
    created_by = models.CharField("登记人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class FilterScheme(models.Model):
    """命名的总表收窄方案：判词多选 + 灯号中的一段文字。"""

    name = models.CharField("方案名称", max_length=40, unique=True)
    verdicts = models.CharField("判词多选", max_length=60, default="")
    aid_text = models.CharField("灯号文字", max_length=40, blank=True, default="")
    created_by = models.CharField("创建人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    @property
    def verdict_list(self) -> list[str]:
        return [v for v in self.verdicts.split(",") if v]

    def matches(self):
        """返回同时满足判词多选与灯号文字的行；条件之间是 AND。"""
        rows = Inspection.objects.all()
        choices = self.verdict_list
        if choices:
            rows = rows.filter(verdict__in=choices)
        if self.aid_text:
            rows = rows.filter(aid_code__icontains=self.aid_text)
        return rows
