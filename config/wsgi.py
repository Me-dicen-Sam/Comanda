"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

_django_app = get_wsgi_application()


def application(environ, start_response):
    def _start_response(status, headers, exc_info=None):
        cleaned_headers = [
            (name, value.lstrip() if name.lower() == 'set-cookie' and isinstance(value, str) else value)
            for name, value in headers
        ]
        return start_response(status, cleaned_headers, exc_info)

    return _django_app(environ, _start_response)
