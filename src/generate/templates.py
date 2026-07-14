"""Deterministic scam/legit message templates, shared by `messages.py` (the
training/eval text corpus) and `network.py` (raw_text for the seeded network).

LLM paraphrase for natural variation is a documented follow-up (see
`messages.py`) -- these templates are the honest, testable baseline the rest of
the pipeline (extraction, linking, evidence) does not depend on being prettier.
"""
from __future__ import annotations

# scam_type -> a few template strings with {amount}/{upi}/{phone}/{url}/{name} slots.
SCAM_TEMPLATES: dict[str, list[str]] = {
    "digital_arrest": [
        "This is Officer {name} from CBI. A parcel booked under your Aadhaar contains "
        "illegal items. To avoid arrest, transfer Rs.{amount} to UPI {upi} for verification "
        "within 1 hour. Do not disconnect this call.",
        "URGENT: Your mobile number is linked to a money-laundering case under ED "
        "investigation. Pay a refundable security deposit of Rs.{amount} to {upi} "
        "immediately or a digital arrest warrant will be issued in your name.",
    ],
    "parcel_customs": [
        "Your parcel from abroad is held at customs. Pay a clearance fee of Rs.{amount} to "
        "{upi} or call {phone} to release it within 24 hours, else it will be destroyed.",
        "Courier Alert: We attempted delivery of your international parcel but customs duty "
        "of Rs.{amount} is pending. Pay via {upi} to reschedule delivery today.",
    ],
    "kyc_update": [
        "Dear customer, your bank KYC will expire today. Update immediately by paying a "
        "Rs.{amount} verification charge to {upi} or your account will be permanently blocked.",
        "Your bank KYC is incomplete. Click {url} and share the OTP sent to you to avoid "
        "suspension of your account.",
    ],
    "lottery_prize": [
        "Congratulations! Your number has won Rs.25,00,000 in the lucky draw. Pay a "
        "processing fee of Rs.{amount} to {upi} to claim your prize before it expires.",
    ],
    "relative_distress": [
        "Mom I lost my phone, this is my friend's number. I'm in trouble and need Rs.{amount} "
        "urgently, please send it to {upi} right now, I'll explain everything later.",
    ],
    "loan_app": [
        "Your instant personal loan of Rs.50,000 is pre-approved! Pay a processing fee of "
        "Rs.{amount} to {upi} to receive the funds in your account today.",
    ],
    "investment": [
        "Join our exclusive stock-tips group, guaranteed 300% returns in 30 days. Deposit "
        "Rs.{amount} to {upi} to start trading today with our expert advisor.",
    ],
}

# One Hinglish (romanized Hindi/English mix) variant per scam_type, appended to
# each list above -- not a separate dict, so the corpus generators and the
# per-type parametrized tests (`SCAM_TEMPLATES[scam_type]`) exercise it for
# free (CLAUDE.md §15 G4). Technical nouns (CBI, KYC, parcel, customs, lottery,
# loan, trading) are kept in English, matching how real Hinglish scam SMS read
# -- that's also what keeps these distinguishable by the existing scam_type
# keyword scoring in `src/detector/classify.py` without per-type additions.
SCAM_TEMPLATES["digital_arrest"].append(
    "Yeh CBI se Officer {name} bol raha hai. Aapke Aadhaar par illegal activity ka case mila "
    "hai. Arrest se bachne ke liye turant Rs.{amount} UPI {upi} par transfer karein, 1 ghante "
    "ke andar. Call mat kaatiye."
)
SCAM_TEMPLATES["parcel_customs"].append(
    "Aapka parcel customs mein ruka hai. Turant Rs.{amount} {upi} par pay karein ya {phone} "
    "par call karein, warna parcel wapas bhej diya jayega."
)
SCAM_TEMPLATES["kyc_update"].append(
    "Aapka bank KYC aaj expire ho raha hai. Turant Rs.{amount} verification charge {upi} par "
    "pay karein warna aapka account blocked ho jayega."
)
SCAM_TEMPLATES["lottery_prize"].append(
    "Badhai ho! Aapka number Rs.25,00,000 ki lucky draw mein jeeta hai. Prize claim karne ke "
    "liye turant Rs.{amount} processing fee {upi} par pay karein, offer jaldi khatam ho raha hai."
)
SCAM_TEMPLATES["relative_distress"].append(
    "Mummy mera phone kho gaya hai, yeh mere dost ka number hai. Main musibat mein hoon, "
    "turant Rs.{amount} chahiye, {upi} par bhej do, baad mein sab bataunga."
)
SCAM_TEMPLATES["loan_app"].append(
    "Aapka Rs.50,000 ka instant loan pre-approved hai! Paisa account mein turant paane ke liye "
    "Rs.{amount} processing fee {upi} par pay karein."
)
SCAM_TEMPLATES["investment"].append(
    "Hamare stock-tips group join karein, guaranteed 300% returns 30 dino mein milega. Trading "
    "turant shuru karne ke liye Rs.{amount} {upi} par deposit karein."
)

LEGIT_TEMPLATES: list[str] = [
    "Your order from {upi} has been placed. Amount Rs.{amount} paid successfully.",
    "OTP for your transaction of Rs.{amount} is 482913. Valid for 10 minutes. Do not share "
    "this OTP with anyone.",
    "Your recharge of Rs.{amount} was successful. Thank you for using our service.",
    "Payment of Rs.{amount} to {upi} was successful. Your order will be delivered soon.",
]

# scam_type -> red flags that plausibly fire on that template family (docs/REPORT_SCHEMA.md §5).
SCAM_TYPE_RED_FLAGS: dict[str, list[str]] = {
    "digital_arrest": ["authority_impersonation", "threat", "urgency", "payment_demand"],
    "parcel_customs": ["urgency", "payment_demand", "suspicious_link"],
    "kyc_update": ["urgency", "payment_demand", "otp_request"],
    "lottery_prize": ["too_good_to_be_true", "payment_demand"],
    "relative_distress": ["urgency", "secrecy", "payment_demand"],
    "loan_app": ["too_good_to_be_true", "payment_demand"],
    "investment": ["too_good_to_be_true", "payment_demand"],
}


def render(template: str, *, amount=None, upi=None, phone=None, url=None, name=None) -> str:
    """Fill `template`'s slots. `upi`/`phone`/`url`, when given, always end up
    somewhere in the returned text -- inline if the template has that slot,
    else as an appended clause -- so a generator can pass an identifier once
    and know entities/raw_text stay consistent regardless of which template a
    scam_type happens to use (see messages.py, network.py). Without this
    guarantee a template with no `{upi}` slot (e.g. an OTP-phishing variant)
    would plant a ground-truth payee_upi that never appears in raw_text at all."""
    text = template.format(
        amount=amount if amount is not None else "",
        upi=upi or "",
        phone=phone or "",
        url=url or "",
        name=name or "Sharma",
    )
    extras = []
    if upi and "{upi}" not in template:
        extras.append(f"Pay to: {upi}.")
    if phone and "{phone}" not in template:
        extras.append(f"Helpline: {phone}.")
    if url and "{url}" not in template:
        extras.append(f"Verify at: {url}.")
    return f"{text} {' '.join(extras)}".strip() if extras else text
