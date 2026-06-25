from app.config import Settings


def test_timeframe_list_parses_csv():
    s = Settings(timeframes="D1, H4 , M5")
    assert s.timeframe_list == ["D1", "H4", "M5"]


def test_defaults_present():
    s = Settings()
    assert s.symbol == "XAU_USD"
    assert s.signal_threshold == 55
