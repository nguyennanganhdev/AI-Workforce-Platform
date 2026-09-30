"""Public adapter failures. Never include backend bodies or credentials in errors."""


class AdapterError(Exception):
    def __init__(
        self, code: str, *, retryable: bool = False, outcome_unknown: bool = False
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.outcome_unknown = outcome_unknown


class ValidationError(AdapterError):
    def __init__(self) -> None:
        super().__init__("validation_error")
