from django.utils.cache import add_never_cache_headers


class NoCacheProtectedMiddleware:
    """
    Prevents caching of sensitive and authenticated views so browser Back/Forward 
    navigation after logout will never expose protected pages from browser cache.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Apply strict no-cache headers if user is authenticated or visiting protected/admin/invigilator/api routes
        is_authenticated = bool(getattr(request, 'user', None) and request.user.is_authenticated)
        is_protected_path = request.path.startswith((
            '/admin-dashboard', '/period', '/exam-session', '/halls', 
            '/users', '/invigilator', '/control-room', '/reports', '/api/'
        ))

        if is_authenticated or is_protected_path:
            add_never_cache_headers(response)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response
