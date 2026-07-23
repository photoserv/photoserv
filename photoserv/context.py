from django.conf import settings
import core
from photoserv import settings
from photoserv.version import __version__ as VERSION


def global_context(request):
    return {
        "UI_THUMBNAIL_LARGE": core.UI_THUMBNAIL_LARGE,
        "UI_THUMBNAIL_SMALL": core.UI_THUMBNAIL_SMALL,
        "SIMPLE_AUTH_ENABLED": settings.SIMPLE_AUTH,
        "OIDC_AUTH_ENABLED": settings.OIDC_ENABLED,
        "OIDC_PROVIDER_NAME": settings.OIDC_NAME,
        "APP_VERSION": VERSION,
    }
