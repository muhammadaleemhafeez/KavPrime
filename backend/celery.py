from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# ✅ use your real Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

# ✅ celery app name can be backend
app = Celery("backend")

# Load config from Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in installed apps
app.autodiscover_tasks()
