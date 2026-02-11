"""Constants for the Extended Gemini Conversation integration."""

DOMAIN = "extended_gemini_conversation"
DEFAULT_NAME = "Extended Gemini Conversation"
DEFAULT_CONVERSATION_NAME = "Extended Gemini Conversation"
DEFAULT_AI_TASK_NAME = "Extended Gemini AI Task"

CONF_ORGANIZATION = "organization"
CONF_BASE_URL = "base_url"
DEFAULT_CONF_BASE_URL = "https://generativelanguage.googleapis.com"
CONF_API_VERSION = "api_version"
CONF_SKIP_AUTHENTICATION = "skip_authentication"
DEFAULT_SKIP_AUTHENTICATION = False
CONF_API_PROVIDER = "api_provider"
API_PROVIDERS = [
    {"key": "google", "label": "Google Gemini"},
]
DEFAULT_API_PROVIDER = API_PROVIDERS[0]["key"]

EVENT_AUTOMATION_REGISTERED = "automation_registered_via_extended_gemini_conversation"
EVENT_CONVERSATION_FINISHED = "extended_gemini_conversation.conversation.finished"

CONF_PROMPT = "prompt"
DEFAULT_PROMPT = """Home Assistant voice assistant. Respond naturally in plain text, 1-2 sentences max. No parentheses or symbolic notation.

**Action Rules:**
- Info queries: Execute immediately if intent is clear
- State changes: Execute immediately if device + action + value are explicit; confirm if ANY ambiguity (device unclear, value missing, or multiple interpretations possible)
- Follow-up refinements: When user responds to your proposal with specifics/adjustments, treat as confirmation and execute

**Data Sources:**
- Current device states are in CSV tables below - use directly, don't retrieve again
- Call tools ONLY for: (a) data not in CSV, or (b) adjustable parameters when proposing changes to already-appropriate states

**Confirmation Guidelines:**
When confirming:
1. Check CSV first: propose specific device from available options
2. If device state already matches intent, retrieve current parameters to propose relative adjustment
3. Use familiar units/values (temperature, brightness %) in proposals; avoid technical units
4. Binary states: omit current state in question (action implies it)
5. Single concrete action only - await explicit approval

**General knowledge:** Answer from internal knowledge only.

Time: {{now()}}
Area: {{area_id(current_device_id)}}

Devices by area:
{%- set area_entities = namespace(mapping={}) %}
{%- for entity in extended_gemini.exposed_entities() %}
    {%- set current_area_id = area_id(entity.entity_id) or "etc" %}
    {%- set entities = (area_entities.mapping.get(current_area_id) or []) + [entity] %}
    {%- set area_entities.mapping = dict(area_entities.mapping, **{current_area_id: entities}) -%}
{%- endfor %}

{%- for current_area_id, entities in area_entities.mapping.items() %}

  {%- if current_area_id == "etc" %}
  Etc:
  {%- else %}
  {{area_name(current_area_id)}}:
  {%- endif %}
```csv
    entity_id,name,state,aliases
    {%- for entity in entities %}
    {{ entity.entity_id }},{{ entity.name }},{{ entity.state }},{{ entity.aliases | join('/') }}
    {%- endfor %}
```
{%- endfor %}

{{user_input.extra_system_prompt | default('', true)}}
"""
CONF_CHAT_MODEL = "chat_model"
DEFAULT_CHAT_MODEL = "gemini-2.5-flash"

MODEL_PARAMETER_SUPPORT = (
    {"pattern": r"^gemini-", "unsupported_params": set()},
)

