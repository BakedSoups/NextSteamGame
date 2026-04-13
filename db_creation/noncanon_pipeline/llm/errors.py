class CreditsExhaustedError(RuntimeError):
    pass


class NoReviewsError(RuntimeError):
    pass


class SteamReviewsUnavailableError(RuntimeError):
    pass


class NoReviewsAfterFilteringError(RuntimeError):
    pass
