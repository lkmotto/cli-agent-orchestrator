"""Generic custom CLI provider implementation.

This provider enables CAO to orchestrate arbitrary REPL-style CLI tools by
driving behavior from agent-profile regex and command fields. It is intended
for integrations such as Factory and Perplexity wrappers, and future tools.
"""

import logging
import re
from typing import Optional

from cli_agent_orchestrator.backends.registry import get_backend
from cli_agent_orchestrator.models.agent_profile import AgentProfile
from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.providers.base import BaseProvider
from cli_agent_orchestrator.services.settings_service import get_server_settings
from cli_agent_orchestrator.utils.agent_profiles import load_agent_profile
from cli_agent_orchestrator.utils.terminal import wait_for_shell, wait_until_status

logger = logging.getLogger(__name__)

ANSI_CODE_PATTERN = r"\x1b(?:\[[0-9;?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))"
DEFAULT_IDLE_REGEX = r"^\s*(?:❯|✦|>|>>>|factory>|perplexity>)\s*$"
DEFAULT_PROCESSING_REGEX = (
    r"(?:thinking|processing|working|running|musing|loading|generating|msg=interrupt)"
)
DEFAULT_WAITING_REGEX = (
    r"(?:Approve|Allow|Proceed|Confirm)[^\n]*(?:y/n|yes/no|\[y/N\])"
    r"|(?:Choice\s+\[o/s(?:/a)?/D\]:)"
    r"|(?:type your answer and press Enter)"
)
DEFAULT_ERROR_REGEX = r"^(?:Error:|ERROR:|Traceback \(most recent call last\):|Exception:)"
DEFAULT_USER_PREFIX_REGEX = r"^(?:●\s+|You:\s+|User:\s+)"
DEFAULT_ASSISTANT_PREFIX_REGEX = r"^(?:Assistant:\s*|AI:\s*|Model:\s*|Response:\s*|•\s+)"


class ProviderError(Exception):
    """Exception raised for custom CLI provider-specific errors."""

    pass


def _strip_ansi(text: str) -> str:
    return re.sub(ANSI_CODE_PATTERN, "", text)


