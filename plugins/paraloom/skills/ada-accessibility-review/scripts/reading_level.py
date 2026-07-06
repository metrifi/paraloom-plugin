"""Reading-level metrics: Flesch-Kincaid Grade Level, SMOG, and Gunning Fog.

The formulas are simple; the only nontrivial primitive is a syllable counter.
We use a vowel-cluster heuristic that's good enough for English prose. Where a
real-world deployment cares about precision, swap in `pyphen`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


# Sentence splitter that handles common abbreviations. We keep this simple on
# purpose — over-engineered sentence segmentation is a rabbit hole and the
# downstream metrics are robust to ±10% variance in sentence count.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _split_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    # Treat newline-paragraph breaks as sentence terminators when not already
    # punctuated, so headings and bullet lines count as sentences.
    parts = []
    for chunk in re.split(r"\n{2,}", text):
        chunk = chunk.strip()
        if not chunk:
            continue
        # If chunk has no terminal punctuation, append a period so the splitter
        # doesn't merge it into the next paragraph.
        if not re.search(r"[.!?]$", chunk):
            chunk = chunk + "."
        parts.extend(_SENTENCE_END.split(chunk))
    return [p.strip() for p in parts if p.strip()]


def _words(text: str) -> List[str]:
    return _WORD.findall(text)


def count_syllables(word: str) -> int:
    """Vowel-cluster heuristic.

    Lowercase the word, count vowel groups, drop a trailing silent 'e', and
    enforce a minimum of one syllable per token. This is intentionally cheap;
    the reading-level formulas are tolerant to small per-word errors because
    they aggregate across hundreds of words.
    """
    w = word.lower().strip("'\"-")
    if not w:
        return 0
    # Strip non-letters defensively.
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    # Count vowel groups (a, e, i, o, u, y at non-initial position).
    groups = re.findall(r"[aeiouy]+", w)
    count = len(groups)
    # Silent trailing 'e'.
    if w.endswith("e") and count > 1 and not w.endswith("le"):
        count -= 1
    # 'ed' is often silent at end of word.
    if w.endswith("ed") and count > 1:
        if not re.search(r"[td]ed$", w):  # 'visited' keeps the syllable
            count -= 1
    return max(count, 1)


def is_complex_word(word: str) -> bool:
    """Gunning Fog 'complex word': 3+ syllables, not a proper noun, not formed
    by adding common suffixes (-es, -ed, -ing) to a simpler root.

    This is the standard Fog definition; we don't try to detect proper nouns
    perfectly — for marketing prose, the noise is acceptable.
    """
    if word[:1].isupper() and not word.isupper():
        return False  # likely proper noun
    syll = count_syllables(word)
    if syll < 3:
        return False
    lower = word.lower()
    for suffix in ("es", "ed", "ing"):
        if lower.endswith(suffix):
            stem = lower[: -len(suffix)]
            if count_syllables(stem) < 3:
                return False
    return True


@dataclass
class ReadingLevelMetrics:
    flesch_kincaid_grade: float
    smog_index: float
    gunning_fog: float
    sentence_count: int
    word_count: int
    syllable_count: int
    complex_word_count: int
    avg_words_per_sentence: float
    avg_syllables_per_word: float
    sentence_grades: List[tuple]  # [(sentence_text, grade), ...]


def compute_metrics(text: str) -> ReadingLevelMetrics:
    sentences = _split_sentences(text)
    words: List[str] = []
    for s in sentences:
        words.extend(_words(s))

    sentence_count = max(len(sentences), 1)
    word_count = max(len(words), 1)
    syllable_count = sum(count_syllables(w) for w in words)
    complex_words = [w for w in words if is_complex_word(w)]
    complex_count = len(complex_words)

    avg_wps = word_count / sentence_count
    avg_spw = syllable_count / word_count

    # Flesch-Kincaid Grade Level
    fk = 0.39 * avg_wps + 11.8 * avg_spw - 15.59

    # Gunning Fog
    fog = 0.4 * (avg_wps + 100.0 * complex_count / word_count)

    # SMOG: sample of 30 sentences, polysyllable count.
    # Standard formula: 1.0430 * sqrt(polysyllables * (30 / sentence_count)) + 3.1291.
    # For short docs we use the variant that scales the polysyllable count
    # proportionally rather than requiring 30 sentences exactly.
    polysyll = sum(1 for w in words if count_syllables(w) >= 3)
    if sentence_count >= 30:
        smog = 1.0430 * ((polysyll * (30.0 / sentence_count)) ** 0.5) + 3.1291
    else:
        # Scaled SMOG: pretend the 30-sentence sample contained
        # polysyll * (30 / sentence_count) polysyllabic words. For very short
        # docs the result is noisy, which we surface in the report.
        scaled = polysyll * (30.0 / sentence_count) if sentence_count else 0
        smog = 1.0430 * (scaled ** 0.5) + 3.1291

    # Per-sentence grade for surfacing the hardest passages.
    sentence_grades = []
    for s in sentences:
        sw = _words(s)
        if len(sw) < 3:
            continue
        sw_count = len(sw)
        ss_count = sum(count_syllables(w) for w in sw)
        s_avg_wps = sw_count  # treat each as one sentence
        s_avg_spw = ss_count / sw_count
        s_fk = 0.39 * s_avg_wps + 11.8 * s_avg_spw - 15.59
        sentence_grades.append((s, round(s_fk, 1)))

    return ReadingLevelMetrics(
        flesch_kincaid_grade=round(fk, 1),
        smog_index=round(smog, 1),
        gunning_fog=round(fog, 1),
        sentence_count=sentence_count,
        word_count=word_count,
        syllable_count=syllable_count,
        complex_word_count=complex_count,
        avg_words_per_sentence=round(avg_wps, 1),
        avg_syllables_per_word=round(avg_spw, 2),
        sentence_grades=sentence_grades,
    )


def hardest_sentences(metrics: ReadingLevelMetrics, n: int = 3) -> List[tuple]:
    """Return top-n sentences ranked by sentence-level Flesch-Kincaid grade."""
    return sorted(metrics.sentence_grades, key=lambda x: x[1], reverse=True)[:n]


def suggest_simplification(sentence: str) -> str:
    """Generate a deliberately conservative simplification suggestion.

    We don't try to rewrite the sentence — that's the writer's job and an LLM
    is far better suited than a heuristic. We surface the structural reasons
    the sentence is hard so the writer knows where to look.
    """
    sw = _words(sentence)
    if not sw:
        return "Sentence is empty after word extraction."
    syll_per_word = sum(count_syllables(w) for w in sw) / len(sw)
    long_words = [w for w in sw if count_syllables(w) >= 3]
    notes = []
    if len(sw) > 25:
        notes.append(f"break this {len(sw)}-word sentence into two or more")
    if syll_per_word > 1.8:
        notes.append("swap multi-syllable words for shorter equivalents")
    if long_words:
        sample = ", ".join(sorted(set(long_words))[:5])
        notes.append(f"reword: {sample}")
    if not notes:
        notes.append("consider whether this sentence carries one idea or several")
    return "; ".join(notes)
