import os
import re
import json
import logging
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.workflow import Workflow, Edge, START, DEFAULT_ROUTE, node
from google.adk.events import RequestInput
from google.adk.tools.agent_tool import AgentTool
from google.adk.apps import App
from google.adk.agents.context import Context

from app.config import config

import sys
from mcp import StdioServerParameters
from google.adk.tools import MCPToolset
from google.adk.tools.mcp_tool import StdioConnectionParams

logger = logging.getLogger("style-match.agent")

# Initialize Gemini Model
model_instance = Gemini(model=config.model)

# Define MCP connection to local server using recommended StdioConnectionParams
mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"]
        )
    )
)

# --- Sub-agents definitions ---

wardrobe_agent = LlmAgent(
    name="wardrobe_agent",
    model=model_instance,
    tools=[mcp_toolset],
    instruction="""You are the Wardrobe Agent. Your job is to analyze the user's wardrobe items and match them to the user's styling request.
Use the `get_wardrobe_items` tool to retrieve the list of clothing items available in the user's wardrobe.
Check if the user has requested specific clothing types, colors, or materials.
Select pieces that coordinate well (e.g. contrast or matching tones).
If no wardrobe details are provided, ask the user to provide a list of clothing items they own.""",
    description="Provides recommendations and styling options based on clothing items available in the user's wardrobe.",
)

weather_matcher_agent = LlmAgent(
    name="weather_matcher_agent",
    model=model_instance,
    tools=[mcp_toolset],
    instruction="""You are the Weather Matcher Agent. Your job is to assess if the suggested clothing options are suitable for the weather conditions and event type.
Use the `get_weather_forecast` tool to retrieve the weather conditions for the location.
Verify that the recommended layers are appropriate (e.g. coat for cold weather, breathable fabrics for hot weather, rain boots/umbrella for rain).""",
    description="Suggests outfits based on weather and event parameters.",
)

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=model_instance,
    tools=[
        AgentTool(wardrobe_agent),
        AgentTool(weather_matcher_agent),
        mcp_toolset  # Wire into orchestrator as well so it can call save_selected_outfit
    ],
    instruction="""You are the StyleMatch Orchestrator. Your goal is to suggest a complete outfit for the user's event and weather.
1. Delegate to wardrobe_agent to get matching wardrobe suggestions based on the user's request.
2. Delegate to weather_matcher_agent to verify the suggestions against the weather and event type.
3. Combine the recommendations into a single, cohesive, well-formatted outfit response.
Include a list of items to wear and the styling rationale.
Refer to previous user feedback stored in context state (if present under 'user_feedback') to revise suggestions.
Once the user confirms the selection (when you have received positive confirmation/approval in the input), call the `save_selected_outfit` tool to save the outfit to their diary.""",
    description="Orchestrator for the styling assistant. Coordinates wardrobe analysis and weather matching.",
)

# --- Workflow nodes ---

@node(name="security_checkpoint")
async def security_checkpoint(ctx: Context, node_input: str) -> str:
    # 1. PII Scrubbing (regex for email and phone numbers)
    clean_input = node_input
    # Email regex
    clean_input = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[EMAIL_REDACTED]", clean_input)
    # Phone number regex
    clean_input = re.sub(r"\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}", "[PHONE_REDACTED]", clean_input)
    
    # Save scrubbed input to state
    ctx.state["query"] = clean_input

    # 2. Prompt Injection Keyword Detection
    injection_keywords = ["ignore previous instructions", "system prompt", "you are now", "developer mode", "bypass security"]
    is_injection = any(kw in clean_input.lower() for kw in injection_keywords)
    
    # 3. Domain-specific rule: restrict unsafe weather recommendations
    unsafe_weather_keywords = ["tornado", "hurricane", "blizzard", "tsunami", "extreme heatwave"]
    is_unsafe_request = any(kw in clean_input.lower() for kw in unsafe_weather_keywords)
    
    # Audit log
    audit_data = {
        "event": "security_checkpoint_evaluation",
        "has_pii": clean_input != node_input,
        "is_injection": is_injection,
        "is_unsafe_request": is_unsafe_request,
        "severity": "INFO"
    }

    if is_injection or is_unsafe_request:
        audit_data["severity"] = "CRITICAL"
        logger.error(json.dumps(audit_data))
        ctx.route = "SECURITY_EVENT"
        ctx.output = "Security check failed. Unsafe prompt or restricted input detected."
        return ctx.output

    logger.info(json.dumps(audit_data))
    ctx.route = DEFAULT_ROUTE
    return clean_input

@node(name="security_event_handler")
async def security_event_handler(ctx: Context, node_input: str) -> str:
    ctx.output = f"Access Denied: {node_input}"
    return ctx.output

@node(name="outfit_approval_checkpoint")
async def outfit_approval_checkpoint(ctx: Context, node_input: str) -> Any:
    # Save the current suggested outfit to state
    ctx.state["suggested_outfit"] = node_input

    # Check if we have a resume input from HITL
    if ctx.resume_inputs and "outfit_approval" in ctx.resume_inputs:
        user_response = ctx.resume_inputs.pop("outfit_approval")
        
        # Parse the user response
        user_response_str = str(user_response).lower()
        if any(approve_word in user_response_str for approve_word in ["yes", "approve", "good", "perfect", "ok"]):
            ctx.route = "approved"
            ctx.output = f"Outfit approved! Enjoy your event.\n\nSuggested Outfit:\n{node_input}"
            return
        else:
            # Save the feedback and route back to orchestrator
            ctx.state["user_feedback"] = user_response
            ctx.route = "needs_revision"
            ctx.output = f"User requested changes: {user_response}"
            return
    else:
        # First time visiting this node: pause and request user approval
        yield RequestInput(
            interrupt_id="outfit_approval",
            message=f"Here is your suggested outfit:\n\n{node_input}\n\nDo you approve this suggestion? (Yes / No + feedback)",
            response_schema=str
        )


@node(name="final_output")
async def final_output(ctx: Context, node_input: str) -> str:
    ctx.output = node_input
    return ctx.output

# --- Workflow definition ---

workflow = Workflow(
    name="style_match_workflow",
    description="Personal Styling Concierge Workflow",
    edges=[
        Edge(from_node=START, to_node=security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=orchestrator_agent),
        Edge(from_node=security_checkpoint, to_node=security_event_handler, route="SECURITY_EVENT"),
        Edge(from_node=orchestrator_agent, to_node=outfit_approval_checkpoint),
        Edge(from_node=outfit_approval_checkpoint, to_node=orchestrator_agent, route="needs_revision"),
        Edge(from_node=outfit_approval_checkpoint, to_node=final_output, route="approved"),
    ]
)

app = App(
    root_agent=workflow,
    name="app",
)
