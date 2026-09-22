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


class FilterPreset(models.Model):
    """命名的查找方案：判词多选 + 灯号包含文字，套用后总表只留同时满足的行。"""

    name = models.CharField("方案名", max_length=40, unique=True)
    verdicts = models.JSONField("判词", default=list)
    code_contains = models.CharField("灯号包含", max_length=40, blank=True, default="")
    created_by = models.CharField("创建人", max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name
