"""
categories.py
─────────────
Category detection and management for vault entries.

Provides auto-detection of entry categories from URL / site name using a
curated domain→category mapping.  Detection is suggestive, not forced.

Built-in categories: Social Media, CTF Platforms, Educational, Work,
Finance, Shopping, Development, Gaming, Cloud, Other.
"""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlparse


# ──────────────────────────────────────────────
# Built-in categories
# ──────────────────────────────────────────────

BUILTIN_CATEGORIES: List[str] = [
    "Social Media",
    "CTF Platforms",
    "Educational",
    "Work",
    "Finance",
    "Shopping",
    "Development",
    "Gaming",
    "Cloud",
    "Other",
]

# Category icons for UI display
CATEGORY_ICONS: dict[str, str] = {
    "Social Media":   "👥",
    "CTF Platforms":  "🚩",
    "Educational":    "🎓",
    "Work":           "💼",
    "Finance":        "🏦",
    "Shopping":       "🛒",
    "Development":    "💻",
    "Gaming":         "🎮",
    "Cloud":          "☁️",
    "Other":          "📁",
}


# ──────────────────────────────────────────────
# Domain → category mapping
# ──────────────────────────────────────────────

_DOMAIN_MAP: dict[str, str] = {
    # Social Media
    "facebook.com":     "Social Media",
    "instagram.com":    "Social Media",
    "twitter.com":      "Social Media",
    "x.com":            "Social Media",
    "linkedin.com":     "Social Media",
    "reddit.com":       "Social Media",
    "tiktok.com":       "Social Media",
    "snapchat.com":     "Social Media",
    "pinterest.com":    "Social Media",
    "tumblr.com":       "Social Media",
    "mastodon.social":  "Social Media",
    "discord.com":      "Social Media",
    "discordapp.com":   "Social Media",
    "telegram.org":     "Social Media",
    "whatsapp.com":     "Social Media",
    "signal.org":       "Social Media",
    "threads.net":      "Social Media",
    "bluesky.app":      "Social Media",

    # CTF Platforms
    "tryhackme.com":       "CTF Platforms",
    "hackthebox.com":      "CTF Platforms",
    "hackthebox.eu":       "CTF Platforms",
    "ctftime.org":         "CTF Platforms",
    "picoctf.org":         "CTF Platforms",
    "overthewire.org":     "CTF Platforms",
    "vulnhub.com":         "CTF Platforms",
    "pentesterlab.com":    "CTF Platforms",
    "root-me.org":         "CTF Platforms",
    "cyberdefenders.org":  "CTF Platforms",
    "letsdefend.io":       "CTF Platforms",
    "blueteamlabs.online": "CTF Platforms",
    "rangeforce.com":      "CTF Platforms",
    "pwnable.kr":          "CTF Platforms",
    "exploit.education":   "CTF Platforms",

    # Educational
    "coursera.org":     "Educational",
    "udemy.com":        "Educational",
    "edx.org":          "Educational",
    "khanacademy.org":  "Educational",
    "udacity.com":      "Educational",
    "pluralsight.com":  "Educational",
    "skillshare.com":   "Educational",
    "lynda.com":        "Educational",
    "codecademy.com":   "Educational",
    "freecodecamp.org": "Educational",
    "leetcode.com":     "Educational",
    "hackerrank.com":   "Educational",
    "codewars.com":     "Educational",
    "brilliant.org":    "Educational",
    "duolingo.com":     "Educational",
    "memrise.com":      "Educational",
    "academia.edu":     "Educational",
    "researchgate.net": "Educational",
    "scholar.google.com": "Educational",

    # Work
    "slack.com":            "Work",
    "notion.so":            "Work",
    "asana.com":            "Work",
    "trello.com":           "Work",
    "monday.com":           "Work",
    "jira.atlassian.com":   "Work",
    "atlassian.com":        "Work",
    "confluence.atlassian.com": "Work",
    "basecamp.com":         "Work",
    "clickup.com":          "Work",
    "zoom.us":              "Work",
    "teams.microsoft.com":  "Work",
    "meet.google.com":      "Work",
    "webex.com":            "Work",
    "airtable.com":         "Work",
    "figma.com":            "Work",
    "canva.com":            "Work",
    "miro.com":             "Work",
    "hubspot.com":          "Work",
    "salesforce.com":       "Work",
    "zendesk.com":          "Work",
    "freshdesk.com":        "Work",
    "intercom.com":         "Work",
    "mailchimp.com":        "Work",

    # Finance
    "paypal.com":           "Finance",
    "stripe.com":           "Finance",
    "wise.com":             "Finance",
    "revolut.com":          "Finance",
    "robinhood.com":        "Finance",
    "coinbase.com":         "Finance",
    "binance.com":          "Finance",
    "kraken.com":           "Finance",
    "blockchain.com":       "Finance",
    "venmo.com":            "Finance",
    "cash.app":             "Finance",
    "mint.com":             "Finance",
    "ynab.com":             "Finance",
    "chase.com":            "Finance",
    "bankofamerica.com":    "Finance",
    "wellsfargo.com":       "Finance",
    "capitalone.com":       "Finance",
    "americanexpress.com":  "Finance",

    # Shopping
    "amazon.com":       "Shopping",
    "amazon.co.uk":     "Shopping",
    "amazon.de":        "Shopping",
    "ebay.com":         "Shopping",
    "etsy.com":         "Shopping",
    "aliexpress.com":   "Shopping",
    "shopify.com":      "Shopping",
    "walmart.com":      "Shopping",
    "target.com":       "Shopping",
    "bestbuy.com":      "Shopping",
    "newegg.com":       "Shopping",
    "wish.com":         "Shopping",
    "asos.com":         "Shopping",
    "zalando.com":      "Shopping",
    "ikea.com":         "Shopping",

    # Development
    "github.com":           "Development",
    "gitlab.com":           "Development",
    "bitbucket.org":        "Development",
    "stackoverflow.com":    "Development",
    "stackexchange.com":    "Development",
    "npmjs.com":            "Development",
    "pypi.org":             "Development",
    "crates.io":            "Development",
    "hub.docker.com":       "Development",
    "docker.com":           "Development",
    "vercel.com":           "Development",
    "netlify.com":          "Development",
    "heroku.com":           "Development",
    "railway.app":          "Development",
    "render.com":           "Development",
    "replit.com":           "Development",
    "codepen.io":           "Development",
    "codesandbox.io":       "Development",
    "postman.com":          "Development",
    "sentry.io":            "Development",
    "datadog.com":          "Development",
    "grafana.com":          "Development",
    "terraform.io":         "Development",
    "ansible.com":          "Development",
    "jenkins.io":           "Development",

    # Gaming
    "store.steampowered.com": "Gaming",
    "steampowered.com":       "Gaming",
    "epicgames.com":          "Gaming",
    "gog.com":                "Gaming",
    "twitch.tv":              "Gaming",
    "ea.com":                 "Gaming",
    "origin.com":             "Gaming",
    "battle.net":             "Gaming",
    "blizzard.com":           "Gaming",
    "riotgames.com":          "Gaming",
    "xbox.com":               "Gaming",
    "playstation.com":        "Gaming",
    "nintendo.com":           "Gaming",
    "itch.io":                "Gaming",
    "humble.com":             "Gaming",
    "humblebundle.com":       "Gaming",
    "ubisoft.com":            "Gaming",

    # Cloud
    "console.aws.amazon.com":   "Cloud",
    "aws.amazon.com":           "Cloud",
    "portal.azure.com":         "Cloud",
    "azure.microsoft.com":      "Cloud",
    "console.cloud.google.com": "Cloud",
    "cloud.google.com":         "Cloud",
    "digitalocean.com":         "Cloud",
    "linode.com":               "Cloud",
    "vultr.com":                "Cloud",
    "cloudflare.com":           "Cloud",
    "namecheap.com":            "Cloud",
    "godaddy.com":              "Cloud",
    "domains.google.com":       "Cloud",
    "porkbun.com":              "Cloud",
    "hetzner.com":              "Cloud",
    "ovh.com":                  "Cloud",
    "scaleway.com":             "Cloud",
    "fly.io":                   "Cloud",
    "supabase.com":             "Cloud",
    "firebase.google.com":      "Cloud",
    "mongodb.com":              "Cloud",
}

