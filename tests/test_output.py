import json
from datetime import timedelta

from conftest import NOW

from gridhour import output
from gridhour.plan import Job


def test_line(st):
    assert output.line_output(st, NOW) == "⚡ 251g · 30p · green in 7h30"


def test_line_green_now(st):
    assert output.line_output(st, NOW.replace(hour=6, minute=40) + timedelta(days=1)).endswith("green now")


def test_line_without_prices(st):
    for s in st.fc.slots:
        s.price = None
    assert output.line_output(st, NOW) == "⚡ 251g · green in 7h30"


def test_line_best(st):
    assert output.line_output(st, NOW, best=Job("job", 120)) == "⚡ 251g · 30p · 2h best 12:00 (in 12h)"


def test_line_colours(st):
    tmux = output.line_output(st, NOW, "tmux")
    assert tmux.count("#[fg=#") == 3 and "#[default]" in tmux
    assert "\x1b[38;2;" in output.line_output(st, NOW, "ansi")


def test_line_without_data(st):
    st.fc.slots = []
    st.fc.errors = ["network: down"]
    assert output.line_output(st, NOW) == "⚡ network: down"


def test_json(st):
    doc = json.loads(output.json_output(st, NOW))
    assert doc["region"] == {"id": 13, "name": "London", "postcode": "SW1A"}
    assert doc["now"]["carbon"] == 251 and doc["now"]["price"] == 30.18
    assert doc["green_now"] is False and doc["next_green"]["from"] == "2026-10-04T06:30Z"
    washing = doc["jobs"][0]
    assert washing["name"] == "Washing" and washing["best"]["from"] == "2026-10-04T11:00Z"
    assert washing["best"]["starts_in_minutes"] == 734
    assert len(doc["slots"]) == 96
