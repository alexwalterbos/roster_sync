from roster_sync.cache import cache_key_for_url, normalize_url


def test_normalize_url_sorts_query_params():
    url = "https://example.invalid/example-customer/example-location/rooster2/index2?b=2&a=1"

    assert normalize_url(url).endswith("a=1&b=2")


def test_cache_key_is_stable_for_equivalent_urls():
    one = "https://example.invalid/example-customer/example-location/rooster2/index2?periode=2026-03&x=1"
    two = "https://example.invalid/example-customer/example-location/rooster2/index2?x=1&periode=2026-03"

    assert cache_key_for_url(one) == cache_key_for_url(two)
