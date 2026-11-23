import os

# CampaignRunner._preflight_llm pings the real LLM endpoint before running
# experiments; unit tests stub _run_experiment and must not depend on network
# or credentials. Dedicated preflight tests re-enable it via monkeypatch.
os.environ.setdefault("CAMPAIGN_SKIP_LLM_PREFLIGHT", "1")
