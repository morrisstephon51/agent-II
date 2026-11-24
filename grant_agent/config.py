import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ.

    The repo ships .env.example and gitignores .env, but nothing read it, so
    ANTHROPIC_API_KEY / COMPOSIO_API_KEY / ALERT_EMAIL were empty unless the
    shell exported them. The weekly cron entry from `main.py --cron` never has
    them, so every scheduled run used placeholder 5/10 scores and sent no email.
    Variables already set in the environment win over the file.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

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

CLAUDE_MODEL = "claude-sonnet-4-6"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Composio email alerts
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "")
COMPOSIO_API_KEY = os.getenv("COMPOSIO_API_KEY", "")
