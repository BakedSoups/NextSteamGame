class CreditsExhaustedError(RuntimeError):
    pass


class NoReviewsError(RuntimeError):
    def __init__(self, message: str, *, status: str) -> None:
        super().__init__(message)
        self.status = status


class SteamReviewsUnavailableError(RuntimeError):
    pass


class NoReviewsAfterFilteringError(RuntimeError):
    pass
