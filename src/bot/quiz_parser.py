"""
Universal Quiz Parser — handles almost any exam/question-bank text format.

Public interface
----------------
bulk_import(text, quiz_manager) -> Dict
guess_category(q) -> str
UniversalQuizParser              (class with .parse(text) -> (questions, stats))
"""

import re
import difflib
import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  LOW-LEVEL REGEXES
# ═══════════════════════════════════════════════════════════════════════════

# Question-number prefix: "1." "1)" "Q1." "Q:" "Question 1:"
_Q_NUM_RE = re.compile(
    r"^(?:Q(?:uestion)?[\.\s]*\d*[\s:\.]?\s*|\d{1,3}[\.)\s]+)",
    re.IGNORECASE,
)

# Option label prefix: "(A)" "A)" "A." "[A]"
_OPT_RE = re.compile(
    r"^[\(\[\{]?([A-Da-d]|[1-4])[\)\]\}\.:>\s]",
    re.IGNORECASE,
)

# Answer marker at start of line
_ANS_RE = re.compile(
    r"^(?:answer|ans(?:wer)?|correct(?:\s+answer)?|key|right)\s*[:\-\.>]?\s*"
    r"[\(\[]?([A-Da-d1-4])[\)\]]?",
    re.IGNORECASE,
)

# Answer marker anywhere in line (requires separator to avoid false positives)
_ANS_INLINE_RE = re.compile(
    r"\b(?:answer|ans(?:wer)?|correct\s+answer|key|solution)\s*[:\-\.>]\s*"
    r"[\(\[]?([A-Da-d1-4])[\)\]]?",
    re.IGNORECASE,
)

# Four inline options on one line: "A) x B) y C) z D) w"
_INLINE4_RE = re.compile(
    r"(?:^|(?<=\s))[\(\[]?[Aa][\)\]\.][\s]+(.+?)\s+"
    r"[\(\[]?[Bb][\)\]\.][\s]+(.+?)\s+"
    r"[\(\[]?[Cc][\)\]\.][\s]+(.+?)\s+"
    r"[\(\[]?[Dd][\)\]\.][\s]+(.+?)\s*$"
)

# Asterisk / bracket correct marker: trailing * or [correct]
_STAR_RE = re.compile(r"[\*]{1,2}\s*$|\[correct\]\s*$|\[ans\]\s*$", re.IGNORECASE)

# Answer-key section header
_KEY_HEADER_RE = re.compile(
    r"^(?:answer\s*key|answers?|solutions?|correct\s*answers?)\s*[:\-]?\s*$",
    re.IGNORECASE,
)

# Single answer-key line: "1. B" or "2) C" or "3- A"
_KEY_LINE_RE = re.compile(r"^(\d{1,3})\s*[\.)\-:\s]\s*([A-Da-d])\s*$")

# Compact inline key: "1-A 2-C 3-B" or "1. A, 2. B"
_KEY_INLINE_RE = re.compile(r"(\d{1,3})\s*[-\.]\s*([A-Da-d])")

# True/False question marker
_TF_RE = re.compile(r"^(true|false)\s*/\s*(false|true)\s*$", re.IGNORECASE)
_TF_ANS_RE = re.compile(r"^(?:answer|ans)\s*[:\-]?\s*(true|false)\s*$", re.IGNORECASE)

# Solution/explanation lines to skip
_SKIP_LINE_RE = re.compile(
    r"^(?:solution|explanation|hint|rationale|note)\s*[:\-]",
    re.IGNORECASE,
)

# "Solution: Option B" — extract answer from it
_SOL_OPT_RE = re.compile(
    r"^solution\s*[:\-]\s*option\s+([A-Da-d])",
    re.IGNORECASE,
)

# "Options: A) ... B) ... C) ... D) ..."
_OPTIONS_LABEL_RE = re.compile(r"^options?\s*[:\-]", re.IGNORECASE)

# Noise lines to discard
_NOISE_RE = re.compile(
    r"^(\d+)$"
    r"|^(page|pg\.?|p\.)\s*\d+$"
    r"|^(www\.|http|©|copyright"
    r"|all\s+rights\s+reserved"
    r"|prepared\s+by|source:)"
    r"|^[-=_*~.]{3,}$",
    re.IGNORECASE,
)

