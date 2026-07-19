"""Focused native reporting node contracts."""

from .html_report import HTMLReportNode
from .pdf_report import PDFReportNode
from .qc_dashboard import QCDashboardNode

__all__ = ["HTMLReportNode", "PDFReportNode", "QCDashboardNode"]
