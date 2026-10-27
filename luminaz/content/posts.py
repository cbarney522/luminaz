"""Three marketing messages a week about accredited investors.

The app drafts Monday / Wednesday / Friday posts from this bank in order (36 posts,
twelve weeks, then it starts over with fresh wording from the model if a key is
set, otherwise repeats). Each post has a long version (LinkedIn, Facebook,
newsletter), a short version (X, Threads, under 280 characters), and hashtags.

Rules every post follows, and that the model is told to follow:
  - Education about accreditation and private funds. Never about a specific fund.
  - No returns, no projections, no "outperform", no "guaranteed", no urgency.
  - Luminaz describes funds and never recommends them.
  - One call to action only: the calculator.
Placeholders: {calculator_url}
"""

POSTS = [
    # ---- Week 1: you may already qualify
    {"topic": "You may already qualify",
     "long": "About one in five American households meets the SEC's definition of an accredited investor. Most of them have no idea.\n\nThe thresholds were set in 1982 and never adjusted for inflation: $200,000 of income for two years ($300,000 with a spouse), or $1 million of net worth not counting your home. A two-career household in its fifties with a paid-down house and a healthy 401(k) often clears it without ever thinking of themselves as \"wealthy.\"\n\nWhy it matters: accredited status is the key to a category of investments that never appears in a brokerage account. Two minutes with the calculator tells you where you stand, and nothing you enter is kept.\n{calculator_url}",
     "short": "1 in 5 US households is an accredited investor. Most don't know it. The thresholds haven't moved since 1982. Two-minute check, nothing stored: {calculator_url}",
     "tags": "#AccreditedInvestor #PersonalFinance #PrivateFunds"},
    {"topic": "What accredited actually means",
     "long": "\"Accredited investor\" sounds like a credential. It isn't. Nobody issues a card. It's a definition in SEC Rule 501 that describes who the government assumes can bear the risk of an unregistered investment.\n\nThree common ways to meet it:\n- Income over $200,000 in each of the last two years ($300,000 with a spouse or partner), with a reasonable expectation of the same this year\n- Net worth over $1 million, alone or with a spouse, excluding your primary residence\n- Holding a Series 7, 65, or 82 license in good standing\n\nMeeting one is enough. Check yours in two minutes: {calculator_url}",
     "short": "\"Accredited investor\" isn't a license you apply for. It's a definition: $200k income, or $1M net worth outside your home, or a Series 7/65/82. Meet one and you're in. {calculator_url}",
     "tags": "#AccreditedInvestor #Rule501 #InvestorEducation"},
    {"topic": "Your house doesn't count",
     "long": "The most common mistake people make when they check whether they're accredited: counting the house.\n\nThe net worth test is $1 million, and your primary residence is excluded. So is the mortgage on it, up to the home's value. What's left is everything else: retirement accounts, brokerage accounts, cash, other real estate, a business you own, minus your other debts.\n\nPeople assume that leaves them short. Often it doesn't. A couple with $700,000 across two 401(k)s, a $200,000 brokerage account, and a rental property is over the line without the house at all.\n\nThe calculator does the arithmetic the SEC way: {calculator_url}",
     "short": "Checking if you're accredited? Your house doesn't count. Neither does the mortgage. Everything else does: retirement accounts, brokerage, rentals, a business. Do the math the SEC way: {calculator_url}",
     "tags": "#NetWorth #AccreditedInvestor #RetirementPlanning"},
    # ---- Week 2: what opens up
    {"topic": "What accredited status unlocks",
     "long": "Being accredited doesn't change what you can buy in a brokerage account. It changes what you can be offered outside of one.\n\nPrivate funds that raise money under SEC Regulation D can only accept accredited investors. That's where private real estate funds, small-business acquisition funds, private credit funds, and venture funds live. None of them trade on an exchange. None of them show up in a retirement plan menu.\n\nThat isn't a reason to invest in them. It is a reason to know the door exists. Find out if you're on the right side of it: {calculator_url}",
     "short": "Accredited status doesn't change your brokerage account. It changes what you can be offered outside one: private real estate, acquisition funds, private credit, venture. Know if the door is open: {calculator_url}",
     "tags": "#PrivateFunds #RegulationD #AccreditedInvestor"},
    {"topic": "Why private funds aren't advertised to you",
     "long": "Ever wonder why you never see ads for private real estate funds or private credit funds?\n\nFor most of the last century, it was illegal. A private fund could not advertise, period. It could only raise money from people the manager already knew.\n\nIn 2013 the JOBS Act changed that. Rule 506(c) lets a fund advertise publicly, on one condition: every investor it accepts must be verified as accredited. Not self-certified. Verified, with documents.\n\nThat's why the accredited definition suddenly matters to ordinary households. It's the ticket. Check whether you hold one: {calculator_url}",
     "short": "Until 2013 private funds couldn't advertise at all. Now they can, under Rule 506(c), but only accredited investors can say yes. That definition is the ticket. Check yours: {calculator_url}",
     "tags": "#JOBSAct #Rule506c #AccreditedInvestor"},
    {"topic": "The four kinds of private funds",
     "long": "When people say \"private fund,\" they usually mean one of four things.\n\nReal estate funds pool money to buy apartment buildings, self-storage, industrial, or land, and return capital when the properties sell.\n\nBusiness acquisition funds buy small companies, often from retiring founders, and run them.\n\nPrivate credit funds lend money to businesses or real estate projects that banks won't touch, and collect interest.\n\nVenture funds back early companies in exchange for equity.\n\nEach has its own timeline, risk, and minimum. All four are typically open only to accredited investors. Step one is knowing whether that's you: {calculator_url}",
     "short": "The four kinds of private funds: real estate, business acquisition, private credit, venture. Different timelines, different risks. One thing in common: accredited investors only. Are you one? {calculator_url}",
     "tags": "#PrivateEquity #RealEstateInvesting #PrivateCredit #AccreditedInvestor"},
    # ---- Week 3: the income test in detail
    {"topic": "The income test, explained",
     "long": "The income test for accredited status trips people up in two places.\n\nFirst, it's two years in a row, not an average. $250,000 last year and $150,000 the year before doesn't qualify on income alone.\n\nSecond, it's gross income, before taxes, and the SEC lets you count it either individually or jointly with a spouse or spousal equivalent. Individually the bar is $200,000; jointly it's $300,000. Two people earning $160,000 each clear the joint test with room to spare.\n\nYou also need a reasonable expectation of reaching the same level this year. A planned retirement in March changes the answer.\n\nRun your numbers: {calculator_url}",
     "short": "The income test: $200k two years running (or $300k jointly), gross, with a reasonable expectation of the same this year. Not an average. Two $160k earners qualify jointly. Check: {calculator_url}",
     "tags": "#AccreditedInvestor #IncomeTest #FinancialLiteracy"},
    {"topic": "Two careers, one threshold",
     "long": "A pattern I see constantly: two professionals in their fifties, each earning a solid but not spectacular salary, who assume private investments are for other people.\n\nA nurse practitioner at $145,000 and an engineer at $170,000 have a joint income of $315,000. That is over the $300,000 joint income test. They have been accredited investors for years and nobody told them.\n\nAccredited status isn't about being rich. It's about clearing a line drawn in 1982. See where your household stands: {calculator_url}",
     "short": "A nurse practitioner at $145k + an engineer at $170k = $315k joint. That's over the accredited investor line, and has been for years. Nobody told them. Check your household: {calculator_url}",
     "tags": "#DualIncome #AccreditedInvestor #MoneyTalk"},
    {"topic": "What \"reasonable expectation\" means",
     "long": "The income test has a forward-looking piece: you need a \"reasonable expectation\" of reaching the same income level in the current year.\n\nThe SEC doesn't define it precisely, and that's deliberate. In practice: if you're in the same job at the same pay, you have it. If you retired in January, you don't. If you took a sabbatical, it depends on when you go back.\n\nIf income is borderline, the net worth test is often the cleaner path anyway. The calculator checks both: {calculator_url}",
     "short": "Income test fine print: you need a \"reasonable expectation\" of the same income this year. Same job, same pay: yes. Retired in January: no. Borderline? Net worth may be the cleaner path. {calculator_url}",
     "tags": "#AccreditedInvestor #InvestorEducation"},
    # ---- Week 4: the net worth test
    {"topic": "How to add up net worth the SEC way",
     "long": "Net worth for the accredited investor test is not what your banking app shows. Here's the SEC arithmetic:\n\nStart with all your assets: checking, savings, brokerage, IRAs, 401(k)s, pensions with a cash value, other real estate at market value, business interests, vehicles, anything you could sell.\n\nLeave out your primary home entirely.\n\nSubtract all your debts except the mortgage on that home (unless the mortgage exceeds the home's value, in which case the excess counts against you, and any home-equity loan taken in the last 60 days counts too).\n\nIf what's left is over $1 million, you're accredited. The calculator does this for you and keeps nothing: {calculator_url}",
     "short": "SEC net worth math: all assets, minus your primary home, minus all debts except that home's mortgage. Over $1M? You're accredited. The calculator does it and stores nothing: {calculator_url}",
     "tags": "#NetWorth #AccreditedInvestor #FinancialPlanning"},
    {"topic": "The 401(k) most people forget",
     "long": "Retirement accounts count toward the accredited investor net worth test, at full value, before taxes.\n\nThat surprises people. A 401(k) feels locked away, so they mentally exclude it. The SEC doesn't. A $600,000 401(k), a $250,000 IRA, and a $200,000 brokerage account is $1,050,000 of net worth before you count a single dollar outside retirement accounts.\n\nThe test is about capacity to bear risk, not liquidity. Whether you'd actually want to invest retirement money in a private fund is a separate question, and one to ask an adviser. Find out where you stand first: {calculator_url}",
     "short": "Retirement accounts count toward accredited net worth at full value, pre-tax. A $600k 401(k) + $250k IRA + $200k brokerage = $1.05M. Already over the line. {calculator_url}",
     "tags": "#401k #NetWorth #AccreditedInvestor"},
    {"topic": "Joint net worth with a spouse",
     "long": "You can meet the $1 million net worth test jointly with a spouse or spousal equivalent, and the assets don't have to be jointly titled.\n\nHer IRA plus his 401(k) plus the joint brokerage account plus the rental property in his name alone: all of it goes in one pile. Debts go in the same pile. If the total clears $1 million, both spouses are accredited, even if only one of them signs the investment.\n\nThis is the test that qualifies the most households who don't know it. Run yours together: {calculator_url}",
     "short": "The $1M net worth test can be met jointly with a spouse, and the assets don't need to be jointly titled. Her IRA + his 401(k) + the rental = one pile. Run it together: {calculator_url}",
     "tags": "#Couples #NetWorth #AccreditedInvestor"},
    # ---- Week 5: verification and process
    {"topic": "How a fund verifies you",
     "long": "Under Rule 506(c), a fund manager can't take your word that you're accredited. They have to verify it, and they're on the hook if they don't.\n\nWhat that looks like in practice: for the income test, two years of tax returns or W-2s plus a written statement about this year. For the net worth test, recent account statements and a credit report for the debt side. Or a letter from your CPA, attorney, or registered adviser confirming they've checked.\n\nIt happens once per investment, with the manager, after you've decided to invest. Nobody needs your statements just to show you what's out there. Start with the two-minute version: {calculator_url}",
     "short": "Rule 506(c) funds must verify you're accredited: tax returns, statements, or a CPA/attorney letter. That happens with the manager, once, after you decide to invest. The two-minute check comes first: {calculator_url}",
     "tags": "#Rule506c #AccreditedInvestor #DueDiligence"},
    {"topic": "What a PPM is",
     "long": "Every private fund hands new investors a document called a private placement memorandum, or PPM. It's often 80 to 150 pages, and most of it is risk factors.\n\nThat isn't a red flag. It's the law working as intended. Because the fund isn't registered with the SEC the way a mutual fund is, the disclosure has to happen in the document, and the manager's lawyer makes sure every conceivable risk is in there.\n\nThe sections worth reading first: the fees, the term (when the fund ends), what happens if you need your money early, and who the general partner is. If you're accredited, you'll see one of these eventually. Find out: {calculator_url}",
     "short": "Every private fund gives you a PPM: 80-150 pages, mostly risk factors. Not a red flag; that's the disclosure law working. Read the fees, the term, the exit rules, and who the GP is first. {calculator_url}",
     "tags": "#PPM #PrivateFunds #InvestorEducation"},
    {"topic": "The Form D you can look up",
     "long": "Here's a free due-diligence tool most investors never use: the SEC's EDGAR database.\n\nEvery private fund that raises money under Regulation D has to file a short notice called Form D within 15 days of its first sale. It's public. It lists the fund's name, the people behind it, the exemption it's relying on, how much it's trying to raise, and how much it has raised so far.\n\nIf a manager tells you about a fund and you can't find its Form D on EDGAR, ask why. Being accredited is the entry ticket; knowing where to look is the seatbelt. Start with the ticket: {calculator_url}",
     "short": "Free due diligence: every Reg D fund must file a public Form D with the SEC within 15 days of its first sale. Name, people, amount raised. Can't find it on EDGAR? Ask why. {calculator_url}",
     "tags": "#FormD #EDGAR #DueDiligence #AccreditedInvestor"},
    # ---- Week 6: risk and fit
    {"topic": "The honest downside",
     "long": "Private funds have real drawbacks, and anyone who skips them isn't doing you a favor.\n\nYour money is locked up, often for five to ten years. There's no daily price and no easy exit. Fees are higher than an index fund. Reporting is quarterly at best. The fund can lose money, including all of it, and no regulator reviewed the offering before you saw it.\n\nWhat you get in exchange is access to assets that don't trade publicly and a manager whose interests are, ideally, aligned with yours. Whether that trade is right for you is a question for your own adviser, not for a listing site. Knowing whether you're eligible is where it starts: {calculator_url}",
     "short": "Private funds, honestly: money locked 5-10 years, no daily price, higher fees, quarterly reporting, can lose everything, no regulator pre-reviewed it. Know that before you know if you're eligible: {calculator_url}",
     "tags": "#InvestingRisk #PrivateFunds #AccreditedInvestor"},
    {"topic": "How much of a portfolio",
     "long": "A common rule of thumb among advisers: private investments as a slice of a portfolio, not the plate.\n\nThe reasoning is liquidity. If ten percent of your money is locked in a fund with a seven-year term, and the other ninety percent is in things you can sell tomorrow, a bad year in the fund is survivable. If it's fifty percent, it isn't.\n\nThis isn't advice about your situation; that's what your own adviser is for. It's context for a decision you may not have known you were eligible to make. Check eligibility here: {calculator_url}",
     "short": "Advisers' rule of thumb: private investments are a slice, not the plate. A locked-up 10% is survivable in a bad year; 50% isn't. Context, not advice. Eligibility check: {calculator_url}",
     "tags": "#PortfolioAllocation #AccreditedInvestor #Diversification"},
    {"topic": "Six questions to ask any fund manager",
     "long": "Before wiring money into any private fund, six questions worth asking the manager directly:\n\n1. Who is the general partner, and what have they run before?\n2. What are all the fees: management, performance, acquisition, disposition, and anything else?\n3. When does the fund end, and what happens if it can't sell everything by then?\n4. How much of your own money is in it?\n5. Are the financials audited, and by whom?\n6. Has any principal ever been subject to a regulatory action?\n\nA good manager answers all six without flinching. A great one answers before you ask. You need to be accredited to be in the room: {calculator_url}",
     "short": "6 questions for any fund manager: Who's the GP? All the fees? When does it end? How much of your own money is in? Audited by whom? Any regulatory history? Good ones answer without flinching. {calculator_url}",
     "tags": "#DueDiligence #PrivateFunds #AccreditedInvestor"},
    # ---- Week 7: myths
    {"topic": "Myth: accredited means rich",
     "long": "Myth: you have to be rich to be an accredited investor.\n\nIn 1982, when the thresholds were set, $200,000 of income was rare and $1 million of net worth was rarer. Adjusted for inflation those figures would be roughly $650,000 and $3.2 million today. They were never adjusted.\n\nSo the definition drifted from \"wealthy\" to \"comfortable professional household near retirement.\" That's why one in five households now qualifies, and why so many of them have no idea. Two minutes: {calculator_url}",
     "short": "Myth: accredited = rich. The 1982 thresholds ($200k income, $1M net worth) would be ~$650k and ~$3.2M today if adjusted. They weren't. Now 1 in 5 households qualifies. {calculator_url}",
     "tags": "#AccreditedInvestor #Inflation #MoneyMyths"},
    {"topic": "Myth: you have to apply",
     "long": "Myth: there's an application, a registry, or a card for accredited investors.\n\nThere isn't. You are accredited the moment your income or net worth meets the definition, and you stop being accredited the moment it doesn't. Nobody tracks it. Each fund verifies you fresh, on the day you invest.\n\nThat's why the first step is simply knowing. A two-minute check that keeps nothing you enter: {calculator_url}",
     "short": "Myth: there's an accredited investor registry or card. There isn't. You're accredited when you meet the definition, and each fund verifies you fresh when you invest. Step one is knowing: {calculator_url}",
     "tags": "#AccreditedInvestor #InvestorEducation"},
    {"topic": "Myth: private funds are for insiders",
     "long": "Myth: private funds are only for people with the right connections.\n\nThat was true for decades, because the law forbade advertising. A fund could only raise from people the manager already knew. If you weren't in the room, you weren't in the fund.\n\nRule 506(c), since 2013, lets funds advertise to anyone and accept anyone who's verified accredited. The room is bigger now. Whether you're allowed in comes down to a definition, not a Rolodex: {calculator_url}",
     "short": "Myth: private funds are for insiders. Was true when advertising was illegal. Since 2013, Rule 506(c) funds can advertise to anyone and accept anyone verified accredited. Definition, not Rolodex: {calculator_url}",
     "tags": "#Rule506c #PrivateFunds #AccreditedInvestor"},
    # ---- Week 8: the fund types, one each
    {"topic": "Real estate funds in plain English",
     "long": "A private real estate fund is a pool of investor money that buys property a single investor couldn't: a 200-unit apartment complex, a portfolio of self-storage facilities, a distribution warehouse.\n\nYou own a share of the fund, not the building. The manager buys, operates, and eventually sells. Along the way you may get distributions from rent; at the end you get your share of the sale proceeds, whatever they turn out to be.\n\nTypical terms run five to ten years. Minimums often start at $25,000 to $100,000. Accredited investors only, in most cases. Are you one? {calculator_url}",
     "short": "Private real estate fund, plainly: pooled money buys buildings you couldn't alone. You own a share of the fund, not the building. 5-10 year terms, $25k-$100k minimums, accredited only. {calculator_url}",
     "tags": "#RealEstateInvesting #PrivateFunds #AccreditedInvestor"},
    {"topic": "Business acquisition funds in plain English",
     "long": "Ten thousand American small-business owners turn 65 every week, and most don't have a succession plan. A business acquisition fund exists to buy those companies.\n\nThe fund pools investor money, buys a few plumbing companies, or dental practices, or landscaping firms, professionalizes them, and sells the group to a larger buyer years later. Investors own a share of the fund.\n\nIt's a longer game than real estate, typically seven to ten years, and the risk is operational: can the manager actually run a business? Accredited investors only, almost always. Check: {calculator_url}",
     "short": "Business acquisition funds buy small companies from retiring founders (10,000 owners turn 65 every week), run them, and sell the group later. 7-10 year terms. Accredited only. {calculator_url}",
     "tags": "#SmallBusiness #PrivateEquity #AccreditedInvestor"},
    {"topic": "Private credit in plain English",
     "long": "When a bank says no to a business loan, the borrower often turns to a private credit fund.\n\nThe fund pools investor money and lends it out: to a developer finishing a building, a company bridging a slow quarter, a franchisee opening a third location. The fund collects interest and, at the end of the loan, the principal. Investors own a share of the fund and typically receive regular income from the interest.\n\nThe risk is straightforward: borrowers can default. Terms are usually shorter than equity funds, three to five years. Accredited investors only. See where you stand: {calculator_url}",
     "short": "Private credit fund, plainly: pooled money lends where banks won't, collects interest, returns principal. Regular income, default risk, 3-5 year terms. Accredited only. {calculator_url}",
     "tags": "#PrivateCredit #IncomeInvesting #AccreditedInvestor"},
    # ---- Week 9: life stage
    {"topic": "The 55-year-old who just found out",
     "long": "A story I hear in different forms every week.\n\nShe's 55, a hospital administrator. He's 58, sells industrial equipment. Together they earn about $290,000. The house is nearly paid off. Between them they have $1.4 million in retirement accounts and a $180,000 brokerage account.\n\nThey have never once been offered a private investment, and assumed that was because they weren't the type.\n\nThey have been accredited investors for at least a decade. On net worth alone, easily. The only thing missing was knowing. {calculator_url}",
     "short": "She's 55, he's 58. $290k joint income, $1.4M in retirement accounts, house nearly paid off. Never been offered a private investment. They've been accredited for a decade. Only thing missing: knowing. {calculator_url}",
     "tags": "#RetirementPlanning #AccreditedInvestor #GenX"},
    {"topic": "Accredited after the kids leave",
     "long": "Two things tend to happen in the five years after the last child leaves home: expenses drop, and savings rates jump.\n\nThat's the window in which a lot of households cross the accredited investor line without noticing. The 401(k) balances that felt abstract at 45 are suddenly large at 55. The mortgage is small. The brokerage account has compounded.\n\nIf it's been a few years since you last added everything up, the answer may have changed. Two minutes, nothing stored: {calculator_url}",
     "short": "The 5 years after the last kid leaves: expenses drop, savings jump, and a lot of households cross the accredited line without noticing. Been a while since you added it up? {calculator_url}",
     "tags": "#EmptyNest #AccreditedInvestor #FinancialPlanning"},
    {"topic": "Recently retired? You may still qualify",
     "long": "Retirement usually ends the income path to accredited status. It rarely ends the net worth path.\n\nThe income test needs current earnings. The net worth test only needs $1 million outside your home, and retirement accounts count in full. A retiree with $900,000 in an IRA and $200,000 in a brokerage account is accredited, with no salary at all.\n\nWhether a retiree should tie money up in a private fund for years is a different and serious question for an adviser. Whether they're eligible to consider it is a two-minute one: {calculator_url}",
     "short": "Retired? The income path to accredited status closes; the net worth path doesn't. $900k IRA + $200k brokerage = accredited, no salary needed. Eligibility is the easy question; ask an adviser the hard one. {calculator_url}",
     "tags": "#Retirement #AccreditedInvestor #NetWorth"},
    # ---- Week 10: how Luminaz fits (light touch)
    {"topic": "What a listing site is, and isn't",
     "long": "A fund listing site does one thing: it lets you see private funds that are raising money, all in one place, without needing to know the manager personally.\n\nIt does not pick funds for you, rank them, or tell you which is good. If it did, it would be giving investment advice, and that requires a license and a relationship it doesn't have with you.\n\nSo the right way to use one: browse, read what the manager wrote, ask for their documents, and take those documents to your own adviser. Luminaz is built that way on purpose. Eligibility first: {calculator_url}",
     "short": "A fund listing site shows you private funds raising money in one place. It doesn't rank them or tell you which is good; that would be advice. Browse, request documents, take them to your adviser. {calculator_url}",
     "tags": "#PrivateFunds #InvestorEducation #Luminaz"},
    {"topic": "Why investors never pay on Luminaz",
     "long": "Investors will never pay a fee on Luminaz. Not to browse, not to shortlist, not to request a fund's documents.\n\nThe reason is simple: the moment a site charges investors, it has an incentive to keep them excited. We'd rather you show up when you have a real question, look calmly, and leave if nothing fits.\n\nFund managers pay a flat monthly fee to be listed, the same whether ten investors look or ten thousand, and Luminaz never takes a cut of anything you invest. Start with whether you're eligible: {calculator_url}",
     "short": "Investors never pay on Luminaz. Sites that charge investors need to keep them excited; we'd rather you look calmly and leave if nothing fits. Managers pay a flat listing fee; we never take a cut of your investment. {calculator_url}",
     "tags": "#Luminaz #AccreditedInvestor #Transparency"},
    {"topic": "Your name stays yours",
     "long": "On most investment platforms, your contact information is the product. Sign up, and the calls start.\n\nOn Luminaz, a fund manager learns your name exactly once: when you click \"Request materials\" on their fund. Shortlisting is anonymous. Browsing is anonymous. We don't sell the list, rent the list, or share the list.\n\nThe calculator works the same way: it keeps your result and your email so we can tell you when the catalog opens. The numbers you type are gone the moment the page loads. {calculator_url}",
     "short": "On Luminaz a manager learns your name once: when you request their documents. Browsing and shortlisting are anonymous. No list is sold, ever. {calculator_url}",
     "tags": "#Privacy #AccreditedInvestor #Luminaz"},
    # ---- Week 11: money conversations
    {"topic": "The conversation to have with your adviser",
     "long": "If you find out you're an accredited investor, the next conversation isn't with a fund manager. It's with whoever already advises you on money.\n\nThree questions worth bringing: Given my timeline, how much could I afford to have locked up for seven years? What would a private investment do to my overall risk? And, if I find something interesting, will you read the offering documents with me?\n\nAn adviser who's never been asked those questions will usually be glad you did. Bring them the eligibility answer first: {calculator_url}",
     "short": "Found out you're accredited? Next call is your adviser, not a fund manager. Ask: how much can I lock up for 7 years, what does it do to my risk, will you read the documents with me? {calculator_url}",
     "tags": "#FinancialAdvisor #AccreditedInvestor #InvestorEducation"},
    {"topic": "The spouse conversation",
     "long": "Because accredited status can be met jointly, it's often a household decision before it's an investment decision.\n\nA useful way to start: not \"should we invest in a private fund\" but \"did you know we qualify to look?\" Most couples have never had that conversation because neither of them knew there was anything to discuss.\n\nRun the calculator together. It takes two minutes and keeps nothing but the result: {calculator_url}",
     "short": "Accredited status is often met jointly, so it's a household conversation first. Not \"should we invest\" but \"did you know we qualify to look?\" Run it together: {calculator_url}",
     "tags": "#Couples #MoneyTalk #AccreditedInvestor"},
    {"topic": "Why nobody told you",
     "long": "If one in five households is accredited, why don't they know?\n\nBecause nobody's job is to tell them. A brokerage earns nothing when you invest privately. A 401(k) provider earns nothing. Until 2013 fund managers couldn't advertise, so they never learned to reach strangers. And the SEC publishes the definition but doesn't send letters.\n\nThe result: a category of investing that most eligible people have never been shown. That's the gap Luminaz exists to close, starting with a two-minute check: {calculator_url}",
     "short": "1 in 5 households is accredited. Why don't they know? Brokerages earn nothing telling you. 401(k) providers earn nothing. Funds couldn't advertise until 2013. Nobody's job to tell you. Until now: {calculator_url}",
     "tags": "#AccreditedInvestor #FinancialLiteracy #Luminaz"},
    # ---- Week 12: recap and definitions
    {"topic": "Closed-end, defined",
     "long": "A term worth knowing before you read any fund's documents: closed-end.\n\nA closed-end fund raises money for a set period, invests it, and has a defined end date, often five to ten years, when it sells everything and returns whatever is left to investors. You can't usually get out early, and the fund can't usually take new money after it closes.\n\nThe alternative, an open-ended or evergreen fund, lets investors come and go and never winds down. Different animal, different risks. Luminaz lists only closed-end funds, because a defined end date is the plainest promise a manager can make. Eligibility: {calculator_url}",
     "short": "Closed-end fund: raises for a set period, invests, ends on a defined date and returns what's left. No early exit, no new money after close. A defined end date is the plainest promise a manager can make. {calculator_url}",
     "tags": "#ClosedEndFund #PrivateFunds #InvestorEducation"},
    {"topic": "General partner, limited partner",
     "long": "Two words you'll see on every private fund document: general partner and limited partner.\n\nThe general partner, or GP, is the manager. They make the decisions, run the fund, and are personally on the hook for its obligations.\n\nThe limited partners, or LPs, are the investors. Their liability is limited to what they put in. They don't manage anything.\n\nWhen you invest in a private fund, you become an LP. The single most important due-diligence question is therefore about the GP: who are they, and what have they done before? Eligibility to ask: {calculator_url}",
     "short": "GP = the manager, makes decisions, personally on the hook. LP = the investors, liability limited to what they put in. You'd be an LP. So the biggest question is always about the GP. {calculator_url}",
     "tags": "#GeneralPartner #LimitedPartner #PrivateFunds"},
    {"topic": "The two-minute recap",
     "long": "Everything about accredited investor status, in one post:\n\n- It's a definition, not a license. Nobody issues it.\n- Income: $200,000 two years running, or $300,000 jointly, and expected again this year.\n- Net worth: $1 million, not counting your home, retirement accounts included, jointly with a spouse if you like.\n- Or a Series 7, 65, or 82 license.\n- Meeting one test is enough.\n- About one in five US households qualifies. Most don't know.\n- It opens the door to private funds. It doesn't tell you whether to walk through.\n\nTwo minutes, nothing stored: {calculator_url}",
     "short": "Accredited investor in one post: a definition, not a license. $200k income (2 yrs) or $300k joint, OR $1M net worth minus your home (401k counts), OR a Series 7/65/82. One is enough. 1 in 5 qualify. {calculator_url}",
     "tags": "#AccreditedInvestor #Recap #FinancialLiteracy"},
    # ---- Week 13: family offices (added 22 October 2026, change 32: Diane's decision to market to family offices)
    {"topic": "The family office nobody calls a family office",
     "long": "If one person decides where a family's money goes, that family runs a family office. Most of them never use the term.\n\nA couple with a sold business, a doctor's household with $8 million in accounts, three siblings managing what their parents left: all of them make allocation decisions, and all of them pass the accredited investor test by a wide margin. Many also pass the higher \"qualified purchaser\" line at $5 million in investments.\n\nWhat they usually lack is not access. It is a quiet place to read about private funds without a salesperson on the line. See where your household stands: {calculator_url}",
     "short": "One person deciding where a family's money goes is a family office, whatever it's called. Most pass the accredited test by a wide margin. What they lack is a quiet place to read, not access. {calculator_url}",
     "tags": "#FamilyOffice #AccreditedInvestor #PrivateFunds"},
    {"topic": "What a $20 million family sees that a $2 million investor doesn't",
     "long": "The filings are the same. Every private fund that advertises files the same public notice, and anyone can read it.\n\nThe difference is time and curation. A larger family office has someone whose job is to read a hundred offerings and keep five. A smaller one has an evening a week.\n\nThat is what a listing site is for: a small number of funds at a time, in the order they were listed, described in plain words, with the offering documents one click away. Free to read. Nobody ranks them for you, because nobody should. Start here: {calculator_url}",
     "short": "The filings are the same for every investor. The difference is time to read them. A listing site shows a few funds at a time, in plain words, documents one click away, nobody ranking them. {calculator_url}",
     "tags": "#FamilyOffice #PrivateFunds #AccreditedInvestor"},
    {"topic": "Why a flat-fee listing site has no reason to push a fund at you",
     "long": "Ask any platform one question: what happens to its revenue when you invest?\n\nOn Luminaz, nothing. Fund managers pay a flat monthly fee to be listed. Luminaz takes no success fee, no share of your investment, no fee per introduction, and it never ranks or recommends a fund. It describes funds and leaves the deciding to you.\n\nFor a family office that does its own diligence, that is the whole point: a source with no reason to steer you. The rules in full, including what Luminaz does not do: {calculator_url}",
     "short": "Ask any platform what happens to its revenue when you invest. On Luminaz: nothing. Managers pay a flat listing fee; no success fee, no ranking, no recommending. We list; you decide. {calculator_url}",
     "tags": "#FamilyOffice #Transparency #PrivateFunds"},
    {"topic": "The questions a family office asks before it wires",
     "long": "A family office that has done this before asks the same questions every time, in the same order.\n\nWho verifies my accredited status, and how? What does the offering memorandum say about fees, the waterfall, and the term? Who is the administrator, and who audits? Where is the Form D, and what does BrokerCheck say about the people? What happens if I need liquidity early, and what does it cost?\n\nEvery one of those answers lives in documents the manager must give you, and every public record can be checked by you in an evening. A listing site should make the asking easy and never answer for the manager. Where to start: {calculator_url}",
     "short": "Before wiring, the experienced family office asks: who verifies me, what are the fees and the waterfall, who administers and audits, where is the Form D, what does BrokerCheck say, what if I need out early. Start here: {calculator_url}",
     "tags": "#FamilyOffice #DueDiligence #PrivateFunds"},
]

