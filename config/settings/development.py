"""Development settings for Lumera Backend."""
from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Allow all origins in local development if desired, but default to configured list
CORS_ALLOW_ALL_ORIGINS = True
