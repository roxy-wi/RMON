class Configuration(object):
    SECRET_KEY = 'very secret salt to protect your RMON sessions'
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'strict'
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 3000
    SCHEDULER_API_ENABLED = True
