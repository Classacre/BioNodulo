"""Compatibility facade for focused native reporting node modules."""

from .reporting_family import HTMLReportNode, PDFReportNode, QCDashboardNode

__all__ = ["HTMLReportNode", "PDFReportNode", "QCDashboardNode"]
