"""本地验证用：sqlite 内存库，跑 manage.py check / test 时指定 --settings=config.test_settings。"""

from config.settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
