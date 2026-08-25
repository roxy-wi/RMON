class OidcLoginError(Exception):
    """An OIDC failure whose sanitized message may be returned to the user."""

    def __init__(self, error: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.error = error
        self.message = message
        self.status_code = status_code
