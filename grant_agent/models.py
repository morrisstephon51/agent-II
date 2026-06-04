from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Grant:
    title: str
    url: str
    source: str
    description: str
    deadline: Optional[date] = None
    award_min: Optional[int] = None
    award_max: Optional[int] = None
    scraped_at: date = field(default_factory=date.today)

    def days_until_deadline(self) -> Optional[int]:
        if self.deadline is None:
            return None
        return (self.deadline - date.today()).days

    def is_recent(self, max_days: int = 90) -> bool:
        """True if deadline is in the future or within max_days ago."""
        if self.deadline is None:
            return True  # keep if unknown
        return self.days_until_deadline() >= -max_days

    def award_range_str(self) -> str:
        if self.award_min and self.award_max:
            return f"${self.award_min:,}–${self.award_max:,}"
        if self.award_max:
            return f"Up to ${self.award_max:,}"
        if self.award_min:
            return f"From ${self.award_min:,}"
        return "Not specified"


@dataclass
class ScoredGrant:
    grant: Grant
    fit_score: int          # 1-10
    qualification_summary: str

    def deadline_str(self) -> str:
        if self.grant.deadline:
            return self.grant.deadline.strftime("%Y-%m-%d")
        return "Rolling / TBD"

    def is_urgent(self, days: int = 30) -> bool:
        d = self.grant.days_until_deadline()
        return d is not None and 0 <= d <= days
