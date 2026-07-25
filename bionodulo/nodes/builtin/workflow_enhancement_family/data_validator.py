"""Workflow data-validator node."""

from .adapter import DataValidatorNode as _DataValidatorContract


class DataValidatorNode(_DataValidatorContract):
    """Validate workflow files and structured values before downstream use."""

    NODE_ID = "data_validator"
