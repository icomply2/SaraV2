"""Compliance check catalogue for SARA pre-vet workflows."""

from copy import deepcopy


SOA_PREVET_CHECKS = [
    {
        "index": 1,
        "testId": "SOA-01",
        "title": "1 - Summary of the Advice",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Summary of the Advice",
        "auditQuestion": "Summary of the Advice",
        "message": "Summarise the Statement of Advice under objectives, scope, strategy recommendations, product recommendations, insurance recommendations where applicable, and disclosure.",
        "passCriteria": "The SOA can be summarised clearly across objectives, scope, strategy recommendations, product recommendations, insurance recommendations where applicable, and fee/disclosure sections.",
        "reviewCriteria": "The SOA contains some relevant sections but the summary is incomplete, unclear, internally inconsistent, or key advice areas require human confirmation.",
        "failCriteria": "The SOA is missing core advice content or cannot be reliably summarised from the document provided.",
    },
    {
        "index": 2,
        "testId": "SOA-02",
        "title": "2 - Objectives",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Identifying customer's objectives: s961B(2)(a)",
        "auditQuestion": "Did the adviser adequately identify the objectives of the customer? Did the customer file pass or fail this step? Why/Why not?",
        "message": "Check whether the SOA identifies the client's objectives disclosed through instructions, including whether objectives are specific, measurable, prioritised and client-relevant.",
        "passCriteria": "The SOA identifies the client's objectives in specific, measurable and client-relevant terms, preferably in the client's own words or with clear context.",
        "reviewCriteria": "Objectives are present but generic, not prioritised, not measurable, or only partly connected to the advice.",
        "failCriteria": "The SOA does not identify the client's objectives, or the stated objectives are too generic to support the advice.",
    },
    {
        "index": 3,
        "testId": "SOA-03",
        "title": "3 - Financial Situation",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": "Fact Find"},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Identifying customer's financial situation and needs: s961B(2)(a)",
        "auditQuestion": "Did the adviser identify the financial situation and needs of the customer? Did the customer file pass or fail this step? Why/Why not?",
        "message": "Check personal circumstances, occupation, health, income, expenses, cashflow, assets, liabilities, superannuation, pensions, insurance and needs.",
        "passCriteria": "The SOA identifies relevant personal circumstances, income, expenses, assets, liabilities, cashflow, superannuation, pensions, insurance and needs sufficient to support the advice.",
        "reviewCriteria": "Some financial information is provided but key details are incomplete, stale, inconsistent, or need confirmation.",
        "failCriteria": "The SOA does not adequately identify the client's financial situation and needs.",
    },
    {
        "index": 4,
        "testId": "SOA-04",
        "title": "4 - Risk Profile",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": "Risk Profile Questionnaire"},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Identifying customer's risk profile: s961B(2)(a)",
        "auditQuestion": "Has the adviser identified the clients risk profile? Did the customer file pass or fail this step? Why/Why not?",
        "message": "Check whether the SOA identifies the client's risk profile and whether it is appropriate for the client's circumstances, assets, income and timeframe.",
        "passCriteria": "The SOA identifies the client's risk profile and the profile appears appropriate having regard to age, assets, income, investment timeframe and circumstances.",
        "reviewCriteria": "A risk profile is stated but the basis or appropriateness is unclear.",
        "failCriteria": "No risk profile is identified, or the profile appears materially inconsistent with the client's circumstances.",
    },
    {
        "index": 5,
        "testId": "SOA-05",
        "title": "5 - Subject Matter",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Identifying the subject matter and scope of the advice sought by customer's: s961B(2)(b)(i)",
        "auditQuestion": "Did the adviser identify the subject matter of the advice sought by the client? Did the customer file pass or fail this step? Why/Why not?",
        "message": "Check the agreed scope of advice, any limitations, why limitations were applied, and whether all recommendations stay within scope.",
        "passCriteria": "The SOA clearly identifies the subject matter and scope of advice, any limitations, and recommendations stay within that scope.",
        "reviewCriteria": "Scope is present but limitations, exclusions or recommendation boundaries are unclear.",
        "failCriteria": "The SOA does not identify scope, or recommendations appear outside the agreed scope.",
    },
    {
        "index": 6,
        "testId": "SOA-06",
        "title": "6 - Open a Self Managed Super Fund",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Opening a Self Managed Super Fund", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Opening a SMSF s961B(2)(f)",
        "auditQuestion": "Where a financial adviser makes a recommendation to open a self-managed super fund, does the Statement of Advice clearly explain how the SMSF is appropriate for the client? Did the customer file pass or fail this step? Why/Why not?",
        "message": "If SMSF establishment is recommended, check suitability, balance and cost effectiveness, trustee duties, client capability, diversification, and any LRBA/gearing implications.",
        "passCriteria": "If SMSF establishment is recommended, the SOA explains suitability, trustee duties, cost effectiveness, client capability, diversification and any LRBA/gearing implications. If no SMSF advice is given, this is not applicable.",
        "reviewCriteria": "SMSF advice is present but suitability, trustee obligations, costs, diversification or LRBA matters require human confirmation.",
        "failCriteria": "SMSF establishment is recommended without adequate evidence that it is appropriate for the client.",
    },
    {
        "index": 7,
        "testId": "SOA-07",
        "title": "7 - Gearing Advice",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Gearing Advice incl LRBA", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Appropriate Gearing Advice s961B(2)(f)",
        "auditQuestion": "Where a financial adviser has provided gearing advice, does the Statement of Advice clearly explain how the gearing advice is appropriate for the client? Did the customer file pass or fail this step? Why/Why not?",
        "message": "If gearing is recommended, check LVR, risk profile, contingency plan, cashflow serviceability, interest-rate stress, insurance considerations and ongoing advice.",
        "passCriteria": "If gearing is recommended, the SOA addresses LVR, risk profile, contingency planning, cashflow serviceability, insurance considerations and ongoing advice. If no gearing advice is given, this is not applicable.",
        "reviewCriteria": "Gearing advice is present but one or more suitability factors are unclear or need confirmation.",
        "failCriteria": "Gearing is recommended without adequate evidence of suitability, serviceability, risk alignment or risk mitigation.",
    },
    {
        "index": 8,
        "testId": "SOA-08",
        "title": "8 - Product Recommendation",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Product Recommendations", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Recommending a financial product: s961B(2)(e)",
        "auditQuestion": "Where a financial product is recommended, does the Statement of Advice clearly explain how the product meets the client objective? Did the customer file pass or fail this step? Why/Why not?",
        "message": "Where a superannuation or investment product is recommended, check whether it is reasonable and whether the SOA explains how it meets the client's objectives and needs.",
        "passCriteria": "Where a superannuation or investment product is recommended, the SOA clearly explains why the product is suitable and how it meets the client's objectives and needs.",
        "reviewCriteria": "A product recommendation is made but the link to objectives, needs or suitability is incomplete or generic.",
        "failCriteria": "A product is recommended without a clear explanation of why it is suitable for the client.",
    },
    {
        "index": 9,
        "testId": "SOA-09",
        "title": "9 - Investment Replacement",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Product Replacement", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Making a recommendation to replace a financial product: s961B(2)(e)",
        "auditQuestion": "Has the adviser made an appropriate recommendation to replace or rollover a financial product? Did the customer file pass or fail this step? Why/Why not?",
        "message": "If a superannuation or investment product is replaced, check consideration of the existing product, suitability of the recommended product, fee comparison, fee impact and alternatives considered.",
        "passCriteria": "If a product is replaced or rolled over, the SOA compares existing, recommended and alternative products, explains costs and benefits, and justifies the replacement. If no replacement occurs, this is not applicable.",
        "reviewCriteria": "Replacement advice is present but comparison, fee impact, alternatives or client benefit requires confirmation.",
        "failCriteria": "Replacement advice is given without adequate comparison or justification.",
    },
    {
        "index": 10,
        "testId": "SOA-10",
        "title": "10 - Investment Portfolio",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Investment Portfolio", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Recommending a financial product - Investment Portfolio Recommendations: s961B(2)(e)",
        "auditQuestion": "Where an investment portfolio is recommended, does the asset allocation meet the risk profile? Did the customer file pass or fail this step? Why/Why not?",
        "message": "If investment portfolio transactions are recommended, check the transaction summary, risk-profile alignment and whether any asset allocation variance is adequately explained.",
        "passCriteria": "Where an investment portfolio is recommended, the asset allocation aligns with the client's risk profile or any variance is adequately explained.",
        "reviewCriteria": "Portfolio advice is present but asset allocation, risk alignment or variance explanation is unclear.",
        "failCriteria": "The recommended portfolio is materially inconsistent with the client's risk profile and no adequate explanation is provided.",
    },
    {
        "index": 11,
        "testId": "SOA-11",
        "title": "11 - Adviser Judgement",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "All judgements are based on customer's relevant circumstances: s961B(2)(f)",
        "auditQuestion": "Has the adviser based all judgements made, in advising the customer, on the customer's relevant circumstances? Did the customer file pass or fail this step? Why/Why not?",
        "message": "Summarise the strategic recommendations and check whether each recommendation, consequence and alternative strategy is based on the client's relevant circumstances.",
        "passCriteria": "The SOA shows the adviser's judgements are based on the client's relevant circumstances and the client is likely to be in a better position if they follow the advice.",
        "reviewCriteria": "The advice may be suitable but the reasoning, consequences or alternatives are incomplete or unclear.",
        "failCriteria": "The advice does not clearly reflect the client's relevant circumstances or appears mismatched to their objectives.",
    },
    {
        "index": 12,
        "testId": "SOA-12",
        "title": "12 - Needs Analysis",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Insurance", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Recommending a financial product - life insurance needs analysis: s961B(2)(e)",
        "auditQuestion": "Has the adviser completed a needs analysis? Did the customer file pass or fail this step?",
        "message": "Where insurance is recommended, check whether a needs analysis calculates appropriate cover or whether the client validly declined and the advice scoped it out.",
        "passCriteria": "Where insurance is recommended, the SOA includes a needs analysis or validly scopes it out where declined. If no insurance advice is given, this is not applicable.",
        "reviewCriteria": "Insurance advice is present but the needs analysis, cover basis or scoping is incomplete or unclear.",
        "failCriteria": "Insurance is recommended without a needs analysis or valid scope limitation.",
    },
    {
        "index": 13,
        "testId": "SOA-13",
        "title": "13 - Insurance Replacement",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Insurance Product Replacement", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Making a recommendation to replace a life insurance product: s961B(2)(e)",
        "auditQuestion": "Has the adviser made a recommendation to replace a life insurance product? Did the customer file pass or fail this step? Why/Why not?",
        "message": "If life insurance is replaced, check why the existing product is unsuitable, whether replacement satisfies objectives, premium/features comparison and alternative insurers considered.",
        "passCriteria": "If insurance is replaced, the SOA explains why the existing product is unsuitable, compares premiums/features, considers alternatives, and links replacement to client objectives. If no replacement occurs, this is not applicable.",
        "reviewCriteria": "Insurance replacement advice is present but comparison, premium impact or alternatives require confirmation.",
        "failCriteria": "Insurance replacement is recommended without adequate comparison or justification.",
    },
    {
        "index": 14,
        "testId": "SOA-14",
        "title": "14 - Fee Disclosure",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Information about fee disclosure and any remuneration or commission: s947B (2) (d)",
        "auditQuestion": "Has the adviser provided appropriate disclosure of fees payable and any remuneration received? Did the customer file pass or fail this step?",
        "message": "Check preparation, implementation, ongoing, product and insurance commission fees, sole purpose issues and informed insurance consent where relevant.",
        "passCriteria": "The SOA discloses advice, implementation, ongoing, product and insurance commission fees where applicable, and addresses sole purpose and informed insurance consent issues where relevant.",
        "reviewCriteria": "Fees are disclosed but some amounts, payment sources, commissions, consent or sole purpose issues require confirmation.",
        "failCriteria": "Material fees, remuneration, commissions or required consent disclosures are missing.",
    },
    {
        "index": 15,
        "testId": "SOA-15",
        "title": "15 - Fee Agreements",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Ongoing/Annual Agreement", "type": ["Retail/Personal Advice", "Wholesale Client Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Information about fee agreements: s962",
        "auditQuestion": "Has the adviser provided the client with an ongoing or annual fee agreement? Did the customer file pass or fail this step?",
        "message": "If an ongoing or annual fee arrangement is recommended, check the agreement, services, fees, payment source, fee consent and reference date requirements.",
        "passCriteria": "Where an ongoing or annual fee arrangement is recommended, the SOA identifies the agreement, services, fees, payment source, consent and reference date requirements. If no arrangement is recommended, this is not applicable.",
        "reviewCriteria": "A fee arrangement is present but service, fee, consent, deduction or reference date details need confirmation.",
        "failCriteria": "An ongoing or annual fee arrangement is recommended without the required agreement or consent details.",
    },
    {
        "index": 16,
        "testId": "SOA-16",
        "title": "16 - Product Disclosure Statement",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Product Disclosure Statement", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "Product disclosure obligations",
        "auditQuestion": "Has the adviser provided or referenced the relevant Product Disclosure Statement for recommended products?",
        "message": "Where a financial product is recommended, check whether the SOA provides or references the relevant Product Disclosure Statement or disclosure document.",
        "passCriteria": "Where a product is recommended, the SOA provides or clearly references the relevant PDS or disclosure document. If no product is recommended, this is not applicable.",
        "reviewCriteria": "A product is recommended but the PDS reference or disclosure evidence is unclear or incomplete.",
        "failCriteria": "A product is recommended and there is no evidence that the relevant PDS or disclosure document was provided or referenced.",
    },
    {
        "index": 17,
        "testId": "SOA-17",
        "title": "17 - Credit Advice",
        "reviewType": "SOA Pre-Vet",
        "saraChecks": {"name": "Credit Advice", "type": ["Retail/Personal Advice"], "checklistType": ""},
        "requiredDocuments": ["soa_vetted"],
        "severity": "mandatory",
        "regulatoryReference": "NCCP Act 2009",
        "auditQuestion": "Does the SOA avoid unlicensed credit advice?",
        "message": "Review whether the SOA includes credit assistance or credit product recommendations without appropriate authority or scope limitation.",
        "passCriteria": "The SOA does not provide regulated credit assistance, or credit matters are clearly scoped out/background only.",
        "reviewCriteria": "The SOA mentions credit, lending, refinancing or loan strategies and it is unclear whether this crosses into regulated credit advice.",
        "failCriteria": "The SOA appears to recommend, arrange or provide credit assistance without clear authority or appropriate scoping.",
    },
]

