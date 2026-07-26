from datetime import date, datetime
from pathlib import Path

from assistant.core.journal.capture import JournalEntry, add_entry, list_entries


def test_add_creates_todays_file_with_folded_false(tmp_path: Path) -> None:
    result = add_entry(tmp_path, "shipped the thing", now=datetime(2026, 7, 26, 18, 5))

    assert result.created is True
    assert result.path == tmp_path / "journal" / "2026-07-26.md"
    content = result.path.read_text()
    assert content == "---\nfolded: false\n---\n- 18:05 shipped the thing\n"


def test_add_appends_a_bullet_to_an_existing_pending_day(tmp_path: Path) -> None:
    add_entry(tmp_path, "first entry", now=datetime(2026, 7, 26, 9, 0))

    result = add_entry(tmp_path, "second entry", now=datetime(2026, 7, 26, 18, 5))

    assert result.created is False
    content = result.path.read_text()
    assert content == ("---\nfolded: false\n---\n- 09:00 first entry\n- 18:05 second entry\n")


def test_appending_to_an_already_folded_day_resets_the_flag(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "2026-07-17.md").write_text(
        "---\nfolded: true\n---\n"
        "## Folded\n"
        "- 14:20 shipped the queue integration ✓ → [[acme-platform-team]]\n"
    )

    result = add_entry(tmp_path, "new pending work", now=datetime(2026, 7, 17, 20, 0))

    assert result.reset_from_folded is True
    content = result.path.read_text()
    assert content == (
        "---\nfolded: false\n---\n"
        "- 20:00 new pending work\n\n"
        "## Folded\n"
        "- 14:20 shipped the queue integration ✓ → [[acme-platform-team]]\n"
    )


def test_wikilink_hints_pass_through_untouched(tmp_path: Path) -> None:
    result = add_entry(
        tmp_path, "praised for [[acme-platform-team]] work", now=datetime(2026, 7, 26, 8, 0)
    )

    assert "[[acme-platform-team]]" in result.path.read_text()


def test_list_returns_no_entries_when_vault_has_no_journal(tmp_path: Path) -> None:
    assert list_entries(tmp_path) == []


def test_list_shows_recent_entries_with_pending_and_folded_state(tmp_path: Path) -> None:
    add_entry(tmp_path, "old day, folded work", now=datetime(2026, 7, 17, 14, 20))
    journal_dir = tmp_path / "journal"
    (journal_dir / "2026-07-17.md").write_text(
        "---\nfolded: true\n---\n## Folded\n- 14:20 old day, folded work\n"
    )
    add_entry(tmp_path, "today's pending work", now=datetime(2026, 7, 26, 9, 0))

    entries = list_entries(tmp_path)

    assert entries == [
        _entry("2026-07-26", "09:00 today's pending work", folded=False),
        _entry("2026-07-17", "14:20 old day, folded work", folded=True),
    ]


def test_list_respects_limit_across_days(tmp_path: Path) -> None:
    add_entry(tmp_path, "day one", now=datetime(2026, 7, 24, 9, 0))
    add_entry(tmp_path, "day two", now=datetime(2026, 7, 25, 9, 0))
    add_entry(tmp_path, "day three", now=datetime(2026, 7, 26, 9, 0))

    entries = list_entries(tmp_path, limit=2)

    assert len(entries) == 2
    assert entries[0].date == date(2026, 7, 26)
    assert entries[1].date == date(2026, 7, 25)


def test_hand_written_obsidian_entries_are_indistinguishable(tmp_path: Path) -> None:
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir(parents=True)
    hand_written = journal_dir / "2026-07-26.md"
    hand_written.write_text(
        "---\nfolded: false\n---\n- jotted this straight into Obsidian, no timestamp\n"
    )

    entries_before = list_entries(tmp_path)
    result = add_entry(tmp_path, "captured via pa", now=datetime(2026, 7, 26, 12, 0))

    assert entries_before == [
        _entry("2026-07-26", "jotted this straight into Obsidian, no timestamp", folded=False)
    ]
    assert result.path == hand_written
    assert result.created is False
    assert hand_written.read_text() == (
        "---\nfolded: false\n---\n"
        "- jotted this straight into Obsidian, no timestamp\n"
        "- 12:00 captured via pa\n"
    )


def test_appending_never_drops_hand_written_content_that_is_not_a_flush_bullet(
    tmp_path: Path,
) -> None:
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir(parents=True)
    hand_written = journal_dir / "2026-07-26.md"
    hand_written.write_text(
        "---\nfolded: false\n---\n"
        "- 09:00 first bullet\n"
        "  a wrapped continuation line\n"
        "\n"
        "some loose prose jotted above the list\n"
    )

    result = add_entry(tmp_path, "captured via pa", now=datetime(2026, 7, 26, 12, 0))

    content = result.path.read_text()
    assert "a wrapped continuation line" in content
    assert "some loose prose jotted above the list" in content
    assert content.endswith("- 12:00 captured via pa\n")


def _entry(iso_date: str, text: str, *, folded: bool) -> JournalEntry:
    return JournalEntry(date=date.fromisoformat(iso_date), text=text, folded=folded)
