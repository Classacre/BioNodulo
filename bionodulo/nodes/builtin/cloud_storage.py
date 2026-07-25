"""Compatibility facade for focused cloud-storage nodes."""

from .cloud_storage_family import S3DownloadNode as S3DownloadNode
from .cloud_storage_family import S3UploadNode as S3UploadNode

__all__ = ["S3DownloadNode", "S3UploadNode"]