DISCLAIMER = "Luminaz describes funds and never recommends them. This is education, not investment advice; talk to your own adviser before investing in any private fund."

SLOTS = ["Monday", "Wednesday", "Friday"]


# ---------------------------------------------------------------- posts by purpose (change 28, 21 October 2026)
# Three purposes, each on its own weekdays (Settings): "investors" draws from POSTS above, "managers" from
# MANAGER_POSTS below, "webinars" from WEBINAR_TEMPLATES for any open webinar in the next two weeks.
# {manager_url} and {signup_url} are filled at send time with a ?src= tag for the platform, like {calculator_url}.
# Every line obeys rules 4.2, 4.5 and 4.10: a flat fee, "self-attested" never "verified", and never that
# Luminaz finds, delivers, matches or introduces investors. A founder approves every post before it goes out.

MANAGER_POSTS = [
    {"topic": "What raising capital really costs",
     "hook": "Most emerging fund managers pay for capital three times.",
     "long": "Most emerging fund managers pay for capital three times.\n\nFirst, a placement agent, at 2 to 5 percent of what they raise. Second, paid leads, at $150 to $480 a name for people who may or may not be accredited. Third, their own hours: the calls, the follow-ups, the decks.\n\nLuminaz is a different kind of cost: a flat monthly fee for a listing that accredited investors can browse. No success fee. No fee per investor. Nothing changes hands when a fund closes.\n\nIt is not a sales team, and it never claims to be one. It is a place to be found. How a listing works: {manager_url}",
     "short": "Placement agents: 2 to 5 percent of the raise. Paid leads: $150 to $480 a name. Luminaz: a flat monthly fee for a listing, no success fee. How it works: {manager_url}",
     "tags": "#FundManagers #PrivateFunds #CapitalRaising"},
    {"topic": "Four gates before a listing goes live",
     "hook": "No fund is listed on Luminaz because someone paid.",
     "long": "No fund is listed on Luminaz because someone paid.\n\nFour things happen first: the manager signs the listing agreement, a person at Luminaz records a Rule 506(d) bad-actor check, Luminaz reviews the listing against a written checklist, and the manager gives the final Publish click.\n\nAll four, every time, in that order. A later failed check closes the gate again.\n\nThe fee pays for the listing and the review work. It buys no place in line and no badge. What the checklist covers: {manager_url}",
     "short": "Four gates before a fund goes live on Luminaz: signed agreement, a recorded 506(d) check, a written review, your own Publish click. The fee buys none of them. {manager_url}",
     "tags": "#FundManagers #Rule506c #Compliance"},
    {"topic": "Ten listings at a time, and the line",
     "hook": "Luminaz shows ten funds at a time. Nobody can buy a place in line.",
     "long": "Luminaz shows ten funds at a time. Nobody can buy a place in line.\n\nWhen all ten slots are taken, a manager who clicks Publish joins the line, in the order of the clicks. When a listing closes, the first fund in line goes live by itself and the manager gets an email. Waiting costs nothing.\n\nTen is a deliberate number. An investor can read ten listings in an evening. A hundred becomes a search engine, and search engines rank, which Luminaz will never do. The rules in plain words: {manager_url}",
     "short": "Luminaz lists ten funds at a time. Publish while all ten are taken and you join the line, in click order, free. First in line goes live by itself when a slot opens. {manager_url}",
     "tags": "#FundManagers #PrivateFunds #Luminaz"},
    {"topic": "The first ten funds list free",
     "hook": "While Luminaz starts up, the first ten funds to go live list free.",
     "long": "While Luminaz starts up, the first ten funds to go live list free.\n\nThat is not a discount for results and it does not depend on how many investors look. It is granted because of when a manager joined, while the audience is still being built, and the listing agreement says so in those words.\n\nAfter the tenth fund, the price is the standard flat monthly fee, billed at the end of each month for the days a listing was live. Paused days are never charged. Where the count stands today: {manager_url}",
     "short": "The first ten funds to go live on Luminaz list free while the platform starts up. Granted for joining early, never for results. Where the count stands: {manager_url}",
     "tags": "#FundManagers #FoundingFunds #PrivateFunds"},
    {"topic": "No projections on a listing",
     "hook": "A Luminaz listing has no field for future performance. On purpose.",
     "long": "A Luminaz listing has no field for future performance. On purpose.\n\nNo rate-of-return figure, no \"projected\" anything, and no comparison with other funds. Those numbers belong in your offering documents, where your counsel wrote them with the right context and the right warnings.\n\nWhat a listing does show: the strategy in plain words, the category, the minimum, the term, the principals, and a button an accredited investor can click to ask you for the documents. Luminaz describes funds and never recommends them. See a sample listing: {manager_url}",
     "short": "A Luminaz listing has no field for future performance, not one number. Those belong in your PPM. The listing shows strategy, category, minimum, term, principals, and a request button. {manager_url}",
     "tags": "#FundManagers #Compliance #PrivateFunds"},
    {"topic": "You verify. Luminaz does not.",
     "hook": "Under Rule 506(c), verifying an investor is your job. Luminaz never claims to do it for you.",
     "long": "Under Rule 506(c), verifying an investor is your job. Luminaz never claims to do it for you.\n\nAn investor on Luminaz self-attests to the basis of their accreditation. Luminaz passes that word along as exactly that: self-attested. It never tells a manager that someone is verified or qualified, because it has not checked, and the rule puts the check on you.\n\nContact reaches you at one moment only: when an investor clicks Request materials. Then it is your process, your verification, your documents. How requests work: {manager_url}",
     "short": "Rule 506(c): the manager verifies. Luminaz tells you an investor is self-attested, never verified. Contact reaches you only when someone clicks Request materials. {manager_url}",
     "tags": "#Rule506c #FundManagers #AccreditedInvestors"},
    {"topic": "What a listing shows, and who sees what",
     "hook": "A fund manager on Luminaz sees counts. An investor sees listings. Nobody sees a list of names.",
     "long": "A fund manager on Luminaz sees counts. An investor sees listings. Nobody sees a list of names.\n\nInvestors can shortlist a fund or watch it. The manager sees how many did, not who. A name and an email reach a manager only when that investor clicks Request materials, and then only that manager.\n\nLuminaz does not sell data, runs no third-party trackers, and keeps your fund documents visible to its review desk only. The privacy rules in full: {manager_url}",
     "short": "On Luminaz, managers see counts, investors see listings, and a name reaches a manager only when that investor clicks Request materials. No data sold, no trackers. {manager_url}",
     "tags": "#FundManagers #Privacy #PrivateFunds"},
    {"topic": "Pause when you are full",
     "hook": "Fully subscribed for now? Pause the listing. Paused days cost nothing.",
     "long": "Fully subscribed for now? Pause the listing. Paused days cost nothing.\n\nA paused listing stays visible with a plain label and takes no requests, so an investor who found you knows you exist and knows to wait. Resume when you reopen. Close for good and the final month is prorated by the day.\n\nNo lock-in, no minimum term, no cancellation fee. The flat monthly fee covers the days you were live and nothing else. The billing rules: {manager_url}",
     "short": "Fully subscribed? Pause your Luminaz listing: it stays visible, takes no requests, and paused days are never charged. Close for good and the last month is prorated by the day. {manager_url}",
     "tags": "#FundManagers #PrivateFunds #Luminaz"},
    {"topic": "What a month costs, in one number",
     "hook": "One percent of a $5 million raise is $50,000. A month on Luminaz is a flat fee.",
     "long": "One percent of a $5 million raise is $50,000. A month on Luminaz is a flat fee.\n\nThe listing fee is published on the manager page, billed at the end of each month for the days a listing was live, and it is the whole price. Luminaz takes nothing when you close, nothing per investor, nothing per request.\n\nThat is not generosity. A fee tied to your raise would make Luminaz something other than a listing platform, and it has chosen not to be that. The price and the rules: {manager_url}",
     "short": "One percent of a $5M raise is $50,000. A month on Luminaz is one flat fee, billed for live days, and that is the whole price. Nothing when you close. {manager_url}",
     "tags": "#FundManagers #CapitalRaising #PrivateFunds"},
    {"topic": "Your Form D is public",
     "hook": "The day you file Form D, anyone can see that you are raising. Make it work for you.",
     "long": "The day you file Form D, anyone can see that you are raising. Make it work for you.\n\nA fund that relies on Rule 506(c) may advertise generally, as long as every investor who gets in is verified as accredited. The filing is the first signal; where you are listed is the second.\n\nA Luminaz listing is one place accredited investors can read your strategy in plain words and ask for your documents. It does not replace your own outreach, your counsel, or your verification file. It sits beside them. What goes on a listing: {manager_url}",
     "short": "Filed Form D under 506(c)? You may advertise generally, and you must verify every investor. A Luminaz listing is one more place to be read, beside your own outreach. {manager_url}",
     "tags": "#FormD #Rule506c #FundManagers"},
    {"topic": "Why a flat fee",
     "hook": "Luminaz is not a broker-dealer. The price is designed to keep it that way.",
     "long": "Luminaz is not a broker-dealer. The price is designed to keep it that way.\n\nIt takes no fee tied to a raise, handles no investor money, passes no subscription documents, and never ranks or recommends a fund. Those are not features it forgot to build. They are the lines that make a flat listing fee the right price.\n\nFor a manager, that means a predictable monthly cost and a platform that stays out of your deal. The rules Luminaz holds itself to: {manager_url}",
     "short": "Luminaz is not a broker-dealer: no fee tied to a raise, no investor money, no ranking, no recommending. That is why the price is a flat listing fee. {manager_url}",
     "tags": "#FundManagers #PrivateFunds #Luminaz"},
    {"topic": "Who Luminaz is for",
     "hook": "Independent managers raising under 506(c): real estate, business acquisition, private credit, venture, energy.",
     "long": "Independent managers raising under 506(c): real estate, business acquisition, private credit, venture, energy.\n\nClosed-end or evergreen, first fund or fifth. Not REITs, not Reg A offerings, not 506(b) funds, which cannot advertise.\n\nIf that is you, the listing form takes about twenty minutes, your documents are seen by the review desk only, and you give the final click before anything goes live. Start here: {manager_url}",
     "short": "Luminaz is for independent 506(c) managers: real estate, business acquisition, private credit, venture, energy. Not REITs, not Reg A, not 506(b). Start here: {manager_url}",
     "tags": "#FundManagers #Rule506c #PrivateFunds"},
    {"topic": "Family offices with a fund of their own",
     "hook": "A family office that sponsors its own fund lists at the same flat fee as everyone else.",
     "long": "A family office that sponsors its own fund lists at the same flat fee as everyone else.\n\nSame four gates, same monthly fee per fund, same rule that nothing goes live until the sponsor gives the final click. A placement agent bringing a client's fund is welcome on the same terms: the fund's manager signs the listing agreement, the invoice can go to whoever pays, and Luminaz takes nothing from the agent and pays the agent nothing.\n\nOne price, one set of rules, whoever brings the fund. Where to start: {manager_url}",
     "short": "A family office sponsoring its own fund, or a placement agent bringing a client's fund: same four gates, same flat monthly fee, same final click by the manager. One price, whoever brings the fund. {manager_url}",
     "tags": "#FamilyOffice #FundManagers #PrivateFunds"},
]

