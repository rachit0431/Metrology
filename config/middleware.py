"""
Middleware for seamless operation in both local HTTP development and
cloud HTTPS iframe preview environments.
"""
from http.cookies import Morsel

# Enable CHIPS (Cookies Having Independent Partitioned State) in Python 3.10+
Morsel._reserved.setdefault('partitioned', 'Partitioned')
Morsel._flags.add('partitioned')


class IframeCookieMiddleware:
    """
    1. Normalizes multi-proxy X-Forwarded-Host headers (if comma-separated).
    2. Restores X-Forwarded-Proto=https when Cloud Run requests pass through
       the local container HTTP nginx proxy.
    3. Prevents false 403 CSRF rejections inside cross-origin preview iframes
       where third-party cookies may be restricted by the browser.
    4. Adds SameSite=None; Secure; Partitioned to session and CSRF cookies in
       HTTPS iframe previews while keeping standard cookies on local HTTP.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        forwarded_host = request.META.get('HTTP_X_FORWARDED_HOST', '')
        if forwarded_host and ',' in forwarded_host:
            forwarded_host = forwarded_host.split(',')[0].strip()
            request.META['HTTP_X_FORWARDED_HOST'] = forwarded_host

        origin = request.META.get('HTTP_ORIGIN', '')
        referer = request.META.get('HTTP_REFERER', '')

        is_cloud_preview = (
            '.run.app' in forwarded_host
            or '.run.app' in origin
            or '.run.app' in referer
            or '.google.com' in origin
            or '.google.com' in referer
        )

        # Nginx inside the container listens on HTTP 8080 behind Cloud Run TLS
        # and sets X-Forwarded-Proto to $scheme ('http'). Restore 'https' for
        # Cloud Run preview traffic so Django knows the outer request is HTTPS.
        if is_cloud_preview:
            request.META['HTTP_X_FORWARDED_PROTO'] = 'https'
            request._dont_enforce_csrf_checks = True

        response = self.get_response(request)

        is_https = (
            is_cloud_preview
            or request.is_secure()
            or request.META.get('HTTP_X_FORWARDED_PROTO', '').lower() == 'https'
        )
        if is_https and hasattr(response, 'cookies'):
            for morsel in response.cookies.values():
                morsel['samesite'] = 'None'
                morsel['secure'] = True
                morsel['partitioned'] = True

        # Container Nginx has 'proxy_intercept_errors on; error_page 403 = /forbidden.html;'
        # which replaces Django's HTML with a raw Nginx 403 page if status 403 is returned.
        if is_cloud_preview and response.status_code == 403:
            response.status_code = 200

        return response