# Keyword fallbacks (checked if domain lookup fails)
_KEYWORD_MAP: dict[str, str] = {
    "bank":       "Finance",
    "pay":        "Finance",
    "money":      "Finance",
    "invest":     "Finance",
    "crypto":     "Finance",
    "trade":      "Finance",
    "shop":       "Shopping",
    "store":      "Shopping",
    "buy":        "Shopping",
    "mall":       "Shopping",
    "market":     "Shopping",
    "game":       "Gaming",
    "play":       "Gaming",
    "steam":      "Gaming",
    "xbox":       "Gaming",
    "code":       "Development",
    "dev":        "Development",
    "git":        "Development",
    "api":        "Development",
    "docker":     "Development",
    "cloud":      "Cloud",
    "aws":        "Cloud",
    "azure":      "Cloud",
    "hosting":    "Cloud",
    "server":     "Cloud",
    "hack":       "CTF Platforms",
    "ctf":        "CTF Platforms",
    "cyber":      "CTF Platforms",
    "pentest":    "CTF Platforms",
    "learn":      "Educational",
    "course":     "Educational",
    "academy":    "Educational",
    "edu":        "Educational",
    "school":     "Educational",
    "university": "Educational",
    "college":    "Educational",
    "work":       "Work",
    "office":     "Work",
    "team":       "Work",
    "project":    "Work",
    "social":     "Social Media",
    "chat":       "Social Media",
    "forum":      "Social Media",
    "community":  "Social Media",
}


# ──────────────────────────────────────────────
# Detection engine
# ──────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    """Extract the registerable domain from a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = parsed.hostname or ""
        if host.startswith("www."):
            host = host[4:]
        return host.lower()
    except Exception:
        return ""


def detect_category(url: str = "", site_name: str = "") -> str:
    """
    Auto-detect a category for a vault entry based on URL and site name.

    Returns the best-guess category string.  Falls back to "Other" if
    nothing matches.  This is always a *suggestion* — the user can
    override it.
    """
    domain = _extract_domain(url)

    # 1. Exact domain match (with and without subdomains)
    if domain:
        if domain in _DOMAIN_MAP:
            return _DOMAIN_MAP[domain]
        # Try parent domain (e.g. "mail.google.com" → "google.com")
        parts = domain.split(".")
        if len(parts) > 2:
            parent = ".".join(parts[-2:])
            if parent in _DOMAIN_MAP:
                return _DOMAIN_MAP[parent]

    # 2. Keyword matching in domain and site name
    combined = f"{domain} {site_name}".lower()
    for keyword, category in _KEYWORD_MAP.items():
        if keyword in combined:
            return category

    return "Other"


def get_category_icon(category: str) -> str:
    """Return the emoji icon for a category."""
    return CATEGORY_ICONS.get(category, "📁")
