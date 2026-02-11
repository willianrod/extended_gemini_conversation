"""Base entity for Extended Gemini Conversation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import json
import logging
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import types as genai_types
import orjson
import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigSubentry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify

from .const import (
    CONF_CHAT_MODEL,
    CONF_CONTEXT_THRESHOLD,
    CONF_CONTEXT_TRUNCATE_STRATEGY,
    CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION,
    CONF_MAX_TOKENS,
    CONF_REASONING_EFFORT,
    CONF_SERVICE_TIER,
    CONF_SHORTEN_TOOL_CALL_ID,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    DEFAULT_CHAT_MODEL,
    DEFAULT_CONTEXT_THRESHOLD,
    DEFAULT_CONTEXT_TRUNCATE_STRATEGY,
    DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_SERVICE_TIER,
    DEFAULT_SHORTEN_TOOL_CALL_ID,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DOMAIN,
)
from .exceptions import FunctionNotFound, ParseArgumentsFailed, TokenLengthExceededError
from .helpers import get_function_executor, get_model_config

if TYPE_CHECKING:
    from . import ExtendedOpenAIConfigEntry

_LOGGER = logging.getLogger(__name__)

# Max number of back and forth with the LLM to generate a response
MAX_TOOL_ITERATIONS = 10


def _adjust_schema(schema: dict[str, Any]) -> None:
    """Adjust the schema to be compatible with Gemini API."""
    # Gemini has different schema requirements than OpenAI
    # For now, we'll keep the schema mostly as-is
    if schema["type"] == "object":
        if "properties" not in schema:
            return

        # Ensure required fields are present
        if "required" not in schema:
            schema["required"] = []

        # Process nested properties
        for prop, prop_info in schema["properties"].items():
            _adjust_schema(prop_info)

    elif schema["type"] == "array":
        if "items" not in schema:
            return

        _adjust_schema(schema["items"])


def _format_structured_output(
    schema: vol.Schema, llm_api: llm.APIInstance | None
) -> dict[str, Any]:
    """Format the schema to be compatible with Gemini API."""
    result: dict[str, Any] = convert(
        schema,
        custom_serializer=(
            llm_api.custom_serializer if llm_api else llm.selector_serializer
        ),
    )

    _adjust_schema(result)

    return result


def _convert_content_to_gemini(
    chat_content: list[conversation.Content],
) -> tuple[str, list[genai_types.Content]]:
    """Convert chat log content to Gemini message format.
    
    Returns:
        A tuple of (system_instruction, history)
        where system_instruction is the system prompt
        and history is the list of Content objects for the conversation
    """
    system_instruction = ""
    history: list[genai_types.Content] = []
    
    for content in chat_content:
        if content.role == "system":
            # Gemini uses system_instruction separately
            system_instruction = content.content
        elif content.role == "user":
            history.append(genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=content.content)]
            ))
        elif content.role == "assistant":
            parts = []
            if content.content:
                parts.append(genai_types.Part(text=content.content))
            if content.tool_calls:
                # Gemini handles function calls differently
                # We'll convert them to function call parts
                for tool_call in content.tool_calls:
                    parts.append(genai_types.Part.from_function_call(
                        name=tool_call.tool_name,
                        args=tool_call.tool_args
                    ))
            history.append(genai_types.Content(
                role="model",  # Gemini uses "model" instead of "assistant"
                parts=parts
            ))
        elif content.role == "tool_result":
            # Gemini uses role="user" for function responses
            history.append(genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_function_response(
                    name=content.tool_name,
                    response=content.tool_result
                )]
            ))
    
    return system_instruction, history


class ExtendedOpenAIBaseLLMEntity(Entity):
    """Extended Gemini base entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, entry: ExtendedOpenAIConfigEntry, subentry: ConfigSubentry
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Google",
            model=subentry.data.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL),
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    def _client(self) -> genai.Client:
        """Return the Gemini client."""
        return self.entry.runtime_data

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        custom_functions: list[dict[str, Any]],
        exposed_entities: list[dict[str, Any]],
        llm_context: llm.LLMContext | None = None,
        structure_name: str | None = None,
        structure: vol.Schema | None = None,
    ) -> None:
        """Generate an answer for the chat log with Gemini streaming support."""
        options = self.subentry.data
        model_name = options.get(CONF_CHAT_MODEL, DEFAULT_CHAT_MODEL)
        max_function_calls = options.get(
            CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION,
            DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION,
        )

        # Get model-specific configuration
        model_config = get_model_config(model_name)

        # Convert messages to Gemini format
        system_instruction, history = _convert_content_to_gemini(chat_log.content)

        # Build tools list from custom functions for Gemini
        tools = []
        if custom_functions:
            function_declarations = []
            for func_spec in custom_functions:
                spec = func_spec["spec"]
                # Convert OpenAI function spec to Gemini FunctionDeclaration
                function_declarations.append(
                    genai_types.FunctionDeclaration(
                        name=spec["name"],
                        description=spec.get("description", ""),
                        parameters=spec.get("parameters", {})
                    )
                )
            if function_declarations:
                tools = [genai_types.Tool(function_declarations=function_declarations)]

        # Build generation config
        max_tokens = options.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)

        _LOGGER.info("Prompt for %s with system: %s, history length: %d", 
                    model_name, system_instruction[:100] if system_instruction else "", len(history))

        # Build generation config
        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction if system_instruction else None,
            max_output_tokens=max_tokens if model_config["supports_max_tokens"] else None,
            top_p=options.get(CONF_TOP_P, DEFAULT_TOP_P) if model_config["supports_top_p"] else None,
            temperature=options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE) if model_config["supports_temperature"] else None,
            tools=tools if tools else None,
        )

        # To prevent infinite loops, we limit the number of iterations
        for n_requests in range(MAX_TOOL_ITERATIONS):
            _LOGGER.debug("Request iteration %d", n_requests)

            # Build contents: history minus last message as context, last message as current
            contents = history if history else [genai_types.Content(role="user", parts=[genai_types.Part(text="")])]
            
            # Generate content with streaming using the new async client API
            try:
                response = await self._client.aio.models.generate_content_stream(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                
                # Process streaming response
                pending_tool_calls: list[llm.ToolInput] = []
                
                async for content in chat_log.async_add_delta_content_stream(
                    self.entity_id, self._transform_gemini_stream(chat_log, response)
                ):
                    if (
                        isinstance(content, conversation.AssistantContent)
                        and content.tool_calls
                    ):
                        pending_tool_calls.extend(content.tool_calls)

                if pending_tool_calls:
                    _LOGGER.info("Response Tool Calls %s", pending_tool_calls)

                # Execute custom functions
                for tool_call in pending_tool_calls:
                    custom_func = next(
                        (
                            f
                            for f in custom_functions
                            if f["spec"]["name"] == tool_call.tool_name
                        ),
                        None,
                    )

                    if custom_func is None:
                        raise FunctionNotFound(tool_call.tool_name)

                    tool_result_content = await self._execute_custom_function(
                        custom_func,
                        tool_call,
                        llm_context,
                        exposed_entities,
                    )

                    chat_log.async_add_assistant_content_without_tools(tool_result_content)

                # Update history for next iteration
                system_instruction, history = _convert_content_to_gemini(chat_log.content)

                # Check if we need to continue (if there are pending tool results)
                if not chat_log.unresponded_tool_results:
                    break
                    
                # Check if we've hit the max function calls limit
                if max_function_calls >= 0 and n_requests >= max_function_calls:
                    _LOGGER.warning("Max function calls limit reached")
                    break
                    
            except Exception as err:
                _LOGGER.error("Error generating content: %s", err, exc_info=True)
                raise

    async def _transform_gemini_stream(
        self,
        chat_log: conversation.ChatLog,
        response: Any,  # Gemini AsyncIterator[GenerateContentResponse]
    ) -> AsyncGenerator[
        conversation.AssistantContentDeltaDict | conversation.ToolResultContentDeltaDict
    ]:
        """Transform Gemini stream to Home Assistant format."""
        first_chunk = True
        total_tokens = 0
        
        async for chunk in response:
            _LOGGER.debug("Received Gemini chunk: %s", chunk)

            # Check for content policy violations
            if chunk.prompt_feedback or not chunk.candidates:
                reason = (
                    chunk.prompt_feedback.block_reason_message
                    if chunk.prompt_feedback
                    else "unknown"
                )
                raise HomeAssistantError(
                    f"Content blocked due to content violations, reason: {reason}"
                )
            
            # Signal new assistant message on first chunk
            if first_chunk:
                yield {"role": "assistant"}
                first_chunk = False
            
            # Track usage if available
            if chunk.usage_metadata:
                usage = chunk.usage_metadata
                if usage.total_token_count:
                    total_tokens = usage.total_token_count
                    chat_log.async_trace(
                        {
                            "stats": {
                                "input_tokens": usage.prompt_token_count or 0,
                                "output_tokens": usage.candidates_token_count or 0,
                            }
                        }
                    )
            
            candidate = chunk.candidates[0]

            # Check finish reason for non-STOP reasons (errors)
            if (
                candidate.finish_reason is not None
                and candidate.finish_reason != "STOP"
            ):
                if candidate.finish_reason == "MAX_TOKENS":
                    raise TokenLengthExceededError(
                        self.subentry.data.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS)
                    )
                _LOGGER.error(
                    "Error in Gemini response: %s",
                    candidate.finish_reason,
                )
                raise HomeAssistantError(
                    f"Error generating response: {candidate.finish_reason}"
                )

            response_parts = (
                candidate.content.parts
                if candidate.content is not None and candidate.content.parts is not None
                else []
            )

            for part in response_parts:
                # Handle text content
                if part.text:
                    yield {"content": part.text}
                
                # Handle function calls
                elif part.function_call:
                    fc = part.function_call
                    tool_name = fc.name or ""
                    tool_call = llm.ToolInput(
                        tool_name=tool_name,
                        tool_args=dict(fc.args) if fc.args else {},
                    )
                    yield {"tool_calls": [tool_call]}
        
        # Check token threshold after streaming completes
        if total_tokens > self.subentry.data.get(
            CONF_CONTEXT_THRESHOLD, DEFAULT_CONTEXT_THRESHOLD
        ):
            await self._truncate_message_history(chat_log)

    async def _execute_custom_function(
        self,
        function_spec: dict[str, Any],
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext | None,
        exposed_entities: list[dict[str, Any]],
    ) -> conversation.ToolResultContent:
        """Execute a custom function."""
        function = function_spec["function"]
        arguments: dict[str, Any] = tool_input.tool_args
        function_executor = get_function_executor(function["type"])

        if self.should_run_in_background(arguments):
            # create a delayed function and execute in background
            function_executor = get_function_executor("composite")
            self.entry.async_create_task(
                self.hass,
                function_executor.execute(
                    self.hass,
                    self.get_delayed_function(function, arguments),
                    arguments,
                    llm_context,
                    exposed_entities,
                ),
            )
            result = "Scheduled"
        else:
            result = await function_executor.execute(
                self.hass, function, arguments, llm_context, exposed_entities
            )

        return conversation.ToolResultContent(
            agent_id=self.entity_id,
            tool_call_id=tool_input.id,
            tool_name=tool_input.tool_name,
            tool_result={"result": str(result)},
        )

    def should_run_in_background(self, arguments: dict[str, Any]) -> bool:
        """Check if function needs delay."""
        return isinstance(arguments, dict) and arguments.get("delay") is not None

    def get_delayed_function(
        self, function: dict[str, Any], arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute function with delay."""
        # create a composite function with delay in script function
        return {
            "type": "composite",
            "sequence": [
                {
                    "type": "script",
                    "sequence": [{"delay": arguments["delay"]}],
                },
                function,
            ],
        }

    async def _truncate_message_history(self, chat_log: conversation.ChatLog) -> None:
        """Truncate message history based on strategy."""
        options = self.subentry.data
        strategy = options.get(
            CONF_CONTEXT_TRUNCATE_STRATEGY, DEFAULT_CONTEXT_TRUNCATE_STRATEGY
        )

        if strategy == "clear":
            # Keep only system prompt and last user message
            # This is handled by refreshing the LLM data
            _LOGGER.info("Context threshold exceeded, conversation history cleared")
            last_user_message_index = None
            messages = chat_log.content
            for i in reversed(range(len(messages))):
                if isinstance(messages[i], conversation.UserContent):
                    last_user_message_index = i
                    break

            if last_user_message_index is not None:
                del messages[1:last_user_message_index]
