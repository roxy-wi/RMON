from datetime import timedelta


class Configuration(object):
    SECRET_KEY = 'very secret salt to protect your RMON sessions'
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 3000
    SCHEDULER_API_ENABLED = True
    JWT_SECRET_KEY = "very secret salt to protect your RMON jwt"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