# Separator line (kept as block boundary signal, content discarded)
_SEP_RE = re.compile(r"^[-=_*~.]{3,}$")


# ═══════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _label_to_idx(ch: str) -> Optional[int]:
    return {"A": 0, "B": 1, "C": 2, "D": 3,
            "a": 0, "b": 1, "c": 2, "d": 3,
            "1": 0, "2": 1, "3": 2, "4": 3}.get(ch)


def _strip_q_prefix(line: str) -> Tuple[Optional[int], str]:
    """Return (question_number, cleaned_text) from a numbered line."""
    m = re.match(r"^(?:Q(?:uestion)?\s*)?(\d{1,3})[\.)\s]+", line.strip(), re.IGNORECASE)
    if m:
        return int(m.group(1)), line.strip()[m.end():].strip()
    return None, line.strip()


def _strip_opt_label(line: str) -> Tuple[Optional[int], str]:
    m = _OPT_RE.match(line.strip())
    if not m:
        return None, line.strip()
    return _label_to_idx(m.group(1)), line.strip()[m.end():].strip()


def _clean_q(raw: str) -> str:
    return _Q_NUM_RE.sub("", raw.strip()).strip()


def _is_question_line(line: str) -> bool:
    return bool(_Q_NUM_RE.match(line.strip()))


def _is_option_line(line: str) -> bool:
    return bool(_OPT_RE.match(line.strip()))


def _is_noise(line: str) -> bool:
    return bool(_NOISE_RE.match(line.strip()))


def _is_separator(line: str) -> bool:
    return bool(_SEP_RE.match(line.strip()))


