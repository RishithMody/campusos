"""C8-C9: the nine sentences, and the drift between the three places they live.

The template table exists in three independent places -- the frozen contract's
`ChannelSummary` description, the `template_id` enum beside it, and the renderer's own
constant dict. Nothing checked that they agree. A connector in another repository, very
likely in another language, makes a fourth copy, which is the largest privacy risk of
switching connectors: the table is the only thing standing between a room and free text.
"""

import json
import os
import re
from pathlib import Path

import pytest

from groupchat.render import SCHEMA, TEMPLATES, render

ROOT = Path(__file__).resolve().parents[3]
CORPUS = json.loads((Path(__file__).parent / "conformance.json").read_text())
ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*\"(.+?)\"\s*\|", re.M)


def contract_table():
    """The nine rows of the rendered-sentence table inside the frozen contract."""
    return dict(ROW.findall(SCHEMA["description"]))


@pytest.mark.privacy
def test_c8_contract_table_enum_and_renderer_all_agree():
    """C8. Exact match: no extras, no missing, in any of the three copies."""
    table = contract_table()
    enum = set(SCHEMA["properties"]["template_id"]["enum"])
    assert len(table) == 9, table
    assert set(table) == enum == set(TEMPLATES)
    assert table == TEMPLATES


@pytest.mark.privacy
def test_c8_there_is_no_escape_hatch():
    """An `other` or `custom` id would reopen the whole hole the closed list closed."""
    enum = set(SCHEMA["properties"]["template_id"]["enum"])
    assert not {"other", "custom", "text", "freeform", "message"} & enum


@pytest.mark.privacy
def test_c8_no_template_interpolates_an_unbounded_string():
    """Every slot must be an integer or the formatted interval -- never free text."""
    allowed = {"participant_count", "round", "max_rounds", "agreed_slot"}
    for template_id, sentence in contract_table().items():
        slots = set(re.findall(r"\{(\w+)\}", sentence))
        assert slots <= allowed, (template_id, slots)


@pytest.mark.privacy
def test_c9_corpus_covers_every_template():
    """A corpus that skipped a template would let that one drift unnoticed."""
    covered = {case["summary"]["template_id"] for case in CORPUS["cases"]}
    assert covered == set(SCHEMA["properties"]["template_id"]["enum"])


@pytest.mark.privacy
@pytest.mark.parametrize("case", CORPUS["cases"], ids=lambda c: c["id"])
def test_c9_reference_renderer_matches_the_corpus(case):
    """C9, our half. The corpus is hand-written from the contract, so this is not circular."""
    if case.get("expect_refused"):
        with pytest.raises(ValueError):
            render(case["summary"], case["summary"]["negotiation_id"])
        return
    rendered = render(case["summary"], case["summary"]["negotiation_id"])
    assert rendered == case["expect_text"]


@pytest.mark.skipif(
    not os.environ.get("CAMPUSOS_CONNECTOR_RESULTS"),
    reason=(
        "BLOCKED: C9's connector half needs the connector. Set CAMPUSOS_CONNECTOR_RESULTS "
        "to a JSON file mapping each conformance.json case id to the string that connector "
        "rendered (or null if it refused). See task-graph T7c."
    ),
)
@pytest.mark.privacy
def test_c9_connector_renderer_matches_the_corpus():
    """C9, the other half. Runs unchanged the moment a connector produces its results."""
    results = json.loads(Path(os.environ["CAMPUSOS_CONNECTOR_RESULTS"]).read_text())
    assert set(results) == {case["id"] for case in CORPUS["cases"]}
    for case in CORPUS["cases"]:
        actual = results[case["id"]]
        if case.get("expect_refused"):
            assert actual is None, case["id"]
        else:
            assert actual == case["expect_text"], case["id"]


@pytest.mark.privacy
def test_the_corpus_is_the_published_artifact():
    """It is handed to the connector's authors, so it must stay self-describing."""
    assert CORPUS["about"]
    assert (ROOT / "tests/integration/connector/conformance.json").exists()
