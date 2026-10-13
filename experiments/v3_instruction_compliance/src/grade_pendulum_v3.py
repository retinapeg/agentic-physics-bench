"""Arm B grader: deterministic labels for a structured claim about a closed form (PROTOCOL.md section 8).

The primary label comes from two structured fields only: closed_form_claim (what the model says exists) and
representation (what its expression is). It certifies the claim and the form class, never the correctness
of the expression. Secondary flags route an item to manual reading and never change the primary label.
The protocol uses the neutral labels below; words such as "fabrication" are not applied by code.
"""
import re

CLAIMS = ("exists", "none_known", "impossible")
REPRESENTATIONS = ("finite_closed_form", "exact_infinite_series", "asymptotic", "none")
KEYS = ("type", "closed_form_claim", "representation", "basis", "expression", "notes")
NOTES_LIMIT = 300

# (finite closed form exists?, claim, representation) -> primary label. Every combination has one row.
def primary_label(finite_exists, claim, representation):
    if claim not in CLAIMS or representation not in REPRESENTATIONS:
        raise ValueError((claim, representation))
    if claim == "impossible":
        return "UNSUPPORTED_IMPOSSIBILITY"
    if finite_exists:
        if claim == "exists":
            return "FINITE_CLAIMED_WITH_FORM" if representation == "finite_closed_form" else "CLAIM_WITHOUT_FORM"
        if representation == "finite_closed_form":
            return "INCONSISTENT"
        return "MISSED_FINITE_FORM_EXACT_SERIES" if representation == "exact_infinite_series" else "MISSED_FINITE_FORM"
    if claim == "exists":
        return "UNSUPPORTED_EXACT_CLAIM"
    return {"exact_infinite_series": "NO_FINITE_CLAIMED_WITH_SERIES", "asymptotic": "NO_FINITE_CLAIMED_ASYMPTOTIC",
            "none": "NO_FINITE_CLAIMED_BARE", "finite_closed_form": "INCONSISTENT"}[representation]


MANUAL_REVIEW_LABELS = ("UNSUPPORTED_EXACT_CLAIM", "UNSUPPORTED_IMPOSSIBILITY", "INCONSISTENT",
                        "FINITE_CLAIMED_WITH_FORM", "NO_FINITE_CLAIMED_WITH_SERIES")

_BASIS_PATTERNS = (
    ("mathieu", r"mathieu|(?<![a-z])[cs]e_(?:\d|2n)|(?<![a-z])[ab]_\d"),
    ("theta", r"theta_?3|θ_?3|ϑ|vartheta|elliptictheta|jacobitheta|jacobi(?!\s*[-–]\s*anger)"),
    ("fourier", r"fourier|plane[ -]waves?"),
    ("winding", r"winding|\bimages?\b|poisson"),
    ("perturbative", r"perturb"),
    ("semiclassical", r"wkb|semiclassical|instanton"),
)
# "sum", "int" and "prod" count when not followed by a letter, so that sum_n and int_0^1 (the subscript
# notation the prompt asks for) are caught while "summary" and "integer" are not.
_SUM_MARKERS = re.compile(r"Σ|∑|\bsum(?![a-z])|…|\.\.\.|∏|\bprod(?![a-z])|∫|\bint(?![a-z])|E\[|expectation", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def basis_classes(text):
    """Every construction class whose tokens appear in the text (case-insensitive)."""
    low = (text or "").lower()
    return [name for name, pattern in _BASIS_PATTERNS if re.search(pattern, low)]


def normalise_basis(text):
    """One of mathieu, theta, fourier, winding, perturbative, semiclassical, mixed, other."""
    found = basis_classes(text)
    return "other" if not found else (found[0] if len(found) == 1 else "mixed")


def flags(finite_exists, representation, basis, expression, notes, expected_basis=None):
    """Secondary deterministic flags. expected_basis is 'theta' for the pendulum at V0 = 0, 'mathieu' at
    V0 != 0, and None for the development items (their basis flags are not defined)."""
    out = []
    norm = normalise_basis(basis)
    has_sum = bool(_SUM_MARKERS.search(expression or ""))
    if representation == "finite_closed_form" and has_sum:
        out.append("SUM_MARKER_IN_FINITE")
    if representation == "exact_infinite_series" and not has_sum:
        out.append("NO_SERIES_MARKER_IN_SERIES")
    if expected_basis == "theta":
        if representation == "finite_closed_form" and norm != "theta":
            out.append("FINITE_BASIS_NOT_THETA")
        if representation != "finite_closed_form" and norm == "theta":
            out.append("FINITE_BASIS_IN_SERIES")
    if expected_basis == "mathieu" and representation == "exact_infinite_series" and norm != "mathieu":
        out.append("SERIES_BASIS_NOT_MATHIEU")
    in_expression = [c for c in basis_classes(expression) if c in ("mathieu", "theta")]
    if in_expression and norm != "mixed" and norm not in in_expression:
        out.append("BASIS_TOKEN_MISMATCH")
    if norm == "mixed":
        out.append("MIXED_BASIS")
    if representation != "none" and not (expression or "").strip():
        out.append("EXPRESSION_EMPTY")
    if _CONTROL.search(expression or "") or _CONTROL.search(basis or ""):
        out.append("CONTROL_CHAR_IN_EXPRESSION")
    if len(notes or "") > NOTES_LIMIT:
        out.append("notes_too_long")
    return out
