"""The six weekly investor education emails.

Written once, read by counsel with the site copy, then sent automatically by
`manage.py daily` one week apart to everyone who completed the accreditation
calculator and has not unsubscribed. Plain text on purpose: it reads as a
person writing, and it is what compliance review can actually read.

Rules baked in: no fund is named, no return is quoted, nothing is recommended,
every email says what accredited status is and is not, and every email carries
the unsubscribe line. {first_name} falls back to "there"; {unsubscribe_url} and
{calculator_url} are filled by the sender.
"""

EMAILS = [
    {
        "subject": "Your result, and what it actually means",
        "body": """Hi {first_name},

You took the Luminaz accreditation calculator, so here is the plain version of what the result means.

"Accredited investor" is a label the SEC created in 1982. It says that, based on income or net worth, you are allowed to be offered private investments that are not sold to the general public. It is not a badge of skill, it does not mean anyone has checked your judgment, and it does not mean private investments are right for you. It only opens a door.

The thresholds have not moved since 1982: $200,000 of income for two years ($300,000 with a spouse), or $1,000,000 of net worth not counting your home. Inflation has done the rest. That is why about one household in five now qualifies and most of them were never told.

Over the next five weeks I will send one short email a week: what a closed-end fund is, what "506(c)" means for you, the kinds of funds Luminaz lists, the questions to ask before you wire money anywhere, and what is filing with the SEC right now.

Nothing in these emails recommends an investment. Luminaz is a place to see what exists; every decision is yours, with your own advisers.

Diane Barney
Luminaz

You are receiving this because you completed the calculator at Luminaz. Unsubscribe: {unsubscribe_url}
""",
    },
    {
        "subject": "What a closed-end fund is (and why it has an ending)",
        "body": """Hi {first_name},

Every fund on Luminaz is "closed-end." Here is what that means and why it matters.

A closed-end fund raises a set amount of money over a set window, then closes to new investors, invests the money according to its stated strategy, and winds down at the end of a defined term, typically five to ten years, returning whatever is left to the investors. You cannot usually take your money out early. In exchange, the manager is not forced to sell at a bad time to pay someone who wants to leave.

The opposite is an "evergreen" or open-end fund, which keeps taking money and lets investors redeem on a schedule. Luminaz does not list those; they work differently and deserve a different kind of attention.

The two things to look for in any closed-end fund: the term (when does it end?) and the strategy (what exactly is the money buying, and why now?). A fund that cannot answer both in a paragraph has not finished thinking.

Diane Barney
Luminaz

Unsubscribe: {unsubscribe_url}
""",
    },
    {
        "subject": "What 506(c) means for you",
        "body": """Hi {first_name},

You will see "Rule 506(c)" on every Luminaz listing. It is the reason the listing can exist.

Private funds do not register with the SEC the way public companies do. Instead they use an exemption. Under the older one, 506(b), a manager could only offer the fund to people they already knew. Under 506(c), created in 2013, a manager may advertise publicly, on one condition: every single investor must be verified as accredited before they invest. Not self-declared. Verified, with documents or a letter from a CPA, attorney, or adviser.

So when you request materials from a fund on Luminaz, expect the manager to ask you to prove your status before they accept a dollar. That is not them being difficult; it is the rule that lets them talk to you at all. Luminaz does not do that verification and never sees your financial documents.

One more thing 506(c) does not do: it does not mean the SEC reviewed the fund. No one at the SEC has read the offering. The fund filed a short notice called a Form D, and that is all.

Diane Barney
Luminaz

Unsubscribe: {unsubscribe_url}
""",
    },
    {
        "subject": "The kinds of funds you will see",
        "body": """Hi {first_name},

Luminaz lists private funds in eight categories. The four most common, in plain language:

Real estate: the fund buys property, usually apartments, storage, industrial, or commercial buildings, improves or operates it, and sells at the end of the term. Income along the way, a lump at the end, and the risks are the property market and the operator.

Business acquisition (private equity): the fund buys small companies, often from retiring founders, runs them better or combines them, and sells them in five to seven years. The risk is the businesses themselves and the people running them.

Private debt: the fund lends money, to businesses or property owners, and earns interest. Steadier than the others, and the risk is whether borrowers pay it back.

Venture: the fund backs young companies, most of which fail, hoping a few succeed enormously. The longest term, the widest range of outcomes.

The other four are energy (oil and gas, renewables, minerals), infrastructure (utilities, storage, transport, data centers), agriculture and timber (farmland, orchards, forests) and specialty (litigation finance, royalties, collectibles). Each has its own cycle and its own risks.

None of these is better than another. They suit different people, different amounts, and different patience. The manager's offering documents will tell you the fees, the term, and the risks specific to that fund; read those before anything else.

Diane Barney
Luminaz

Unsubscribe: {unsubscribe_url}
""",
    },
    {
        "subject": "Twelve questions before you wire money into a private fund",
        "body": """Hi {first_name},

Before any private investment, ask the manager these. A good manager will welcome them; a weak one will hurry past them.

1. Who exactly is the general partner, and what have they done before?
2. What does the fund buy, and what is the plan for selling it?
3. When does the fund end, and what happens if it cannot sell on time?
4. What are the fees, all of them: management, carried interest, acquisition, disposition, asset management?
5. How much of their own money is the manager putting in?
6. What is the minimum, and can I invest through my IRA or trust?
7. How and when will I receive reports, and are the financials audited?
8. Who holds the money, and who signs the checks?
9. What is the worst realistic outcome, and has the manager lived through one?
10. Have any of the principals been subject to regulatory or disciplinary action? (The Form D and BrokerCheck can confirm the answer.)
11. Can I speak to an investor from a prior fund?
12. What is in the PPM that you would rather I not notice?

Answers belong in the offering documents; if they are only spoken, ask for them in writing. Luminaz does not evaluate funds or answer these questions for you; the manager does.

Diane Barney
Luminaz

Unsubscribe: {unsubscribe_url}
""",
    },
    {
        "subject": "What is filing right now",
        "body": """Hi {first_name},

Last one in this series. Every private fund that raises money files a short public notice with the SEC called a Form D within fifteen days of its first sale. It is on the SEC's EDGAR site for anyone to read: the fund's name, its category, how much it is raising, the minimum investment, the people behind it, and whether a broker is being paid.

That means the private market is not as private as it sounds. You can see who is raising, right now, in any category, without asking anyone's permission. It is how Luminaz finds the managers it invites, and it is a habit worth having yourself: before any fund, look up its Form D and make sure the story matches.

From here, Luminaz will send one platform notice: the day the catalog opens. No more lessons unless you ask.

When the catalog is open, the link is here: {calculator_url}

Diane Barney
Luminaz

Unsubscribe: {unsubscribe_url}
""",
    },
]
