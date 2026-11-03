from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class TestRunner(DiscoverRunner):
    """
    Runs tests with a cache that keeps nothing, so request limits (core/throttle.py)
    do not add up across the whole test run. Tests of the limits switch a real
    cache on with override_settings.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._cache_override = override_settings(
            CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
        self._cache_override.enable()

    def teardown_test_environment(self, **kwargs):
        self._cache_override.disable()
        super().teardown_test_environment(**kwargs)