ROA_PREVET_PROMPTS = [
    "RA-01 Is this further advice suited to an RoA?",
    "RA-02 Can the prior SOA it relies on be located and is it valid?",
    "RA-03 Have the client's relevant personal circumstances changed significantly since the SOA?",
    "RA-04 Does the further advice stay within the basis and product scope of the SOA?",
    "RA-05 Does the RoA record the required content and is it retained?",
]

REQUIRED_CHECK_FIELDS = (
    "index",
    "testId",
    "title",
    "reviewType",
    "saraChecks",
    "requiredDocuments",
    "severity",
    "regulatoryReference",
    "auditQuestion",
    "message",
    "passCriteria",
    "reviewCriteria",
    "failCriteria",
)


def get_checks(review_type=None):
    checks = SOA_PREVET_CHECKS
    if review_type:
        checks = [c for c in checks if c["reviewType"].lower() == review_type.lower()]
    return deepcopy(sorted(checks, key=lambda c: c["index"]))


def validate_catalogue():
    checks = get_checks("SOA Pre-Vet")
    indexes = [c["index"] for c in checks]
    test_ids = [c["testId"] for c in checks]
    missing = [
        f"{c.get('testId', c.get('title', 'unknown'))}:{field}"
        for c in checks
        for field in REQUIRED_CHECK_FIELDS
        if field not in c or c[field] in (None, "")
    ]
    return {
        "count": len(checks),
        "uniqueIndexes": len(indexes) == len(set(indexes)),
        "uniqueTestIds": len(test_ids) == len(set(test_ids)),
        "missingFields": missing,
    }


