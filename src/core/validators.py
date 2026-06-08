"""
Question Validation Engine — centralised pre-delivery checks.

Telegram hard limits (as of Bot API 7.x):
  poll question  : 300 chars
  poll option    : 100 chars
  option count   : 2–10
  explanation    : 200 chars
"""

from typing import Dict, List, Optional, Tuple

POLL_Q_LIMIT  = 300
POLL_OPT_LIMIT = 100
POLL_MAX_OPTS  = 10
POLL_MIN_OPTS  = 2
EXPL_LIMIT     = 200

QUESTION_MIN_LEN = 5
QUESTION_MAX_LEN = 290   # leave 10 chars for category prefix


class ValidationResult:
    __slots__ = ("valid", "error", "warnings")

    def __init__(self, valid: bool, error: str = "", warnings: List[str] = None):
        self.valid    = valid
        self.error    = error
        self.warnings = warnings or []

    def __bool__(self):
        return self.valid


def validate(q: Dict) -> ValidationResult:
    """Full validation — returns ValidationResult(valid, error, [warnings])."""
    warnings: List[str] = []

    if not q:
        return ValidationResult(False, "question is None or empty dict")

    text = (q.get("question") or "").strip()
    if not text:
        return ValidationResult(False, "question text is empty")
    if len(text) < QUESTION_MIN_LEN:
        return ValidationResult(False, f"question too short ({len(text)} chars)")
    if len(text) > QUESTION_MAX_LEN:
        warnings.append(f"question will be truncated ({len(text)} → {QUESTION_MAX_LEN})")

    options = q.get("options")
    if not isinstance(options, list):
        return ValidationResult(False, "options is not a list")
    if len(options) < POLL_MIN_OPTS:
        return ValidationResult(False, f"too few options ({len(options)} < {POLL_MIN_OPTS})")
    if len(options) > POLL_MAX_OPTS:
        return ValidationResult(False, f"too many options ({len(options)} > {POLL_MAX_OPTS})")

    clean_opts = [str(o).strip() for o in options]
    if any(not o for o in clean_opts):
        return ValidationResult(False, "one or more options are empty")

    if len(set(o.lower() for o in clean_opts)) < len(clean_opts):
        return ValidationResult(False, "duplicate options detected")

    for i, opt in enumerate(clean_opts):
        if len(opt) > POLL_OPT_LIMIT:
            warnings.append(f"option {i} will be truncated ({len(opt)} → {POLL_OPT_LIMIT})")

    correct = q.get("correct_answer")
    if not isinstance(correct, int):
        return ValidationResult(False, "correct_answer is not an int")
    if not (0 <= correct < len(options)):
        return ValidationResult(False, f"correct_answer {correct} out of range [0, {len(options)-1}]")

    return ValidationResult(True, warnings=warnings)


def sanitize(q: Dict) -> Optional[Dict]:
    """
    Return a sanitized copy of q compatible with Telegram poll limits,
    or None if the question is fundamentally broken and cannot be fixed.
    """
    result = validate(q)
    if not result.valid:
        # Try basic fixes first
        if "question text is empty" in result.error or "too short" in result.error:
            return None
        if "options is not a list" in result.error:
            return None
        if "too few options" in result.error:
            return None
        if "duplicate options" in result.error:
            return None
        if "correct_answer" in result.error:
            return None

    text    = (q.get("question") or "").strip()
    options = [str(o).strip() for o in q.get("options", [])]
    correct = int(q.get("correct_answer", 0))

    # Truncate question
    if len(text) > QUESTION_MAX_LEN:
        text = text[:QUESTION_MAX_LEN - 1] + "…"

    # Truncate options
    clean_options = []
    for opt in options:
        if len(opt) > POLL_OPT_LIMIT:
            opt = opt[:POLL_OPT_LIMIT - 1] + "…"
        clean_options.append(opt)

    # Cap option count
    if len(clean_options) > POLL_MAX_OPTS:
        # Keep correct answer in range
        clean_options = clean_options[:POLL_MAX_OPTS]
        if correct >= POLL_MAX_OPTS:
            correct = 0

    out = dict(q)
    out["question"]       = text
    out["options"]        = clean_options
    out["correct_answer"] = correct
    return out


def build_explanation(q: Dict) -> str:
    """Build a Telegram-safe explanation string (≤200 chars)."""
    opts    = q.get("options", [])
    correct = q.get("correct_answer", 0)
    cat     = q.get("category", "General")
    qid     = q.get("id", "?")
    answer  = opts[correct] if 0 <= correct < len(opts) else "?"
    expl    = f"✅ {answer}\n📚 {cat}  ·  Q#{qid}"
    return expl[:EXPL_LIMIT]
