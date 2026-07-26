from assistant.core.store.parser import parse_achievements, parse_frontmatter, slugify


def test_parse_frontmatter_splits_yaml_block_from_body() -> None:
    text = "---\ntype: role\ncompany: Acme Corp\n---\n## Context\nSome prose.\n"

    frontmatter, body = parse_frontmatter(text)

    assert frontmatter == {"type": "role", "company": "Acme Corp"}
    assert body == "## Context\nSome prose.\n"


def test_parse_frontmatter_handles_missing_frontmatter() -> None:
    text = "## Contact\nJamie Rivera\n"

    frontmatter, body = parse_frontmatter(text)

    assert frontmatter == {}
    assert body == text


def test_parse_frontmatter_handles_null_and_list_values() -> None:
    text = "---\nend: null\nskills: [csharp, dotnet-core]\n---\nbody\n"

    frontmatter, _ = parse_frontmatter(text)

    assert frontmatter == {"end": None, "skills": ["csharp", "dotnet-core"]}


def test_slugify_matches_the_schema_spec_example() -> None:
    assert slugify("Partner-bank onboarding automation") == "partner-bank-onboarding-automation"
    assert slugify("Settlement-service refactor") == "settlement-service-refactor"


def test_parse_achievements_extracts_headings_under_the_achievements_section() -> None:
    body = (
        "## Context\n"
        "Some context.\n"
        "\n"
        "## Achievements\n"
        "### Settlement-service refactor\n"
        "Collapsed several microservices.\n"
        "**Impact:** first integration tests.\n"
        "\n"
        "### Partner-bank onboarding automation\n"
        "Extended the settlement module.\n"
        "\n"
        "## Reflections\n"
        "Role-level lessons.\n"
    )

    achievements = parse_achievements(body)

    assert [a.heading for a in achievements] == [
        "Settlement-service refactor",
        "Partner-bank onboarding automation",
    ]
    assert [a.slug for a in achievements] == [
        "settlement-service-refactor",
        "partner-bank-onboarding-automation",
    ]
    assert (
        achievements[0].body
        == "Collapsed several microservices.\n**Impact:** first integration tests."
    )
    assert achievements[1].body == "Extended the settlement module."


def test_parse_achievements_returns_empty_tuple_when_no_achievements_section() -> None:
    body = "## Context\nJust context, no achievements.\n"

    assert parse_achievements(body) == ()


def test_parse_achievements_ignores_headings_outside_achievements_section() -> None:
    body = (
        "## Context\n"
        "### Not an achievement\n"
        "This heading is outside the Achievements section.\n"
        "\n"
        "## Achievements\n"
        "### Real achievement\n"
        "Body.\n"
    )

    achievements = parse_achievements(body)

    assert [a.heading for a in achievements] == ["Real achievement"]
