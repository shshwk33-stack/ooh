"""Reproducible, geometry-only processing of verified administrative boundaries.

This package does not compute mobility, spatial value, advertising exposure, or
bootstrap estimates.  The existing frontend and its fixtures remain separate.
"""

__version__ = "1.0.0"


class PipelineError(ValueError):
    """A validation failure; no successful analysis artifacts are published."""

    def __init__(self, message, *, code="VALIDATION_FAILED", context=None):
        super().__init__(message)
        self.code = code
        self.context = context or {}

    def issue(self):
        return {"code": self.code, "message": str(self), **self.context}
