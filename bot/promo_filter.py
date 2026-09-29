"""Keyword-based detection of promotional tweets (no API needed)."""

import re

_PROMO_PATTERNS = [
    r"\bpromo ?codes?\b",
    r"\bcodes? promo\b",
    r"\buse (my )?code\b",
    r"\butilise[zr]? (le |mon )?code\b",
    r"\bdiscount codes?\b",
    r"\b\d{1,2} ?% (off|de réduction)\b",
    r"\bfree trial\b",
    r"\bessai gratuit\b",
    r"\bgiveaway\b",
    r"\blink in (my )?bio\b",
    r"\blien (en|dans (ma|la)) bio\b",
    r"\bsign up (now|today|here|for)\b",
    r"\bsubscribe (now|today|here|to (my|our))\b",
    r"\babonnez[- ]vous\b",
    r"\binscrivez[- ]vous\b",
    r"\bjoin (my|our) (telegram|discord|newsletter|community|webinar|course|group|channel)\b",
    r"\brejoi(ns|gnez) (mon|notre|ma) (telegram|discord|newsletter|communauté|groupe|canal|formation)\b",
    r"\bwebinar\b",
    r"\bwebinaire\b",
    r"\bmasterclass\b",
    r"\blimited[- ]time offer\b",
    r"\boffre limitée\b",
    r"\bsponsored\b",
    r"\bsponsorisé\b",
    r"(^|\s)#(ad|ads|sponsored|promo|pub)\b",
]

PROMO_PROMPT = (
    "Ce tweet est-il de la promotion ou de la publicité ? C'est le cas s'il fait la "
    "promotion d'un produit, service, abonnement, newsletter, formation, webinaire, "
    "application, broker, code promo, concours/giveaway, lien d'affiliation, ou s'il "
    "invite à s'abonner, s'inscrire ou acheter. Une information de marché ou une actualité "
    "n'est PAS de la promotion.\n"
    "Réponds uniquement par 'OUI' ou 'NON'.\n\n"
)

_PROMO_RE = re.compile("|".join(_PROMO_PATTERNS), re.IGNORECASE)


def looks_promotional(text: str) -> bool:
    """Return True if the text matches common advertising/self-promotion phrases."""
    return bool(text and _PROMO_RE.search(text))
