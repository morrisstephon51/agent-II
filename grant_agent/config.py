import os

MISSION = (
    "AI education and community literacy platform targeting underserved communities "
    "in Chicago south suburban Cook County"
)

GRANTED_QUERIES = [
    "NSF SBIR artificial intelligence education",
    "Department of Labor WIOA workforce technology training",
    "Woods Fund Chicago community technology",
]

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

# Composio email alerts
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
