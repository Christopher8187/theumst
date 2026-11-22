"""The word index: BM25 over each object's label, name and statement (0.0.19, the game's search).

A Qdrant collection of its own, `knowledge-words-bm25`, holds one point per knowledge object, its id the
object's knowledge_id, with one sparse vector `words`. A document's sparse vector carries, for each of its
terms, BM25's term-frequency part

    tf * (K1 + 1) / (tf + K1 * (1 - B + B * dl / AVGDL))

and Qdrant's `idf` modifier multiplies each term by its inverse document frequency over the collection
at query time. A query's sparse vector is 1 for each distinct term, so a point's score is the BM25 score of
the query against the object. AVGDL is a constant (the average over the 28 books of November 2026), so
a point never needs rewriting when other books arrive.

Every object of every book is indexed, hidden books included: what a reader may see is filtered at query
time by `grimoire_id`, so switching a book's visibility rewrites nothing. The payload holds the ids the
search needs (`knowledge_id`, `grimoire_id`) and `name_key`, the object's name in index
form, so the latcher's route can find names a text mentions through a keyword index. No text of an
object is kept in the collection beyond that name key. `scripts/fill_word_index.py` fills it.

Terms: Unicode letters and digits, lower-cased with accents dropped, at least two characters, common English
words and LaTeX command words dropped, and a light plural fold ("groups" -> "group"). Each term is hashed to
a 32-bit index, so the index needs no vocabulary.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from typing import Any, Iterable

COLLECTION = "knowledge-words-bm25"
SPARSE_NAME = "words"
K1 = 1.2
B = 0.75
# The average number of terms in label + name + statement over the 28 books on theumst.com on
# 22 November 2026 (fill_word_index prints the average of what it indexes).
AVGDL = 18.0
PAYLOAD_INDEXES = {
    "knowledge_id": "integer",
    "grimoire_id": "integer",
    "name_key": "keyword",
}

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset(
    """
    a an and are as at be been being but by can do does for from had has have he her his how i if in into is it
    its let may me more most must my no not of on one or our she so such than that the their them then there
    these they this those thus to two was we were what when where which while who will with would you your
    any all each every some also only both either neither nor very same other another
    frac mathbb mathcal mathrm mathbf mathfrak mathit operatorname text textbf textit left right cdot cdots
    ldots dots vdots ddots quad qquad begin end displaystyle limits hat bar tilde overline underline
    """.split()
)


def _folded(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def raw_words(text: str) -> list[str]:
    """The text's words in order, folded, nothing dropped: the form of a name key and its n-grams."""
    return _WORD.findall(_folded(text))


_UNSTEMMED = frozenset({"series", "species"})


def _stem(word: str) -> str:
    if word in _UNSTEMMED:
        return word
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("sses", "xes", "ches", "shes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def terms(text: str) -> list[str]:
    """The BM25 terms of a text, in order, repeats kept."""
    return [_stem(word) for word in raw_words(text) if len(word) >= 2 and word not in _STOP]


def term_index(term: str) -> int:
    """A term's index in the sparse vector: the first 32 bits of its BLAKE2b hash."""
    return int.from_bytes(hashlib.blake2b(term.encode("utf-8"), digest_size=4).digest(), "big")


def name_key(name: str) -> str:
    """A name in index form: its folded words joined by single spaces."""
    return " ".join(raw_words(name))


def document_text(label: str | None, name: str | None, statement: str | None) -> str:
    return " ".join(part for part in (label or "", name or "", statement or "") if part)


def document_vector(label: str | None, name: str | None, statement: str | None,
                    *, avgdl: float = AVGDL) -> dict[str, list]:
    """An object's sparse vector: BM25's term-frequency part for each of its terms."""
    found = terms(document_text(label, name, statement))
    return _tf_vector(Counter(found), len(found), avgdl)


def _tf_vector(counts: Counter, length: int, avgdl: float) -> dict[str, list]:
    weights: dict[int, float] = {}
    norm = K1 * (1 - B + B * length / avgdl) if length else K1
    for term, tf in counts.items():
        index = term_index(term)
        weights[index] = weights.get(index, 0.0) + tf * (K1 + 1) / (tf + norm)
    indices = sorted(weights)
    return {"indices": indices, "values": [round(weights[i], 6) for i in indices]}


def query_vector(texts: Iterable[str]) -> dict[str, list]:
    """A query's sparse vector: 1 for each distinct term of the texts. Empty when they have none."""
    indices = sorted({term_index(term) for text in texts for term in terms(text)})
    return {"indices": indices, "values": [1.0] * len(indices)}


def point(row: dict[str, Any], *, avgdl: float = AVGDL) -> dict[str, Any]:
    """The word store's point for one object row (knowledge_id, grimoire_id, label, name, statement). A crystal
    is not kept: an upload may move an object to another crystal, and the search reads crystals from PostgreSQL."""
    return {
        "id": int(row["knowledge_id"]),
        "vector": {SPARSE_NAME: document_vector(row.get("label"), row.get("name"), row.get("statement"),
                                                avgdl=avgdl)},
        "payload": {
            "knowledge_id": int(row["knowledge_id"]),
            "grimoire_id": int(row["grimoire_id"]),
            "name_key": name_key(row.get("name") or ""),
        },
    }


def name_ngrams(text: str, *, shortest: int = 1, longest: int = 8, limit: int = 4000,
                min_single: int = 5) -> list[str]:
    """Every run of `shortest` to `longest` words of the text in name-key form, first seen first, at most
    `limit`. A single word counts only when it has at least `min_single` letters, so "set" or "map" alone
    never names an object."""
    words = raw_words(text)
    seen: dict[str, None] = {}
    for start in range(len(words)):
        for size in range(shortest, longest + 1):
            if start + size > len(words):
                break
            if size == 1 and (len(words[start]) < min_single or words[start] in _STOP):
                continue
            seen.setdefault(" ".join(words[start:start + size]), None)
            if len(seen) >= limit:
                return list(seen)
    return list(seen)
