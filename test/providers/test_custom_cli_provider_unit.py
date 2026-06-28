from unittest.mock import MagicMock, patch

import pytest

from cli_agent_orchestrator.models.agent_profile import AgentProfile
from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.custom_cli import CustomCliProvider, ProviderError


def _profile(**overrides):
    data = {
        "name": "custom-agent",
        "description": "custom",
        "provider": "custom_cli",
        "customCliCommand": "python -m cli_agent_orchestrator.providers.factory_repl",
        "customCliIdleRegex": r"^\s*factory>\s*$",
        "customCliAssistantPrefixRegex": r"^Assistant:\s*",
        "customCliUserPrefixRegex": r"^factory>\s*",
        "customCliExitCommand": "/exit",
        "customCliPasteEnterCount": 1,
    }
    data.update(overrides)
    return AgentProfile(**data)


@patch("cli_agent_orchestrator.providers.custom_cli.load_agent_profile")
def test_custom_cli_provider_requires_command(mock_load_profile):
    mock_load_profile.return_value = _profile(customCliCommand=None)
    with pytest.raises(ProviderError, match="must define customCliCommand"):
        CustomCliProvider("t1", "s1", "w1", agent_profile="custom-agent")


@patch("cli_agent_orchestrator.providers.custom_cli.load_agent_profile")
def test_custom_cli_get_status_detects_completed(mock_load_profile):
    mock_load_profile.return_value = _profile()
    provider = CustomCliProvider("t1", "s1", "w1", agent_profile="custom-agent")
    output = """
factory> classify this task
Assistant:
done
factory>
"""
    assert provider.get_status(output) == TerminalStatus.COMPLETED


@patch("cli_agent_orchestrator.providers.custom_cli.load_agent_profile")
def test_custom_cli_get_status_detects_waiting(mock_load_profile):
    mock_load_profile.return_value = _profile(
        customCliWaitingRegex=r"Choice \[y/n\]:",
        customCliIdleRegex=r"^\s*custom>\s*$",
    )
    provider = CustomCliProvider("t1", "s1", "w1", agent_profile="custom-agent")
    output = """
Need approval to continue
Choice [y/n]:
"""
    assert provider.get_status(output) == TerminalStatus.WAITING_USER_ANSWER


@patch("cli_agent_orchestrator.providers.custom_cli.load_agent_profile")
def test_custom_cli_extract_last_message(mock_load_profile):
    mock_load_profile.return_value = _profile()
    provider = CustomCliProvider("t1", "s1", "w1", agent_profile="custom-agent")
    output = """
factory> build summary
Assistant:
line one
line two
factory>
"""
    assert provider.extract_last_message_from_script(output) == "line one\nline two"


@pytest.mark.asyncio
@patch("cli_agent_orchestrator.providers.custom_cli.wait_until_status")
@patch("cli_agent_orchestrator.providers.custom_cli.wait_for_shell")
@patch("cli_agent_orchestrator.providers.custom_cli.get_backend")
@patch("cli_agent_orchestrator.providers.custom_cli.load_agent_profile")
async def test_custom_cli_initialize_launches_command(
    mock_load_profile,
    mock_get_backend,
    mock_wait_for_shell,
    mock_wait_until_status,
):
    mock_load_profile.return_value = _profile(customCliCommand="echo custom")
    mock_wait_for_shell.return_value = True
    mock_wait_until_status.return_value = True
    backend = MagicMock()
    mock_get_backend.return_value = backend

    provider = CustomCliProvider("t1", "s1", "w1", agent_profile="custom-agent")
    ok = await provider.initialize()

    assert ok is True
    backend.send_keys.assert_called_once_with("s1", "w1", "echo custom")
    assert provider.exit_cli() == "/exit"