class CustomCliProvider(BaseProvider):
    """Provider for configurable REPL-style CLI tools."""

    def __init__(
        self,
        terminal_id: str,
        session_name: str,
        window_name: str,
        agent_profile: Optional[str] = None,
        allowed_tools: Optional[list] = None,
        skill_prompt: Optional[str] = None,
    ):
        super().__init__(terminal_id, session_name, window_name, allowed_tools, skill_prompt)
        if not agent_profile:
            raise ProviderError("Custom CLI provider requires agent_profile parameter")
        self._initialized = False
        self._agent_profile = agent_profile
        self._profile = self._load_profile(agent_profile)
        self._command = self._profile.customCliCommand or ""
        if not self._command:
            raise ProviderError(
                f"Agent profile '{agent_profile}' must define customCliCommand for custom_cli"
            )
        self._idle_prompt_regex = self._profile.customCliIdleRegex or DEFAULT_IDLE_REGEX
        self._processing_regex = self._profile.customCliProcessingRegex or DEFAULT_PROCESSING_REGEX
        self._waiting_regex = self._profile.customCliWaitingRegex or DEFAULT_WAITING_REGEX
        self._error_regex = self._profile.customCliErrorRegex or DEFAULT_ERROR_REGEX
        self._user_prefix_regex = (
            self._profile.customCliUserPrefixRegex or DEFAULT_USER_PREFIX_REGEX
        )
        self._assistant_prefix_regex = (
            self._profile.customCliAssistantPrefixRegex or DEFAULT_ASSISTANT_PREFIX_REGEX
        )
        self._exit_command = self._profile.customCliExitCommand or "/exit"
        self._paste_enter_count = self._normalize_enter_count(
            self._profile.customCliPasteEnterCount
        )

    @staticmethod
    def _load_profile(agent_profile: str) -> AgentProfile:
        try:
            return load_agent_profile(agent_profile)
        except Exception as e:
            raise ProviderError(f"Failed to load agent profile '{agent_profile}': {e}") from e

    @staticmethod
    def _normalize_enter_count(value: Optional[int]) -> int:
        if value is None:
            return 1
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            return 1
        return value

    @property
    def paste_enter_count(self) -> int:
        return self._paste_enter_count

    @property
    def blocks_orchestrated_input_while_waiting_user_answer(self) -> bool:
        return True

    async def initialize(self) -> bool:
        init_timeout = get_server_settings()["provider_init_timeout"]
        if (
            isinstance(self._profile.customCliInitTimeout, int)
            and self._profile.customCliInitTimeout > 0
        ):
            init_timeout = self._profile.customCliInitTimeout

        if not await wait_for_shell(self.terminal_id, timeout=init_timeout):
            raise TimeoutError(f"Shell initialization timed out after {init_timeout}s")

        get_backend().send_keys(self.session_name, self.window_name, self._command)

        if not await wait_until_status(
            self.terminal_id,
            {TerminalStatus.IDLE, TerminalStatus.COMPLETED},
            timeout=float(init_timeout),
            polling_interval=1.0,
        ):
            raise TimeoutError(f"Custom CLI initialization timed out after {init_timeout} seconds")

        self._initialized = True
        return True

    def get_status(self, output: str) -> TerminalStatus:
        if not output:
            return TerminalStatus.UNKNOWN

        clean_output = _strip_ansi(output)
        lines = clean_output.splitlines()
        tail_lines = lines[-30:]
        tail_output = "\n".join(tail_lines)
        bottom_lines = [line for line in tail_lines if line.strip()][-8:]
        bottom_output = "\n".join(bottom_lines)

        if self._waiting_regex and re.search(
            self._waiting_regex, bottom_output, re.IGNORECASE | re.MULTILINE
        ):
            return TerminalStatus.WAITING_USER_ANSWER

        if self._error_regex and re.search(
            self._error_regex, tail_output, re.IGNORECASE | re.MULTILINE
        ):
            return TerminalStatus.ERROR

        has_idle_prompt = any(
            re.search(self._idle_prompt_regex, line.strip(), re.IGNORECASE) for line in bottom_lines
        )
        has_processing = bool(
            self._processing_regex
            and re.search(self._processing_regex, bottom_output, re.IGNORECASE | re.MULTILINE)
        )
        has_user = bool(
            self._user_prefix_regex
            and re.search(self._user_prefix_regex, clean_output, re.IGNORECASE | re.MULTILINE)
        )
        has_assistant = bool(
            self._assistant_prefix_regex
            and re.search(self._assistant_prefix_regex, clean_output, re.IGNORECASE | re.MULTILINE)
        )

        if has_idle_prompt:
            if has_user and has_assistant:
                return TerminalStatus.COMPLETED
            return TerminalStatus.IDLE

        if has_processing:
            return TerminalStatus.PROCESSING

        return TerminalStatus.PROCESSING

    def _fallback_extract(self, clean_output: str) -> str:
        lines = [line.strip() for line in clean_output.splitlines() if line.strip()]
        non_prompt = [
            line for line in lines if not re.search(self._idle_prompt_regex, line, re.IGNORECASE)
        ]
        if not non_prompt:
            raise ValueError("Empty custom CLI response - no content found")
        return "\n".join(non_prompt[-8:])

    def extract_last_message_from_script(self, script_output: str) -> str:
        clean_output = _strip_ansi(script_output)

        matches = list(
            re.finditer(
                self._assistant_prefix_regex,
                clean_output,
                re.IGNORECASE | re.MULTILINE,
            )
        )
        if not matches:
            return self._fallback_extract(clean_output)

        start = matches[-1].end()
        search_region = clean_output[start:]
        end_match = re.search(self._idle_prompt_regex, search_region, re.IGNORECASE | re.MULTILINE)
        text = search_region[: end_match.start()] if end_match else search_region
        text = text.strip()
        if text:
            return text
        return self._fallback_extract(clean_output)

    def exit_cli(self) -> str:
        return self._exit_command

    def cleanup(self) -> None:
        self._initialized = False
