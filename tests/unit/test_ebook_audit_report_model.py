from __future__ import annotations

from core.ebook.models import AuditReport


def test_audit_report_summary_contains_counts() -> None:
    report = AuditReport(total_books=5, total_size_gb=1.25)
    text = report.summary()

    assert "Library Audit Report" in text
    assert "Total Books: 5" in text
    assert "Total Size: 1.25 GB" in text