def prompt_text_for_check(check):
    return (
        f"{check['testId']} - {check['title']}\n"
        f"Regulatory reference: {check['regulatoryReference']}\n"
        f"Audit question: {check['auditQuestion']}\n"
        f"Instruction: {check['message']}\n"
        f"Pass criteria: {check['passCriteria']}\n"
        f"Review criteria: {check['reviewCriteria']}\n"
        f"Fail criteria: {check['failCriteria']}"
    )


def default_prompts_for_review_type(review_type):
    if "roa" in (review_type or "").lower():
        return ROA_PREVET_PROMPTS[:]
    return [prompt_text_for_check(check) for check in get_checks("SOA Pre-Vet")]


def render_soa_prompt():
    rendered_checks = "\n\n".join(prompt_text_for_check(check) for check in get_checks("SOA Pre-Vet"))
    return f"""ROLE: SOA pre-vet - assess the appropriateness and disclosure of this Statement of Advice before it goes to the client. The SOA is a SINGLE, self-contained document: assess what the SOA itself contains.

Produce ONE finding for EACH catalogue check below, in order, using the exact testId.
For each finding:
- Set question to the audit question plus the regulatory reference.
- Apply the explicit pass/review/fail criteria.
- In reasoning, give a compliance-grade basis, not a section-presence summary. Explain the extracted client facts, the relevant compliance criteria, and why those facts support Pass, Review, or Fail.
- In criteriaAssessment, break the check into the key criteria or sub-tests and mark each as Met, Partly met, Not met, or Not applicable.
- In evidenceItems, quote the most relevant short source text and explain why it matters. Do not cite headings alone unless the heading is itself the only relevant evidence.
- In gaps, list any missing, unclear, generic, inconsistent, or weak evidence. Use [] only where there are no material gaps.
- In recommendedAction, state what the adviser or compliance manager should do next. If no action is needed, say "No action required."
- If a check is conditional and the advice topic is absent, use Pass and explain that it is not applicable.
- If a mandatory required document is not provided, mark Review or Fail based on the criteria and explain the missing evidence.

Catalogue checks:

{rendered_checks}

Apply firm policy: asset allocation variance up to 10 percentage points outside risk-profile min/max ranges is permitted and should be a coaching observation, not a Fail. Low-level document-quality issues should be listed in adviserSuggestion and should not by themselves force compliance review.

Outcome logic:
- For this SOA pre-vet, do not use RoA / Record of Advice wording in the summary or findings.
- The JSON field roaPermitted is a legacy compatibility field. For SOA pre-vet, treat it as "SOA has no failed tests". It does not mean this is an RoA.
- If requiresComplianceReview is true, summary must say the SOA requires compliance review, not that it is self-approvable.
- requiresComplianceReview is true if ANY regulatory test is Review or Fail.
- summary is a one-line overall outcome about the Statement of Advice / SOA."""
