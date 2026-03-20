from roster_sync.dyflexis_client import DyflexisClient


def test_looks_like_roster_html_accepts_roster_markup():
    html = '<html><body><div id="rooster"></div><table class="calender"></table></body></html>'

    assert DyflexisClient.looks_like_roster_html(html) is True


def test_looks_like_roster_html_rejects_non_roster_markup():
    html = "<html><body><form id='login'></form></body></html>"

    assert DyflexisClient.looks_like_roster_html(html) is False
