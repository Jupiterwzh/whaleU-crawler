from shared.rag.validity import judge_validity, extract_dates


def test_extract_dates():
    text = "报名时间：2026-03-01 至 2026-03-15，比赛时间 2026-04-01"
    dates = extract_dates(text)
    assert "2026-03-15" in dates
    assert "2026-04-01" in dates


def test_judge_no_timestamp_maps_impact():
    r = judge_validity("食堂将进行改造施工，工期约两个月")
    assert r["effective_days"] in (15, 30, 60, 90, 180)


def test_judge_explicit_until():
    r = judge_validity("选课时间：3月1日至3月15日，请按时完成选课", date="2026-03-01")
    assert r["valid_until"]
