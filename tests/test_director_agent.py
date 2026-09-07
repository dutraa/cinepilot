import asyncio

from director_agent import DirectorAgent
from event_log import EventLog
from grafana_publisher import GrafanaPublisher
from schemas import CinematicIntent
from state import AppState
from story_demo import load_initial_shot, load_story_fixture


class FakeSession:
    def __init__(self) -> None:
        self.messages = []

    async def send_client_content(self, **kwargs):
        self.messages.append(kwargs)


def test_agent_sends_intent_once_per_version(tmp_path) -> None:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    state.set_intent(
        CinematicIntent(
            shot_name="Reveal",
            creative_goal="Make the building feel imposing.",
            subject="Building",
        )
    )
    agent = DirectorAgent(object(), state, GrafanaPublisher(url="", user="", api_key=""))
    session = FakeSession()

    asyncio.run(agent._sync_intent(session, force=True))
    asyncio.run(agent._sync_intent(session))

    assert len(session.messages) == 1
    content = session.messages[0]["turns"]
    assert "Make the building feel imposing." in content.parts[0].text


def test_agent_sends_story_context_once_per_context_version(tmp_path) -> None:
    state = AppState(EventLog(str(tmp_path / "events.jsonl")))
    coverage, contribution = load_initial_shot()
    state.load_story(load_story_fixture(), coverage, contribution, "deterministic_demo")
    agent = DirectorAgent(object(), state, GrafanaPublisher(url="", user="", api_key=""))
    session = FakeSession()

    asyncio.run(agent._sync_story(session, force=True))
    asyncio.run(agent._sync_story(session))

    assert len(session.messages) == 1
    text = session.messages[0]["turns"].parts[0].text
    assert "The place worth coming back to" in text
    assert "Isolation" in text

    state.skip_active_beat("isolation")
    asyncio.run(agent._sync_story(session))
    assert len(session.messages) == 2
