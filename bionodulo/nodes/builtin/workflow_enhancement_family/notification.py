"""Workflow notification node."""

from .adapter import NotificationNode as _NotificationContract


class NotificationNode(_NotificationContract):
    """Deliver a configured workflow notification."""

    NODE_ID = "notification"
