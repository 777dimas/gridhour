import json
from datetime import timedelta, timezone

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


def test_ical_time():
    assert output._ical_time(NOW) == "20261003T224600Z"
    local = NOW.astimezone(timezone(timedelta(hours=8)))
    assert output._ical_time(local) == "20261003T224600Z"


def test_ical_text():
    text = "Wash\\dry; cheap, green\r\nnext\rlast\nend"
    assert output._ical_text(text) == (
        "Wash\\\\dry\\; cheap\\, green\\nnext\\nlast\\nend"
    )


def test_ical_uid():
    start = NOW.replace(hour=23, minute=30)
    uid = output._ical_uid("Washing", start, 1)

    # During British summer time, both timestamps fall on October 4 in the UK.
    assert uid == output._ical_uid("Washing", start + timedelta(hours=2), 1)
    assert uid != output._ical_uid("Washing", start + timedelta(days=1), 1)
    assert uid != output._ical_uid("Washing", start, 2)
    assert uid != output._ical_uid("Dryer", start, 1)
    assert len(uid.split("@")[0]) == 40
    assert uid.endswith("@gridhour")


def test_ical_fold():
    assert output._ical_fold("a" * 75) == "a" * 75
    assert output._ical_fold("a" * 76) == "a" * 75 + "\r\n a"

    text = "SUMMARY:" + "é" * 100
    folded = output._ical_fold(text)
    lines = folded.split("\r\n")

    assert all(len(line.encode("utf-8")) <= 75 for line in lines)
    assert all(line.startswith(" ") for line in lines[1:])
    assert folded.replace("\r\n ", "") == text


def test_ical_document():
    lines = ["BEGIN:VCALENDAR", "END:VCALENDAR"]
    assert output._ical_document(lines) == (
        "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n"
    )


def test_ical_empty(st):
    st.jobs = []
    assert output.ical_output(st, NOW) == (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//gridhour//Job windows//EN\r\n"
        "END:VCALENDAR\r\n"
    )


def test_ical_job(st):
    st.jobs = [Job("Washing", 120)]
    doc = output.ical_output(st, NOW)

    assert doc.count("BEGIN:VEVENT\r\n") == 1
    assert doc.count("END:VEVENT\r\n") == 1
    assert "SUMMARY:Washing (gridhour)\r\n" in doc
    assert "DTSTAMP:20261003T224600Z\r\n" in doc
    assert "DTSTART:20261004T110000Z\r\n" in doc
    assert "DTEND:20261004T130000Z\r\n" in doc
    assert "UID:" in doc
    assert doc.endswith("END:VCALENDAR\r\n")


def test_ical_description(st):
    st.jobs = [Job("Washing", 120)]
    best = json.loads(output.json_output(st, NOW))["jobs"][0]["best"]
    description = (
        "Best window average: carbon %.1f gCO2/kWh; price %.2f p/kWh"
        % (best["carbon"], best["price"])
    )

    doc = output.ical_output(st, NOW).replace("\r\n ", "")
    assert "DESCRIPTION:" + output._ical_text(description) + "\r\n" in doc


def test_ical_split_job(st):
    st.mode = "cheap"
    st.jobs = [Job("EV charge", 90, split=True)]
    st.fc.slots = [s for s in st.fc.slots if s.start >= NOW][:6]

    for slot, price in zip(st.fc.slots, [1, 100, 2, 100, 3, 100], strict=True):
        slot.price = price

    doc = output.ical_output(st, NOW).replace("\r\n ", "")
    assert doc.count("BEGIN:VEVENT\r\n") == 3

    for number, index in enumerate([0, 2, 4], start=1):
        slot = st.fc.slots[index]
        summary = "EV charge (gridhour) (part %d of 3)" % number
        assert "SUMMARY:" + summary + "\r\n" in doc
        assert "DTSTART:" + output._ical_time(slot.start) + "\r\n" in doc
        assert "DTEND:" + output._ical_time(slot.end) + "\r\n" in doc


def test_ical_no_window(st):
    st.jobs = [Job("Washing", 120)]
    st.fc.slots = []

    doc = output.ical_output(st, NOW)

    assert "BEGIN:VEVENT" not in doc
    assert doc.startswith("BEGIN:VCALENDAR\r\n")
    assert doc.endswith("END:VCALENDAR\r\n")


def test_ical_without_prices(st):
    st.jobs = [Job("Washing", 120)]
    for slot in st.fc.slots:
        slot.price = None

    doc = output.ical_output(st, NOW).replace("\r\n ", "")

    assert doc.count("BEGIN:VEVENT\r\n") == 1
    assert "price unknown\r\n" in doc
    assert "SUMMARY:Washing (gridhour)\r\n" in doc


def test_ical_safe_job_name(st):
    st.jobs = [Job("Wash\\dry; cheap, green\r\nBEGIN:VEVENT", 120)]

    doc = output.ical_output(st, NOW).replace("\r\n ", "")

    assert doc.count("BEGIN:VEVENT\r\n") == 1
    assert (
        "SUMMARY:Wash\\\\dry\\; cheap\\, green??BEGIN:VEVENT (gridhour)\r\n"
    ) in doc


def test_ical_repeated_export(st):
    st.jobs = [Job("Washing", 120)]

    first = output.ical_output(st, NOW)
    second = output.ical_output(st, NOW + timedelta(minutes=1))

    first_uids = [line for line in first.split("\r\n") if line.startswith("UID:")]
    second_uids = [line for line in second.split("\r\n") if line.startswith("UID:")]

    assert len(first_uids) == 1
    assert first_uids == second_uids
    assert "DTSTAMP:20261003T224600Z\r\n" in first
    assert "DTSTAMP:20261003T224700Z\r\n" in second
