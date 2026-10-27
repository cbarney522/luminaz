"""The first-contact email to a fund manager. The agent fills the blanks from the
lead record (Form D data) and Diane approves each one before it goes out.

Placeholders: {first}, {fund_name}, {category_phrase}, {filed_phrase}, {founder},
{signature}, {manager_url}, {credit_line}, and three that come from Settings so no price
is typed into the email: {rate}, {founding_cap}, {free_months}. Change the words here or
in Settings (outreach_subject / outreach_body override this file when set).
"""

SUBJECT = "{fund_name}: a place accredited investors can find it"

BODY = """Hi {first},

I saw {fund_name}'s Form D{filed_phrase} and wanted to reach out directly.

I'm building Luminaz, a listing site where accredited investors browse 506(c) funds{category_phrase} and request materials from the manager. Investors use it free. Managers pay a flat {rate} a month per listing, billed at the end of each month for the days the listing was live, pause or cancel any time. Every listing is free until the catalog has enough accredited investors, so you are never billed for a listing nobody can see yet. There's no percentage of the raise and no success fee: you keep the whole raise, and Luminaz is paid for the work of running the site, not for results. We don't publish performance projections, rank funds, or sit between you and your investors; when an investor requests materials, their name goes to you and the conversation is yours.
{credit_line}
The first {founding_cap} fund managers to list are Founding Managers: the {rate} rate locked for every fund you ever list, in exchange for being early while the catalog fills.

If that's useful, reply and I'll send the listing link, or tell me a time and I'll walk you through it in ten minutes. If it isn't, a one-line "no" saves us both time.

{founder}
Luminaz
{signature}
{manager_url}"""

CREDIT_LINE = "\nBecause we've spoken before, your first invoice after the free period carries a {rate} credit.\n"


def draft(lead, founder, signature, manager_url, credit=False, subject_t=None, body_t=None,
          rate="$850", founding_cap="25", free_months="0"):
    """Returns (subject, body) with every placeholder filled from the lead row."""
    subject_t = subject_t or SUBJECT
    body_t = body_t or BODY
    first = (lead.get("contact_name") or "").strip().split(" ")[0] or "there"
    cat = (lead.get("category") or "").strip()
    category_phrase = (" in " + cat.lower()) if cat and cat.lower() not in ("", "other") else ""
    filed = (lead.get("filed") or "").strip()
    filed_phrase = (" filed " + filed[:10]) if filed else ""
    ctx = dict(first=first, fund_name=lead.get("fund_name") or "your fund", category_phrase=category_phrase,
               filed_phrase=filed_phrase, founder=founder, signature=signature, manager_url=manager_url,
               credit_line=CREDIT_LINE.format(rate=rate) if credit else "",
               rate=rate, founding_cap=founding_cap, free_months=free_months)
    try:
        return subject_t.format(**ctx), body_t.format(**ctx)
    except (KeyError, IndexError, ValueError):
        return SUBJECT.format(**ctx), BODY.format(**ctx)