def _text_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _make_q(question: str, options: List[str], correct: int, category: str = "") -> Dict:
    return {
        "question":       question.strip(),
        "options":        [str(o).strip() for o in options],
        "correct_answer": correct,
        "category":       category or guess_category(question),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  CATEGORY AUTO-TAGGER
# ═══════════════════════════════════════════════════════════════════════════

_CAT_KW: Dict[str, List[str]] = {
    "Legal Reasoning": [
        "article", "constitution", "ipc", "crpc", "act", "court", "supreme",
        "amendment", "fundamental right", "directive", "habeas", "mandamus",
        "writ", "bail", "cognizable", "tort", "contract", "negligence",
        "liability", "section", "judgement", "decree",
    ],
    "Current Affairs": [
        "recently", "2024", "2025", "2026", "latest", "appointed", "elected",
        "inaugurated", "launched", "scheme", "mission", "prime minister",
        "president", "government",
    ],
    "English": [
        "synonym", "antonym", "grammar", "passage", "comprehension", "sentence",
        "phrase", "idiom", "verb", "noun", "adjective", "tense", "vocabulary",
        "word", "meaning", "spelling",
    ],
    "Logical Reasoning": [
        "series", "pattern", "sequence", "analogy", "syllogism", "conclusion",
        "inference", "assumption", "assertion", "coding", "blood relation",
        "direction", "ranking",
    ],
    "GK": [
        "capital", "country", "state", "river", "mountain", "ocean", "planet",
        "invention", "discovered", "largest", "smallest", "national", "award",
    ],
    "History": [
        "ancient", "medieval", "mughal", "british", "independence", "1947",
        "freedom fighter", "battle", "empire", "dynasty", "revolt", "treaty",
    ],
    "Polity": [
        "parliament", "rajya sabha", "lok sabha", "governor", "election",
        "vote", "panchayat", "federal", "judicial", "executive", "legislative",
    ],
}


def guess_category(q: str) -> str:
    q_low = q.lower()
    scores = {cat: sum(1 for kw in kws if kw in q_low) for cat, kws in _CAT_KW.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


# ═══════════════════════════════════════════════════════════════════════════
#  ANSWER-KEY EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════

def _extract_answer_keys(lines: List[str]) -> Tuple[Dict[int, str], Set[int]]:
    """
    Scan lines for answer-key sections.  Returns:
        key_map      : {question_number: letter}
        key_indices  : set of line indices that belong to key sections
    """
    key_map: Dict[int, str] = {}
    key_indices: Set[int] = set()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # --- Strategy 1: explicit header ---
        if _KEY_HEADER_RE.match(line) and len(line) <= 80:
            key_indices.add(i)
            i += 1
            while i < len(lines):
                kl = lines[i].strip()
                km = _KEY_LINE_RE.match(kl)
                if km:
                    key_map[int(km.group(1))] = km.group(2).upper()
                    key_indices.add(i)
                    i += 1
                    continue
                # Text answer: "1. Constitution" or "2. Shakespeare"
                kt = re.match(r"^(\d{1,3})\s*[\.)\-:]\s*(.+)$", kl)
                if kt and len(kl) < 80:
                    key_map[int(kt.group(1))] = kt.group(2).strip()
                    key_indices.add(i)
                    i += 1
                    continue
                if not kl:
                    i += 1
                    break
                break
            continue

        # --- Strategy 2: dense block of >= 4 consecutive "N. X" lines ---
        if _KEY_LINE_RE.match(line):
            block: List[Tuple[int, int, str]] = []
            j = i
            while j < len(lines):
                kl = lines[j].strip()
                km = _KEY_LINE_RE.match(kl)
                if km:
                    block.append((j, int(km.group(1)), km.group(2).upper()))
                    j += 1
                elif not kl:
                    j += 1
                else:
                    break
            if len(block) >= 4:
                for idx, num, letter in block:
                    key_map[num] = letter
                    key_indices.add(idx)
                i = j
                continue

        # --- Strategy 3: compact inline list "1-A 2-C 3-B ..." (>= 5 entries) ---
        matches = _KEY_INLINE_RE.findall(line)
        if len(matches) >= 5:
            for num_str, letter in matches:
                key_map[int(num_str)] = letter.upper()
            key_indices.add(i)
            i += 1
            continue

        # --- Strategy 4: "Answers: 1-A 2-C ..." label prefix ---
        if re.match(r"^answers?\s*[:\-]", line, re.IGNORECASE):
            label_matches = _KEY_INLINE_RE.findall(line)
            if label_matches:
                for num_str, letter in label_matches:
                    key_map[int(num_str)] = letter.upper()
                key_indices.add(i)
                i += 1
                continue

        i += 1

    return key_map, key_indices


# ═══════════════════════════════════════════════════════════════════════════
#  BLOCK-LEVEL PARSERS
# ═══════════════════════════════════════════════════════════════════════════

class _BlockParser:
    """Tries multiple strategies to extract a question dict from a block of lines."""

    def parse(self, lines: List[str]) -> Optional[Dict]:
        lines = [l.strip() for l in lines if l.strip()]
        if not lines:
            return None
        for strategy in (
            self._s_solution_book,
            self._s_true_false,
            self._s_standard_labeled,
            self._s_inline_opts,
            self._s_numbered_opts,
            self._s_asterisk,
            self._s_loose,
            self._s_pending,
        ):
            result = strategy(lines)
            if result is not None:
                return result
        return None

    # ── Format 6: Solution-book style ─────────────────────────────────────

    def _s_solution_book(self, lines: List[str]) -> Optional[Dict]:
        """
        Question N: <text>
        Options: A) ... B) ... C) ... D) ...
        Solution: Option B
        Explanation: ...  (skipped)
        """
        if not re.match(r"^question\s*\d*\s*[:\-]", lines[0], re.IGNORECASE):
            return None

        q_text = re.sub(
            r"^question\s*\d*\s*[:\-]\s*", "", lines[0], flags=re.IGNORECASE
        ).strip()
        options: Optional[List[str]] = None
        correct: Optional[int] = None

        for line in lines[1:]:
            if _SOL_OPT_RE.match(line):
                m = _SOL_OPT_RE.match(line)
                correct = _label_to_idx(m.group(1))
                continue
            if _ANS_RE.match(line):
                m = _ANS_RE.match(line)
                correct = _label_to_idx(m.group(1))
                continue
            if _SKIP_LINE_RE.match(line):
                continue
            if _OPTIONS_LABEL_RE.match(line):
                rest = re.sub(r"^options?\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
                m4 = _INLINE4_RE.search(rest)
                if m4:
                    options = [m4.group(i).strip() for i in range(1, 5)]

        if not q_text or options is None or correct is None:
            return None
        return _make_q(q_text, options, correct)

    # ── Format 7: True/False ───────────────────────────────────────────────

    def _s_true_false(self, lines: List[str]) -> Optional[Dict]:
        tf_idx = next((i for i, l in enumerate(lines) if _TF_RE.match(l)), None)
        if tf_idx is None:
            return None

        q_lines = lines[:tf_idx]
        if not q_lines:
            return None
        question = _clean_q(" ".join(q_lines))
        if len(question) < 8:
            return None

        correct: Optional[int] = None
        for line in lines[tf_idx + 1:]:
            m = _TF_ANS_RE.match(line)
            if m:
                correct = 0 if m.group(1).lower() == "true" else 1
                break

        if correct is None:
            return None

        options = ["True", "False", "Partially True", "Cannot be determined"]
        return _make_q(question, options, correct)

    # ── Format 1 / 2: Standard A/B/C/D labeled options ────────────────────

    def _s_standard_labeled(self, lines: List[str]) -> Optional[Dict]:
        q_lines: List[str] = []
        opt_lines: List[str] = []
        ans_line: Optional[str] = None

        for line in lines:
            if _SKIP_LINE_RE.match(line):
                continue
            if _ANS_RE.match(line):
                ans_line = line
            elif _is_option_line(line) and not (_is_question_line(line) and not q_lines):
                opt_lines.append(line)
            else:
                if not opt_lines:
                    q_lines.append(line)

        if not q_lines:
            return None
        question = _clean_q(" ".join(q_lines))
        if len(question) < 8:
            return None

        options, _ = self._extract_abcd(opt_lines)
        if options is None:
            return None

        correct: Optional[int] = None
        if ans_line:
            m = _ANS_RE.match(ans_line)
            if m:
                correct = _label_to_idx(m.group(1))

        if correct is None:
            return None
        return _make_q(question, options, correct)

    # ── Inline 4 options on same line ─────────────────────────────────────

    def _s_inline_opts(self, lines: List[str]) -> Optional[Dict]:
        full = " ".join(l for l in lines if not _SKIP_LINE_RE.match(l))

        correct: Optional[int] = None
        ans_m = _ANS_INLINE_RE.search(full)
        if ans_m:
            correct = _label_to_idx(ans_m.group(1))
            full = full[: ans_m.start()].rstrip()

        m = _INLINE4_RE.search(full)
        if not m:
            return None

        question = _clean_q(full[: m.start()])
        if len(question) < 8:
            return None

        options = [m.group(i).strip() for i in range(1, 5)]

        if correct is None:
            rest = full[m.end():]
            ans_m2 = _ANS_INLINE_RE.search(rest)
            correct = _label_to_idx(ans_m2.group(1)) if ans_m2 else None

        if correct is None:
            return None
        return _make_q(question, options, correct)

    # ── Numbered options 1./2./3./4. ──────────────────────────────────────

    def _s_numbered_opts(self, lines: List[str]) -> Optional[Dict]:
        ans_idx: Optional[int] = None
        ans_line_pos: Optional[int] = None

        for i, line in enumerate(lines):
            if _SKIP_LINE_RE.match(line):
                continue
            m = _ANS_RE.match(line)
            if m:
                ans_idx = _label_to_idx(m.group(1))
                ans_line_pos = i
                break

        if ans_idx is None:
            return None

        content = [l for l in lines[:ans_line_pos] if not _SKIP_LINE_RE.match(l)]
        opt_pairs: List[Tuple[int, str]] = []
        q_lines: List[str] = []

        for line in content:
            num_m = re.match(r"^([1-4])[\.)\s]+(.+)$", line)
            if num_m and len(line) < 80:
                opt_pairs.append((int(num_m.group(1)) - 1, num_m.group(2).strip()))
            else:
                if not opt_pairs:
                    q_lines.append(line)

        if len(opt_pairs) < 4:
            return None

        question = _clean_q(" ".join(q_lines))
        if len(question) < 8:
            return None

        options: List[Optional[str]] = [None, None, None, None]
        for idx, text in opt_pairs[:4]:
            if 0 <= idx <= 3:
                options[idx] = text

        if None in options:
            return None
        return _make_q(question, options, ans_idx)  # type: ignore[arg-type]

    # ── Asterisk correct marker ────────────────────────────────────────────

    def _s_asterisk(self, lines: List[str]) -> Optional[Dict]:
        q_lines: List[str] = []
        opt_lines: List[str] = []

        for line in lines:
            if _SKIP_LINE_RE.match(line):
                continue
            if _is_option_line(line):
                opt_lines.append(line)
            elif not opt_lines:
                q_lines.append(line)

        if not q_lines or len(opt_lines) < 2:
            return None

        question = _clean_q(" ".join(q_lines))
        if len(question) < 8:
            return None

        options: List[str] = []
        correct: Optional[int] = None

        for line in opt_lines:
            is_correct = bool(_STAR_RE.search(line))
            clean = _STAR_RE.sub("", line).strip()
            _, text = _strip_opt_label(clean)
            options.append(text)
            if is_correct:
                correct = len(options) - 1

        if len(options) != 4 or correct is None:
            return None
        return _make_q(question, options, correct)

    # ── Loose / last-resort ────────────────────────────────────────────────

    def _s_loose(self, lines: List[str]) -> Optional[Dict]:
        question: Optional[str] = None
        options: List[str] = []
        correct: Optional[int] = None

        for line in lines:
            if _SKIP_LINE_RE.match(line):
                continue
            m = _ANS_RE.match(line)
            if m:
                correct = _label_to_idx(m.group(1))
                continue
            if _is_option_line(line) and not (_is_question_line(line) and not question):
                _, text = _strip_opt_label(line)
                options.append(text)
            elif not question:
                q = _clean_q(line)
                if len(q) >= 8:
                    question = q

        if not question or len(options) < 4 or correct is None:
            return None
        return _make_q(question, options[:4], correct)

    # ── Pending (no answer yet — to be filled by answer key) ──────────────

    def _s_pending(self, lines: List[str]) -> Optional[Dict]:
        """
        Return a partial question (correct_answer=None) when a valid question
        + 4 options exist but no answer line is present.  The answer will be
        supplied later from an answer-key section.
        """
        q_lines: List[str] = []
        opt_lines: List[str] = []

        for line in lines:
            if _SKIP_LINE_RE.match(line):
                continue
            if _ANS_RE.match(line):
                return None  # Has an answer line but earlier strategies missed it — don't double-count
            if _is_option_line(line) and not (_is_question_line(line) and not q_lines):
                opt_lines.append(line)
            else:
                if not opt_lines:
                    q_lines.append(line)

        if not q_lines:
            return None
        question = _clean_q(" ".join(q_lines))
        if len(question) < 8:
            return None

        # Try ABCD options
        options, _ = self._extract_abcd(opt_lines)
        if options is not None:
            return _make_q(question, options, None)  # type: ignore[arg-type]

        # Try inline 4-on-one-line
        full = " ".join(opt_lines)
        m4 = _INLINE4_RE.search(full)
        if m4:
            options = [m4.group(i).strip() for i in range(1, 5)]
            return _make_q(question, options, None)  # type: ignore[arg-type]

        return None

    # ── Helper ────────────────────────────────────────────────────────────

    def _extract_abcd(self, opt_lines: List[str]) -> Tuple[Optional[List[str]], None]:
        opts: List[Optional[str]] = [None, None, None, None]

        for line in opt_lines:
            m4 = _INLINE4_RE.match(line)
            if m4:
                return [m4.group(i).strip() for i in range(1, 5)], None
            idx, text = _strip_opt_label(line)
            if idx is not None and 0 <= idx <= 3:
                opts[idx] = text

        if None in opts:
            return None, None
        return opts, None  # type: ignore[return-value]


# ═══════════════════════════════════════════════════════════════════════════
#  UNIVERSAL QUIZ PARSER
# ═══════════════════════════════════════════════════════════════════════════

class UniversalQuizParser:
    """
    Two-pass parser.

    Pass 1: split text into question blocks, parse each block independently.
    Pass 2: extract all answer-key sections (including end-of-chapter keys),
            apply to questions that are still missing answers.
    """

    def __init__(self) -> None:
        self._block_parser = _BlockParser()

    def parse(self, text: str) -> Tuple[List[Dict], Dict]:
        raw_lines = text.splitlines()
        lines = [l.rstrip() for l in raw_lines]
        lines_scanned = len(lines)

        clean_lines, auto_fixed = self._preprocess(lines)

        key_map, key_line_set = _extract_answer_keys(clean_lines)

        blocks = self._split_blocks(clean_lines, key_line_set)
        blocks_found = len(blocks)

        questions: List[Dict] = []

        for block_lines, qnum in blocks:
            q = self._block_parser.parse(block_lines)
            if q is None:
                continue
            if qnum is not None:
                q["_qnum"] = qnum
            questions.append(q)

        key_applied = 0
        for q in questions:
            qnum = q.pop("_qnum", None)
            if q.get("correct_answer") is None and qnum in key_map:
                letter = key_map[qnum]
                idx = _label_to_idx(letter)
                if idx is None:
                    idx = self._match_text_answer(letter, q.get("options", []))
                if idx is not None:
                    q["correct_answer"] = idx
                    key_applied += 1

        # Drop questions still without answers
        questions = [q for q in questions if q.get("correct_answer") is not None]

        questions = self._dedup(questions)

        format_detected = self._detect_format(clean_lines, key_map, blocks_found)

        stats: Dict = {
            "lines_scanned":   lines_scanned,
            "format_detected": format_detected,
            "blocks_found":    blocks_found,
            "key_applied":     key_applied,
            "auto_fixed":      auto_fixed,
            "total_detected":  len(questions),
            "imported":        0,
            "skipped":         0,
            "failed":          0,
            "errors":          [],
        }
        return questions, stats

    # ── Pre-processing ─────────────────────────────────────────────────────

    def _preprocess(self, lines: List[str]) -> Tuple[List[str], int]:
        result: List[str] = []
        fixes = 0

        for line in lines:
            stripped = line.strip()

            if not stripped:
                result.append("")
                continue

            if _is_noise(stripped):
                result.append("")
                continue

            fixed = re.sub(r"^0\)", "O)", line)
            if fixed != line:
                fixes += 1

            result.append(fixed)

        return result, fixes

    # ── Block splitting ────────────────────────────────────────────────────

    def _split_blocks(
        self, lines: List[str], key_line_set: Set[int]
    ) -> List[Tuple[List[str], Optional[int]]]:
        segments: List[Tuple[List[str], Optional[int]]] = []
        seg: List[str] = []
        qnum: Optional[int] = None

        def flush() -> None:
            nonlocal seg, qnum
            content = [l for l in seg if l.strip()]
            if content:
                segments.append((content, qnum))
            seg.clear()
            qnum = None

        for i, line in enumerate(lines):
            if i in key_line_set:
                continue

            stripped = line.strip()

            if _is_separator(stripped):
                flush()
                continue

            if not stripped:
                flush()
                continue

            if _is_question_line(stripped):
                num, _ = _strip_q_prefix(stripped)
                if num is not None and not seg:
                    qnum = num
                elif num is not None and seg and self._block_has_opts(seg):
                    flush()
                    qnum = num

            seg.append(line)

        flush()

        # Fallback: single huge segment with no blank lines
        if len(segments) == 1 and len(segments[0][0]) > 6:
            segments = self._split_by_question_starts(segments[0][0])

        return segments

    def _block_has_opts(self, lines: List[str]) -> bool:
        return sum(1 for l in lines if _is_option_line(l.strip())) >= 2

    def _split_by_question_starts(
        self, lines: List[str]
    ) -> List[Tuple[List[str], Optional[int]]]:
        segments: List[Tuple[List[str], Optional[int]]] = []
        current: List[str] = []
        qnum: Optional[int] = None

        for line in lines:
            if self._is_true_question_start(line.strip()):
                if current and self._block_has_opts(current):
                    segments.append((current[:], qnum))
                    current = []
                num, _ = _strip_q_prefix(line.strip())
                qnum = num
            current.append(line)

        if current:
            segments.append((current, qnum))

        return segments if segments else [(lines, None)]

    def _is_true_question_start(self, line: str) -> bool:
        if not _is_question_line(line):
            return False
        text = _Q_NUM_RE.sub("", line).strip()
        if line.endswith("?"):
            return True
        if len(text) > 45:
            return True
        starters = ("who", "what", "which", "when", "where", "why", "how",
                     "whose", "find", "identify", "choose", "select", "state")
        return any(text.lower().startswith(w) for w in starters)

    # ── Answer text matching ───────────────────────────────────────────────

    def _match_text_answer(self, text: str, options: List[str]) -> Optional[int]:
        """Find best-matching option index when key provides text instead of a letter."""
        text_lower = text.strip().lower()
        best_idx: Optional[int] = None
        best_score = 0.0

        for i, opt in enumerate(options):
            score = _text_similarity(text_lower, opt.lower())
            if score > best_score:
                best_score = score
                best_idx = i

        return best_idx if best_score >= 0.5 else None

    # ── Near-duplicate removal ─────────────────────────────────────────────

    def _dedup(self, questions: List[Dict]) -> List[Dict]:
        seen: List[str] = []
        result: List[Dict] = []

        for q in questions:
            qtext = q["question"].lower()
            if not any(_text_similarity(qtext, s) > 0.85 for s in seen):
                seen.append(qtext)
                result.append(q)

        return result

    # ── Format detection ───────────────────────────────────────────────────

    def _detect_format(
        self, lines: List[str], key_map: Dict, blocks_found: int
    ) -> str:
        has_key = bool(key_map)
        has_tf = any(_TF_RE.match(l.strip()) for l in lines)
        has_inline = any(_INLINE4_RE.search(l) for l in lines)
        has_sol_book = any(
            re.match(r"^question\s*\d+\s*[:\-]", l, re.IGNORECASE) for l in lines
        )
        has_options_label = any(_OPTIONS_LABEL_RE.match(l.strip()) for l in lines)

        parts: List[str] = []

        if has_tf:
            parts.append("True/False")
        if has_sol_book or has_options_label:
            parts.append("Solution-book style")
        if has_inline:
            parts.append("MCQ (single-line)")
        elif blocks_found > 0:
            parts.append("MCQ (multi-line)")
        if has_key:
            parts.append("Answer Key at end")

        return ", ".join(parts) if parts else "Unknown"


# ═══════════════════════════════════════════════════════════════════════════
#  BULK IMPORT COORDINATOR
# ═══════════════════════════════════════════════════════════════════════════

def bulk_import(text: str, quiz_manager) -> Dict:
    """
    Parse *text* and add valid questions to *quiz_manager*.

    Returns a dict with keys:
        total_detected, imported, skipped, failed, errors,
        format_detected, lines_scanned, auto_fixed, key_applied,
        blocks_found.
    """
    parser = UniversalQuizParser()
    questions, stats = parser.parse(text)

    existing = {q["question"].strip().lower() for q in quiz_manager.questions}

    batch: List[Dict] = []
    skipped = 0
    errors: List[str] = []

    for item in questions:
        q_text = item.get("question", "").strip()
        options = item.get("options", [])
        correct = item.get("correct_answer")

        if not q_text or len(q_text) < 8:
            skipped += 1
            continue
        if not isinstance(options, list) or len(options) != 4:
            skipped += 1
            continue
        if not all(o and str(o).strip() for o in options):
            skipped += 1
            continue
        if correct is None or not (0 <= correct <= 3):
            skipped += 1
            continue
        if q_text.lower() in existing:
            skipped += 1
            continue

        item["category"] = guess_category(q_text)
        existing.add(q_text.lower())
        batch.append(item)

    imported = 0
    failed = 0

    if batch:
        try:
            res = quiz_manager.add_questions(batch)
            imported = res.get("added", 0)
            skipped += res.get("rejected", {}).get("duplicates", 0)
            errs = res.get("errors", [])
            failed += len(errs)
            errors = errs[:5]
        except Exception as exc:
            failed = len(batch)
            errors = [str(exc)]

    stats.update({
        "total_detected": len(questions),
        "imported":       imported,
        "skipped":        skipped,
        "failed":         failed,
        "errors":         errors,
    })

    logger.info(
        "bulk_import: scanned=%d blocks=%d detected=%d imported=%d "
        "skipped=%d failed=%d key_applied=%d format=%r",
        stats["lines_scanned"],
        stats["blocks_found"],
        stats["total_detected"],
        imported,
        skipped,
        failed,
        stats["key_applied"],
        stats["format_detected"],
    )

    return stats