MANAGER_DISCLAIMER = ("Luminaz is a technology and listing platform, not a broker-dealer or investment adviser. "
                      "It charges a flat listing fee, takes no fee tied to any raise, and does not verify accredited status; "
                      "the fund manager does, under Rule 506(c).")

# Webinar posts: filled with a webinar's title, date and sign-up link when it is open and within the next
# two weeks. "announce" early, "last_call" inside the final three days. One of each per webinar.
WEBINAR_TEMPLATES = {
    "investors": {
        "announce": {"topic": "Webinar: {title}",
                     "hook": "Fifteen minutes on how private funds work. Free, and no fund is pitched.",
                     "long": "Fifteen minutes on how private funds work. Free, and no fund is pitched.\n\n{title}\n{when}\n\nWhat a private fund is, who is allowed to invest, how verification works, and the questions to ask before you wire a dollar. No returns talk, no specific funds, no sales pitch at the end.\n\nSave a seat: {signup_url}",
                     "short": "Free 15-minute webinar: {title}, {when}. How private funds work, who can invest, what to ask first. No fund pitched. Seats: {signup_url}",
                     "tags": "#AccreditedInvestor #Webinar #PrivateFunds"},
        "last_call": {"topic": "Last call: {title}",
                      "hook": "Last call for {title}.",
                      "long": "Last call for {title}.\n\n{when}. Fifteen minutes, free, no fund pitched: how private funds work and what to ask before you invest in one.\n\nSave a seat: {signup_url}",
                      "short": "Last call: {title}, {when}. Fifteen free minutes on how private funds work. Seats: {signup_url}",
                      "tags": "#AccreditedInvestor #Webinar"},
    },
    "managers": {
        "announce": {"topic": "Webinar for fund managers: {title}",
                     "hook": "For managers raising under 506(c): fifteen minutes on what raising capital really costs.",
                     "long": "For managers raising under 506(c): fifteen minutes on what raising capital really costs.\n\n{title}\n{when}\n\nWhat placement agents and paid leads cost, what a flat-fee listing is and is not, and what Luminaz checks before a fund goes live. Questions welcome.\n\nSave a seat: {signup_url}",
                     "short": "Fund managers: {title}, {when}. Fifteen minutes on what raising capital really costs and how a flat-fee listing works. Seats: {signup_url}",
                     "tags": "#FundManagers #Webinar #CapitalRaising"},
        "last_call": {"topic": "Last call for fund managers: {title}",
                      "hook": "Last call for {title}.",
                      "long": "Last call for {title}.\n\n{when}. Fifteen minutes for fund managers raising under 506(c): what raising capital really costs and how a flat-fee listing works.\n\nSave a seat: {signup_url}",
                      "short": "Last call, fund managers: {title}, {when}. Fifteen minutes on what raising capital really costs. Seats: {signup_url}",
                      "tags": "#FundManagers #Webinar"},
    },
}


def hook_for(long_text):
    """The first line a reader sees: the first sentence of the post, at most 120 characters."""
    first = (long_text or "").strip().split("\n")[0].strip()
    for mark in (". ", "? ", "! "):
        cut = first.find(mark)
        if 0 < cut < 120:
            return first[:cut + 1]
    return first[:120]