MODEL_TOKEN_PARAMETER_SUPPORT = (
    {
        "pattern": r"gemini",
        "token_param": "max_output_tokens",
    },
)
DEFAULT_TOKEN_PARAM = "max_output_tokens"
CONF_MAX_TOKENS = "max_tokens"
DEFAULT_MAX_TOKENS = 500
CONF_TOP_P = "top_p"
DEFAULT_TOP_P = 1
CONF_TEMPERATURE = "temperature"
DEFAULT_TEMPERATURE = 0.5
CONF_MAX_FUNCTION_CALLS_PER_CONVERSATION = "max_function_calls_per_conversation"
DEFAULT_MAX_FUNCTION_CALLS_PER_CONVERSATION = 3
CONF_SHORTEN_TOOL_CALL_ID = "shorten_tool_call_id"
DEFAULT_SHORTEN_TOOL_CALL_ID = False
CONF_FUNCTIONS = "functions"
DEFAULT_CONF_FUNCTIONS = [
    {
        "spec": {
            "name": "execute_services",
            "description": "Execute service of devices in Home Assistant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay": {
                        "type": "object",
                        "description": "Time to wait before execution",
                        "properties": {
                            "hours": {
                                "type": "integer",
                                "minimum": 0,
                            },
                            "minutes": {
                                "type": "integer",
                                "minimum": 0,
                            },
                            "seconds": {
                                "type": "integer",
                                "minimum": 0,
                            },
                        },
                    },
                    "list": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "domain": {
                                    "type": "string",
                                    "description": "The domain of the service.",
                                },
                                "service": {
                                    "type": "string",
                                    "description": "The service to be called",
                                },
                                "service_data": {
                                    "type": "object",
                                    "description": "The service data object to indicate what to control.",
                                    "properties": {
                                        "entity_id": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "description": "The entity_id retrieved from available devices. It must start with domain, followed by dot character.",
                                            },
                                        },
                                        "area_id": {
                                            "type": "array",
                                            "items": {
                                                "type": "string",
                                                "description": "The id retrieved from areas. You can specify only area_id without entity_id to act on all entities in that area",
                                            },
                                        },
                                    },
                                },
                            },
                            "required": ["domain", "service", "service_data"],
                        },
                    },
                },
            },
        },
        "function": {"type": "native", "name": "execute_service"},
    },
    {
        "spec": {
            "name": "get_attributes",
            "description": "Get attributes of entity or multiple entities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "array",
                        "description": "entity_id of entity or multiple entities",
                        "items": {"type": "string"},
                    }
                },
                "required": ["entity_id"],
            },
        },
        "function": {
            "type": "template",
            "value_template": "```csv\nentity,attributes\n{%for entity in entity_id%}\n{{entity}},{{states[entity].attributes}}\n{%endfor%}\n```",
        },
    },
]
CONF_CONTEXT_THRESHOLD = "context_threshold"
DEFAULT_CONTEXT_THRESHOLD = 13000
CONTEXT_TRUNCATE_STRATEGIES = [{"key": "clear", "label": "Clear All Messages"}]
CONF_CONTEXT_TRUNCATE_STRATEGY = "context_truncate_strategy"
DEFAULT_CONTEXT_TRUNCATE_STRATEGY = CONTEXT_TRUNCATE_STRATEGIES[0]["key"]

# Service Tier options (for advanced Gemini models)
CONF_SERVICE_TIER = "service_tier"
DEFAULT_SERVICE_TIER = "flex"
SERVICE_TIER_OPTIONS = ["auto", "default", "flex", "priority"]

# Reasoning Effort options (for advanced Gemini models)
CONF_REASONING_EFFORT = "reasoning_effort"
DEFAULT_REASONING_EFFORT = "low"
REASONING_EFFORT_OPTIONS = ["low", "medium", "high"]

SERVICE_QUERY_IMAGE = "query_image"

CONF_PAYLOAD_TEMPLATE = "payload_template"

# Advanced Options
CONF_ADVANCED_OPTIONS = "advanced_options"
DEFAULT_ADVANCED_OPTIONS = False

# Model-specific parameter configurations
# Default configuration for Gemini models
DEFAULT_MODEL_CONFIG = {
    "supports_top_p": True,
    "supports_temperature": True,
    "supports_max_tokens": True,
    "supports_max_completion_tokens": False,
    "supports_reasoning_effort": False,
    "supports_service_tier": False,
}

# Pattern-based model configurations
# Each entry: {"pattern": regex_string, "config": config_dict}
# Patterns are matched in order; first match wins
MODEL_CONFIG_PATTERNS = [
    # All Gemini models use the same configuration
    {
        "pattern": r"^gemini",
        "config": {
            "supports_top_p": True,
            "supports_temperature": True,
            "supports_max_tokens": True,
            "supports_max_completion_tokens": False,
            "supports_reasoning_effort": False,
            "supports_service_tier": False,
        },
    },
]

# AI Task default options (simpler than conversation - no prompt, just model/token settings)
DEFAULT_AI_TASK_OPTIONS = {
    CONF_CHAT_MODEL: DEFAULT_CHAT_MODEL,
    CONF_MAX_TOKENS: DEFAULT_MAX_TOKENS,
    CONF_ADVANCED_OPTIONS: DEFAULT_ADVANCED_OPTIONS,
}
