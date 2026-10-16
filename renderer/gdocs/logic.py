"""Pure, API-free logic of the MOON42 Google Docs generator (dates, e-mail,
mobile, eligibility, row-profile matching, skill categories)."""

import re
import unicodedata
from dataclasses import dataclass, field

MOON42_DOMAIN = "@moon42.com"


def strip_accents(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


# --- Dates (FR-9) -----------------------------------------------------------

def format_date(value):
    """'YYYY/MM' -> 'mm/yyyy', 'YYYY' -> 'yyyy', None -> 'Present'."""
    if value is None:
        return "Present"
    text = str(value).strip()
    match = re.fullmatch(r"(\d{4})/(\d{1,2})", text)
    if match:
        return f"{int(match.group(2)):02d}/{match.group(1)}"
    return text


MISSING = object()  # `end` key absent from the YAML (null means ongoing)


def format_date_range(start, end=MISSING):
    """'<start> – <end>' (en dash). A missing/empty part drops with the
    separator: end=MISSING drops the end, end=None means ongoing ('Present').
    Without a start only a real end date is shown."""
    if not start:
        return format_date(end) if end not in (MISSING, None) else ""
    if end is MISSING:
        return format_date(start)
    return f"{format_date(start)} – {format_date(end)}"


def join_parts(parts, separator):
    """Join the non-empty parts; missing parts take their separator with them."""
    return separator.join(p for p in parts if p and str(p).strip())


# --- E-mail and mobile (FR-8) ----------------------------------------------

def _letters(text):
    return re.sub(r"[^a-z]", "", strip_accents(text).lower())


def moon42_email(first_name, last_name, sheet_email=None):
    """Return (email, warning). The sheet value wins if it is a moon42.com
    address; otherwise '<first token of firstName>.<lastName>@moon42.com'."""
    if sheet_email and sheet_email.strip().lower().endswith(MOON42_DOMAIN):
        return sheet_email.strip(), None
    first_tokens = first_name.split()
    email = f"{_letters(first_tokens[0] if first_tokens else '')}." \
            f"{_letters(last_name)}{MOON42_DOMAIN}"
    warning = None
    if (len(first_tokens) > 1 or len(last_name.split()) > 1
            or "." in first_name or "." in last_name):
        warning = (f"Származtatott e-mail-cím ({email}): a név több tagból áll "
                   "vagy pontot tartalmaz, ellenőrizd a címet.")
    return email, warning


def pick_mobile(contacts, sheet_mobile=None):
    """YAML 'mobile' contact, else 'phone', else the sheet's formatted Mobile
    value, else None. Values are passed through verbatim."""
    for contact_type in ("mobile", "phone"):
        for contact in contacts or []:
            if contact.get("type") == contact_type and contact.get("value"):
                return contact["value"]
    if sheet_mobile and sheet_mobile.strip():
        return sheet_mobile
    return None


# --- Eligibility (FR-4) -----------------------------------------------------

def is_eligible(status, profile_cell_text, profile_cell_has_chip=False):
    """A row is eligible when Status is 'in progress' (trimmed,
    case-insensitive) and the MOON42 Profile cell is empty or whitespace only.

    Cell signature: `profile_cell_text` is the cell's displayed (formatted)
    string or None; `profile_cell_has_chip` is True if the cell carries a
    chip or link (then it is never empty, whatever its text)."""
    if (status or "").strip().lower() != "in progress":
        return False
    if profile_cell_has_chip:
        return False
    return not (profile_cell_text or "").strip()


# --- Name matching (FR-5) ---------------------------------------------------

def name_tokens(name):
    """Accent- and case-insensitive tokens split on whitespace, dots, hyphens."""
    return {t for t in re.split(r"[\s.\-]+", strip_accents(name or "").lower()) if t}


@dataclass
class MatchResult:
    status: str  # "matched" | "skipped" | "error"
    profile_id: str = None
    reason: str = None
    warnings: list = field(default_factory=list)


def match_rows(rows, profiles):
    """rows: list of (row_key, name) of the eligible rows.
    profiles: list of (profile_id, firstName, lastName).
    Returns {row_key: MatchResult}."""
    profile_tokens = [(pid, name_tokens(first) | name_tokens(last))
                      for pid, first, last in profiles]
    results = {}
    for key, name in rows:
        tokens = name_tokens(name)
        if not tokens:
            results[key] = MatchResult("skipped", reason="Üres Name érték.")
            continue
        full = [pid for pid, pt in profile_tokens if tokens <= pt]
        if len(full) == 1:
            results[key] = MatchResult("matched", profile_id=full[0])
        elif len(full) > 1:
            results[key] = MatchResult(
                "skipped",
                reason="Több profil illeszkedik: " + ", ".join(sorted(full)) + ".")
        else:
            result = MatchResult("skipped", reason="Nincs illeszkedő profil.")
            partial = sorted(pid for pid, pt in profile_tokens if tokens & pt)
            if partial:
                result.warnings.append(
                    f"Részleges névegyezés („{name}”), jelölt profilok: "
                    + ", ".join(partial) + ".")
            results[key] = result
    by_profile = {}
    for key, result in results.items():
        if result.status == "matched":
            by_profile.setdefault(result.profile_id, []).append(key)
    for pid, keys in by_profile.items():
        if len(keys) > 1:
            for key in keys:
                results[key] = MatchResult(
                    "error", profile_id=pid,
                    reason=f"Több jogosult sor illeszkedik ugyanarra a profilra ({pid}).")
    return results


# --- Skill categories (README "Megfeleltetés") -------------------------------

# Cloud providers inside devOpsAndCloud: exact (normalized) item names. Tools
# of a provider (e.g. "AWS Lambda", "Azure DevOps") stay in DevOps / IaC.
CLOUD_PROVIDERS = {
    "aws", "amazon web services", "azure", "microsoft azure", "gcp",
    "google cloud", "google cloud platform", "digitalocean", "heroku",
    "hetzner", "vercel", "godaddy", "oracle cloud", "ibm cloud",
    "alibaba cloud", "cloudflare",
}


def split_skills(technical):
    """Map skills.technical to the template's skill rows (lists, empty if
    absent): programming, frameworks, databases, testing, ai, cloud, devops,
    other. Cloud = the providers of devOpsAndCloud, DevOps = the rest."""
    def get(key):
        return list(technical.get(key) or [])

    dev_ops = get("devOpsAndCloud")
    cloud = [s for s in dev_ops if s.strip().lower() in CLOUD_PROVIDERS]
    return {
        "programming": get("programmingLanguages"),
        "frameworks": get("frameworksAndLibraries"),
        "databases": get("databases"),
        "testing": get("testingAndQA"),
        "ai": get("ai"),
        "cloud": cloud,
        "devops": [s for s in dev_ops if s not in cloud],
        "other": (get("toolsAndTechnologies") + get("operatingSystems")
                  + get("developmentMethodologies")
                  + get("specializedDomains")),
    }
