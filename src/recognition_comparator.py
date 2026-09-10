from dataclasses import dataclass
import re


# =========================================================
# Configuration
# =========================================================

INSERTION_COST = 0.60
DELETION_COST = 0.60

# Similarity above this is displayed as a normal match.
MATCH_THRESHOLD = 0.70

# Penalty for an extra recognized word.
EXTRA_PENALTY = 0.25


# =========================================================
# Normalization
# =========================================================

def normalize_word(word: str) -> str:
    """
    Basic normalization.

    This is intentionally simple.
    Later this is a good place to add:
      - Ukrainian-specific normalization
      - spelling normalization
      - lemmatization
    """
    word = word.lower().strip()

    # Remove punctuation around words.
    word = re.sub(
        r"^[^\wа-яіїєґ'-]+|[^\wа-яіїєґ'-]+$",
        "",
        word,
    )

    return word


def normalize_words(words: list[str]) -> list[str]:
    result = []

    for word in words:
        normalized = normalize_word(word)

        if normalized:
            result.append(normalized)

    return result


# =========================================================
# Character/token similarity
# =========================================================

def levenshtein_distance(a: str, b: str) -> int:
    """
    Character-level Levenshtein distance.
    """

    if len(a) < len(b):
        a, b = b, a

    previous = list(range(len(b) + 1))

    for i, char_a in enumerate(a, 1):
        current = [i]

        for j, char_b in enumerate(b, 1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (char_a != char_b)

            current.append(
                min(insert, delete, replace)
            )

        previous = current

    return previous[-1]


def token_similarity(expected: str, actual: str) -> float:
    """
    Compare two individual word/tokens.

    1.0 = identical
    0.0 = completely different

    This is the main extension point for future
    Ukrainian/ASR-specific improvements.
    """

    expected = normalize_word(expected)
    actual = normalize_word(actual)

    if not expected or not actual:
        return 0.0

    # Exact token match.
    if expected == actual:
        return 1.0

    # Character-level fuzzy match.
    distance = levenshtein_distance(
        expected,
        actual,
    )

    return 1.0 - distance / max(
        len(expected),
        len(actual),
    )


# =========================================================
# Alignment result
# =========================================================

@dataclass
class Difference:
    type: str
    expected: str | None
    actual: str | None
    similarity: float = 0.0


# =========================================================
# Global word alignment
# =========================================================

def align_tokens(
    actual: list[str],
    expected: list[str],
) -> list[Difference]:
    """
    Globally align recognized tokens against expected tokens.

    Operations:

        replace  -> expected <-> actual
        delete   -> expected word is missing
        insert   -> actual word is extra

    Unlike a greedy comparison, this considers the
    complete sequence and avoids cascading mismatches.
    """

    expected_count = len(expected)
    actual_count = len(actual)

    # DP cost matrix.
    dp = [
        [0.0] * (actual_count + 1)
        for _ in range(expected_count + 1)
    ]

    # Backtracking matrix.
    back = [
        [None] * (actual_count + 1)
        for _ in range(expected_count + 1)
    ]

    # Missing expected words.
    for i in range(1, expected_count + 1):
        dp[i][0] = (
            dp[i - 1][0]
            + DELETION_COST
        )

        back[i][0] = "delete"

    # Extra recognized words.
    for j in range(1, actual_count + 1):
        dp[0][j] = (
            dp[0][j - 1]
            + INSERTION_COST
        )

        back[0][j] = "insert"

    # Fill DP matrix.
    for i in range(1, expected_count + 1):
        for j in range(1, actual_count + 1):

            expected_token = expected[i - 1]
            actual_token = actual[j - 1]

            similarity = token_similarity(
                expected_token,
                actual_token,
            )

            # Matching two tokens.
            #
            # exact match:
            #     similarity = 1.0
            #     cost = 0.0
            #
            # fuzzy match:
            #     similarity < 1.0
            #     cost > 0.0
            replace = (
                dp[i - 1][j - 1]
                + (1.0 - similarity)
            )

            # Expected token is missing.
            delete = (
                dp[i - 1][j]
                + DELETION_COST
            )

            # Actual token is extra.
            insert = (
                dp[i][j - 1]
                + INSERTION_COST
            )

            best = min(
                replace,
                delete,
                insert,
            )

            dp[i][j] = best

            if best == replace:
                back[i][j] = "replace"

            elif best == delete:
                back[i][j] = "delete"

            else:
                back[i][j] = "insert"

    # -----------------------------------------------------
    # Backtrack
    # -----------------------------------------------------

    differences = []

    i = expected_count
    j = actual_count

    while i > 0 or j > 0:

        operation = back[i][j]

        if operation == "replace":

            expected_token = expected[i - 1]
            actual_token = actual[j - 1]

            similarity = token_similarity(
                expected_token,
                actual_token,
            )

            difference_type = (
                "match"
                if similarity >= MATCH_THRESHOLD
                else "changed"
            )

            differences.append(
                Difference(
                    type=difference_type,
                    expected=expected_token,
                    actual=actual_token,
                    similarity=similarity,
                )
            )

            i -= 1
            j -= 1

        elif operation == "delete":

            differences.append(
                Difference(
                    type="missing",
                    expected=expected[i - 1],
                    actual=None,
                    similarity=0.0,
                )
            )

            i -= 1

        elif operation == "insert":

            differences.append(
                Difference(
                    type="extra",
                    expected=None,
                    actual=actual[j - 1],
                    similarity=0.0,
                )
            )

            j -= 1

    differences.reverse()

    return differences


# =========================================================
# Score
# =========================================================

def calculate_score(
    differences: list[Difference],
    expected_count: int,
) -> float:
    """
    Calculate recognition score from 0.0 to 1.0.

    Matching/fuzzy words contribute their similarity.
    Missing words contribute 0.
    Extra words receive a small penalty.
    """

    if expected_count == 0:
        return 1.0 if not differences else 0.0

    score = 0.0

    for difference in differences:

        if difference.type in (
            "match",
            "changed",
        ):
            score += difference.similarity

        elif difference.type == "extra":
            score -= EXTRA_PENALTY

        # "missing" contributes 0.

    score /= expected_count

    return max(
        0.0,
        min(1.0, score),
    )


# =========================================================
# Main API
# =========================================================

def compare_with_etalon(
    words: list[str],
    etalon: list[str],
) -> tuple[float, list[dict]]:
    """
    Compare recognized speech with an etalon.

    Returns:

        score:
            float from 0.0 to 1.0

        differences:
            list describing the alignment.
    """

    actual = normalize_words(words)
    expected = normalize_words(etalon)

    # Nothing expected.
    if not expected:

        differences = [
            {
                "type": "extra",
                "expected": None,
                "actual": word,
                "similarity": 0.0,
            }
            for word in actual
        ]

        return (
            1.0 if not actual else 0.0,
            differences,
        )

    differences = align_tokens(
        actual=actual,
        expected=expected,
    )

    score = calculate_score(
        differences=differences,
        expected_count=len(expected),
    )

    # Convert dataclasses to dictionaries
    # to keep the public API simple.
    result = []

    for difference in differences:
        result.append(
            {
                "type": difference.type,
                "expected": difference.expected,
                "actual": difference.actual,
                "similarity": round(
                    difference.similarity,
                    3,
                ),
            }
        )

    return score, result
