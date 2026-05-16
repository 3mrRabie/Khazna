"""
normalizer.py
─────────────
Smart site name normalization module.
Provides brand-aware labeling and removes noise from raw URLs.
"""

import re
from urllib.parse import urlparse

# Well-known brands to map to their proper casing
BRAND_MAP = {
    "google": "Google",
    "instagram": "Instagram",
    "github": "GitHub",
    "gitlab": "GitLab",
    "hackthebox": "Hack The Box",
    "tryhackme": "TryHackMe",
    "facebook": "Facebook",
    "twitter": "Twitter",
    "x": "X",
    "linkedin": "LinkedIn",
    "amazon": "Amazon",
    "apple": "Apple",
    "microsoft": "Microsoft",
    "netflix": "Netflix",
    "spotify": "Spotify",
    "konami": "Konami",
    "yahoo": "Yahoo!",
    "discord": "Discord",
    "slack": "Slack",
    "trello": "Trello",
    "jira": "Jira",
    "atlassian": "Atlassian",
    "aws": "AWS",
    "reddit": "Reddit",
    "tiktok": "TikTok",
    "snapchat": "Snapchat",
    "pinterest": "Pinterest",
    "paypal": "PayPal",
    "stripe": "Stripe",
}

# Specific subdomain/hostname overrides
SUBDOMAIN_BRAND_MAP = {
    "academy.hackthebox.com": "HTB Academy",
    "academy.hackthebox.eu": "HTB Academy",
    "accounts.google.com": "Google",
    "myaccount.google.com": "Google",
    "account.konami.net": "Konami",
    "console.aws.amazon.com": "AWS",
    "aws.amazon.com": "AWS",
}

def is_clean_name(name: str) -> bool:
    """
    Check if a name is already human-readable and clean.
    A clean name typically has no dots (like a URL) or has spaces.
    """
    if not name:
        return False
        
    # If it has spaces, it's almost certainly a human-readable title
    if " " in name:
        return True
        
    # If it contains no dots, it's not a raw hostname
    if "." not in name:
        return True
        
    # If it's explicitly in the brand map (ignoring case)
    if name.lower() in BRAND_MAP.values() or name.lower() in BRAND_MAP.keys():
        return True
        
    return False

def extract_hostname(url_or_domain: str) -> str:
    """Extracts the hostname from a URL or raw domain string."""
    if not url_or_domain:
        return ""
        
    # urlparse requires a scheme to properly parse netloc
    if "://" not in url_or_domain:
        parsed = urlparse("http://" + url_or_domain)
    else:
        parsed = urlparse(url_or_domain)
        
    host = parsed.netloc or parsed.path
    host = host.split('/')[0].split(':')[0] # Remove path and port
    return host.lower()

def normalize_site_name(site_name: str, url: str) -> str:
    """
    Smarter site name normalization.
    Preserves existing clean names, strips noise from raw URLs,
    and applies brand-aware casing and aliases.
    """
    site_name = (site_name or "").strip()
    url = (url or "").strip()
    
    # 1. Prefer an already clean site_name
    if is_clean_name(site_name):
        return site_name
        
    # 2. Extract hostname from site_name or url
    host = extract_hostname(site_name)
    if not host and url:
        host = extract_hostname(url)
        
    if not host:
        return site_name or "Unknown"
        
    # 3. Check for specific subdomain overrides FIRST
    if host in SUBDOMAIN_BRAND_MAP:
        return SUBDOMAIN_BRAND_MAP[host]
        
    # 4. Strip noisy prefixes
    parts = host.split('.')
    noise_prefixes = {'www', 'm', 'mobile', 'android', 'ios', 'app', 'account', 'accounts', 'login', 'auth', 'sso', 'secure', 'my'}
    
    while len(parts) > 1 and parts[0] in noise_prefixes:
        parts.pop(0)
        
    # 5. Extract the primary domain part
    if not parts:
        return "Unknown"
        
    # Consider the first part as the primary brand/name (e.g. 'instagram' from 'instagram.com')
    # This works for most cases, though things like 'co.uk' exist, usually the brand is before it.
    primary_name = parts[0]
    
    # 6. Apply Brand Map
    if primary_name in BRAND_MAP:
        return BRAND_MAP[primary_name]
        
    # 7. Fallback: Capitalize nicely
    # Convert dashes to spaces, title case
    clean_name = primary_name.replace('-', ' ').title()
    return clean_name
