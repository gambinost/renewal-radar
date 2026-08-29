from renewal_radar.matching import (
    MatchBand,
    classify_band,
    match_clients,
    name_similarity,
    normalize_name,
)


def test_normalize_strips_suffix_case_and_punctuation():
    assert normalize_name("Acme Co.") == "acme"
    assert normalize_name("ACME CO") == "acme"


def test_casing_punctuation_and_suffix_variants_auto_match():
    # PRD 6: casing, punctuation, legal suffix differences -> auto-match.
    pairs = [
        ("Acme Co.", "ACME CO"),
        ("Fresh & Co. Marketing", "Fresh and Co Marketing"),
        ("Pinnacle Systems Group", "Pinnacle Systems"),
        ("Amberfield & Sons", "Amberfield Sons Ltd"),
    ]
    for billing_name, project_name in pairs:
        score = name_similarity(billing_name, project_name)
        assert classify_band(score) is MatchBand.AUTO, (billing_name, project_name, score)


def test_genuine_typo_is_fuzzy_matched_not_just_normalized():
    score = name_similarity("Bluebird Creative Ltd", "Bluebrid Creative")
    assert classify_band(score) is MatchBand.AUTO


def test_superficially_similar_but_different_company_does_not_auto_match():
    # PRD 6: the case that breaks naive fixed-threshold matching. These are
    # two different real companies; the score is high enough to tempt a
    # single loose cutoff but must stay below the auto-match band.
    score = name_similarity("Meridian Health Partners", "Meridian Home Partners")
    assert classify_band(score) is not MatchBand.AUTO


def test_clearly_unrelated_names_score_below_review_band():
    score = name_similarity("Acme Co.", "Thornwood Brands")
    assert classify_band(score) is MatchBand.NONE


def test_match_clients_does_not_let_an_imposter_steal_the_correct_match():
    # Both "Meridian Health Partners" and "Meridian Home Partners" are present
    # on both sides. A naive per-row independent argmax could plausibly still
    # get this right by luck; this test locks in that the global assignment
    # pairs each with its own true match rather than either imposter pairing.
    billing_names = ["Meridian Health Partners", "Meridian Home Partners LLC"]
    project_names = ["Meridian Health Partners", "Meridian Home Partners"]

    results = match_clients(billing_names, project_names)
    by_billing = {r.billing_name: r for r in results}

    assert by_billing["Meridian Health Partners"].project_name == "Meridian Health Partners"
    assert by_billing["Meridian Home Partners LLC"].project_name == "Meridian Home Partners"
    assert by_billing["Meridian Health Partners"].band is MatchBand.AUTO
    assert by_billing["Meridian Home Partners LLC"].band is MatchBand.AUTO


def test_match_clients_flags_review_band_without_auto_matching():
    results = match_clients(["Thornwood Brand Partners"], ["Thornwood Brands"])
    assert len(results) == 1
    assert results[0].band is MatchBand.REVIEW


def test_match_clients_leaves_low_scoring_names_unmatched():
    results = match_clients(["Acme Co."], ["Thornwood Brands"])
    assert results == []
