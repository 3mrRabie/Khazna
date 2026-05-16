"""
health.py
─────────
Password health analysis engine for the security dashboard.

Scans all decrypted vault entries and computes:
• Weak passwords       – score < 45 from check_password_strength()
• Weak passwords       – score < 45 from check_password_strength()
• Old passwords        – not modified in > 90 days
• Overall health score – weighted average

All analysis runs in-memory on already-decrypted data.  No plaintext
touches the database or leaves the process.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from encryption import check_password_strength
from models import PasswordEntry


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

WEAK_THRESHOLD   = 45    # score < this → weak
OLD_DAYS         = 90    # password older than this → old


# ──────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────

@dataclass
class HealthIssue:
    """A single password health issue for one entry."""
    entry_id:    int
    site_name:   str
    issue_type:  str      # "weak", "old"
    severity:    str      # "high", "medium", "low"
    description: str
    score:       int = 0  # password strength score (for weak issues)


@dataclass
class HealthReport:
    """Aggregated password health analysis result."""
    total_count:    int   = 0
    weak_count:     int   = 0

    old_count:      int   = 0
    breached_count: int   = 0    # filled in by breach checker
    overall_score:  int   = 100  # 0–100, higher is better
    issues:         List[HealthIssue] = field(default_factory=list)


# ──────────────────────────────────────────────
# Analyzer
# ──────────────────────────────────────────────

class PasswordHealthAnalyzer:
    """
    Stateless analyzer.  Call ``analyze(entries)`` with the full list of
    decrypted vault entries to get a HealthReport.
    """

    def analyze(self, entries: List[PasswordEntry]) -> HealthReport:
        """Run all health checks and return a comprehensive report."""
        report = HealthReport(total_count=len(entries))

        if not entries:
            return report

        issues: List[HealthIssue] = []

        # 1. Weak password detection
        strength_cache: dict[int, int] = {}
        for entry in entries:
            if not entry.password or not entry.id:
                continue
            result = check_password_strength(entry.password)
            score = result["score"]
            strength_cache[entry.id] = score

            if score < WEAK_THRESHOLD:
                severity = "high" if score < 25 else "medium"
                issues.append(HealthIssue(
                    entry_id=entry.id,
                    site_name=entry.display_name(),
                    issue_type="weak",
                    severity=severity,
                    description=f"Password strength: {result['level']} ({score}/100)",
                    score=score,
                ))
                report.weak_count += 1


        # 3. Old password detection
        now = datetime.now()
        cutoff = now - timedelta(days=OLD_DAYS)
        for entry in entries:
            if not entry.id:
                continue
            mod_date = entry.modified_at or entry.created_at
            if mod_date and mod_date < cutoff:
                age_days = (now - mod_date).days
                issues.append(HealthIssue(
                    entry_id=entry.id,
                    site_name=entry.display_name(),
                    issue_type="old",
                    severity="low" if age_days < 180 else "medium",
                    description=f"Password last changed {age_days} days ago",
                ))
                report.old_count += 1

        # Sort issues by severity (high first), then by type
        severity_order = {"high": 0, "medium": 1, "low": 2}
        issues.sort(key=lambda i: (severity_order.get(i.severity, 3), i.issue_type))

        report.issues = issues

        # 4. Calculate overall health score
        report.overall_score = self._calculate_score(report)

        return report

    @staticmethod
    def _calculate_score(report: HealthReport) -> int:
        """
        Compute an overall vault health score (0–100).

        Deductions:
        - Each weak password:   -8 points
        - Each weak password:   -8 points
        - Each old password:    -3 points
        - Each breached:        -15 points
        """
        if report.total_count == 0:
            return 100

        deductions = (
            report.weak_count     * 8
            + report.old_count    * 3
            + report.breached_count * 15
        )

        # Normalize: at most 100 points deducted
        score = max(0, 100 - deductions)
        return score
