import sys
from pathlib import Path

import pytest

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fake_openai import FakeAsyncOpenAI, default_responder


@pytest.fixture
def patch_openai(monkeypatch):
    """Patch the one place a real AsyncOpenAI client is constructed
    (CampaignCoordinator.__init__) so the whole agent pipeline runs against
    canned responses instead of the network. Returns a factory so tests can
    swap in a custom `responder` for a particular scenario (e.g. DECLINED).
    """
    created_clients = []

    def _patch(responder=None):
        def fake_constructor(api_key: str):
            client = FakeAsyncOpenAI(api_key=api_key, responder=responder or default_responder)
            created_clients.append(client)
            return client

        monkeypatch.setattr("agents.coordinator.AsyncOpenAI", fake_constructor)
        return created_clients

    return _patch


@pytest.fixture
def app(monkeypatch, tmp_path):
    # Ensure the app sees an API key configured, regardless of the host env.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-suite")
    import importlib
    import main as main_module
    importlib.reload(main_module)
    return main_module.app
