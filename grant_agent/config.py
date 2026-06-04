import os
from dataclasses import dataclass, field
from typing import List


MISSION = (
    "AI education and community literacy platform targeting underserved communities "
    "in Chicago south suburban Cook County"
)

# Granted MCP search queries per target source
GRANTED_QUERIES = [
    "NSF SBIR artificial intelligence education",
    "Department of Labor WIOA workforce technology training",
    "Woods Fund Chicago community technology",
]

# Pages to scrape directly (Firecrawl preferred, httpx fallback)
SCRAPE_TARGETS = [
    {
        "source": "Google.org AI Opportunity Fund",
        "url": "https://www.google.org/our-work/googlers-grants/",
        "fallback_url": "https://blog.google/outreach-initiatives/google-org/",
    },
    {
        "source": "OpenAI People-First AI Fund",
        "url": "https://openai.com/global-affairs/people-first-ai-fund/",
        "fallback_url": "https://openai.com/global-affairs/",
    },
    {
        "source": "NSF SBIR",
        "url": "https://www.sbir.gov/api/solicitations/open",
        "is_api": True,
    },
    {
        "source": "DOL WIOA",
        "url": "https://www.grants.gov/search-grants?oppStatuses=forecasted%7Copen&agencyCode=DOL",
        "fallback_url": "https://www.grants.gov/search-grants",
    },
    {
        "source": "Woods Fund Chicago",
        "url": "https://www.woodsfund.org/grantmaking/apply/",
        "fallback_url": "https://www.woodsfund.org/grantmaking/",
    },
]

ALERT_DAYS = 30
MAX_GRANT_AGE_DAYS = 90
SCORE_BOLD_THRESHOLD = 7

CLAUDE_MODEL = "claude-sonnet-4-6"

ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
