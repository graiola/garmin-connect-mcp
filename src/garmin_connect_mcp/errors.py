"""Public error messages deliberately exclude remote response bodies and credentials."""

class ConnectorError(Exception):
    """An actionable, non-sensitive error safe to return to an MCP client."""

class ConfigurationError(ConnectorError):
    pass

class UpstreamError(ConnectorError):
    def __init__(self, status: int):
        self.status = status
        messages = {
            401: "Garmin authentication failed. Check key expiration/revocation locally.",
            403: "Garmin denied this resource. Check Personal API access and permissions.",
            404: "Garmin did not find this resource; it may be unavailable for this account.",
            429: "Garmin rate limit reached. Wait before trying again.",
        }
        super().__init__(messages.get(status, f"Garmin returned HTTP {status}. Try again later."))
