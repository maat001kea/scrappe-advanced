from scraper.network.user_agents import UserAgentPool


def test_user_agent_pool_size() -> None:
    pool = UserAgentPool(seed=1)
    assert pool.size() >= 100


def test_user_agent_pool_random_returns_string() -> None:
    pool = UserAgentPool(seed=1)
    ua = pool.random()
    assert isinstance(ua, str)
    assert ua.startswith("Mozilla/")
