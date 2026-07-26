import pytest

from assistant.modules.job_search.parsing import PostingParseError, infer_market, parse_posting


class TestInferMarket:
    def test_defaults_to_remote_when_no_singapore_signal(self) -> None:
        assert infer_market("Backend Engineer\nAcme Corp\nFully remote, US timezones.") == "remote"

    def test_infers_sg_when_singapore_is_mentioned(self) -> None:
        assert infer_market("Backend Engineer\nAcme Corp\nBased in Singapore.") == "sg"

    def test_singapore_match_is_case_insensitive(self) -> None:
        assert infer_market("Role based in SINGAPORE, on-site.") == "sg"

    def test_does_not_match_singapore_as_a_substring(self) -> None:
        assert infer_market("We use Singaporean vendors but the role is remote.") == "remote"


class TestParsePosting:
    def test_extracts_title_and_company_from_labeled_lines(self) -> None:
        text = "Title: AI Engineer\nCompany: Anthropic\n\nWe build helpful AI.\n"

        posting = parse_posting(text)

        assert posting.title == "AI Engineer"
        assert posting.company == "Anthropic"

    def test_extracts_title_and_company_from_job_title_label(self) -> None:
        text = "Job Title: Staff Engineer\nCompany: Acme Corp\n"

        posting = parse_posting(text)

        assert posting.title == "Staff Engineer"
        assert posting.company == "Acme Corp"

    def test_falls_back_to_first_two_lines_when_unlabeled(self) -> None:
        text = "Senior Backend Engineer\nAcme Corp\nRemote, full-time.\n"

        posting = parse_posting(text)

        assert posting.title == "Senior Backend Engineer"
        assert posting.company == "Acme Corp"

    def test_splits_title_at_company_on_first_line(self) -> None:
        text = "AI Engineer at Anthropic\n\nSan Francisco, CA.\n"

        posting = parse_posting(text)

        assert posting.title == "AI Engineer"
        assert posting.company == "Anthropic"

    def test_market_is_inferred_when_not_overridden(self) -> None:
        text = "AI Engineer at Anthropic\nBased in Singapore.\n"

        posting = parse_posting(text)

        assert posting.market == "sg"

    def test_market_override_wins_over_inference(self) -> None:
        text = "AI Engineer at Anthropic\nBased in Singapore.\n"

        posting = parse_posting(text, market="remote")

        assert posting.market == "remote"

    def test_url_is_carried_through_untouched(self) -> None:
        text = "AI Engineer at Anthropic\n"

        posting = parse_posting(text, url="https://example.com/job/123")

        assert posting.url == "https://example.com/job/123"

    def test_url_defaults_to_none(self) -> None:
        posting = parse_posting("AI Engineer at Anthropic\n")

        assert posting.url is None

    def test_extracts_bulleted_requirements(self) -> None:
        text = (
            "AI Engineer at Anthropic\n\n"
            "Requirements:\n"
            "- 5+ years of Python\n"
            "* Experience with distributed systems\n"
            "• Strong communication skills\n"
        )

        posting = parse_posting(text)

        assert posting.requirements == [
            "5+ years of Python",
            "Experience with distributed systems",
            "Strong communication skills",
        ]

    def test_no_requirements_yields_empty_list(self) -> None:
        posting = parse_posting("AI Engineer at Anthropic\n")

        assert posting.requirements == []

    def test_extracts_capitalized_keywords_from_requirements_and_skips_stopwords(self) -> None:
        text = (
            "AI Engineer at Anthropic\n\n"
            "Requirements:\n"
            "- Strong experience with Python and AWS\n"
            "- Familiarity with Kubernetes\n"
        )

        posting = parse_posting(text)

        assert posting.keywords == ["Python", "AWS", "Kubernetes"]

    def test_keywords_are_deduplicated_preserving_first_occurrence(self) -> None:
        text = (
            "AI Engineer at Anthropic\n\n"
            "Requirements:\n"
            "- Strong Python skills\n"
            "- Familiarity with Python and some Go\n"
        )

        posting = parse_posting(text)

        assert posting.keywords == ["Python", "Go"]

    def test_raises_on_empty_text(self) -> None:
        with pytest.raises(PostingParseError):
            parse_posting("")

    def test_raises_when_no_title_can_be_determined(self) -> None:
        with pytest.raises(PostingParseError):
            parse_posting("\n\n   \n")
