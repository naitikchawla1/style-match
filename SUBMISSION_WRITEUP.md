# Submission Write-Up: StyleMatch Styling Concierge

## Problem Statement
Deciding what to wear for different occasions while accounting for local weather forecasts and one's actual wardrobe contents is a daily friction point. Most online styling advice is generic, disconnected from what clothes the user actually owns, and blind to local weather parameters. StyleMatch addresses this need by providing a secure, personalized styling assistant that aligns recommendations to both the user's local wardrobe inventory and weather conditions.

---

## Solution Architecture

StyleMatch uses a modular multi-agent system orchestrated through a directed workflow graph:

```mermaid
graph TD
    START(START) --> SC[security_checkpoint]
    SC -- DEFAULT_ROUTE --> OA[orchestrator_agent]
    SC -- SECURITY_EVENT --> SEH[security_event_handler]
    
    OA --> AC[outfit_approval_checkpoint]
    AC -- needs_revision --> OA
    AC -- approved --> FO[final_output]

    subgraph Sub-Agents (via AgentTool)
        OA -.-> WA[wardrobe_agent]
        OA -.-> WMA[weather_matcher_agent]
    end

    subgraph Local MCP Server
        WA --> |get_wardrobe_items| MCP[MCP Server]
        WMA --> |get_weather_forecast| MCP
        OA --> |save_selected_outfit| MCP
    end
```

---

## Concepts Used

1. **ADK 2.0 Workflow API**: Used to design the execution flow graph in [app/agent.py](file:///c:/Users/NAITIK%20CHAWLA/Documents/adk-workspace/style-match/app/agent.py#L143-L162).
2. **LlmAgent**: Used for specialized sub-agents (`wardrobe_agent`, `weather_matcher_agent`) and the central `orchestrator_agent` in [app/agent.py](file:///c:/Users/NAITIK%20CHAWLA/Documents/adk-workspace/style-match/app/agent.py#L32-L79).
3. **AgentTool**: Handled sub-agent delegation (`wardrobe_agent` and `weather_matcher_agent` tool parameters) in [app/agent.py](file:///c:/Users/NAITIK%20CHAWLA/Documents/adk-workspace/style-match/app/agent.py#L55-L60).
4. **MCP Server**: Implemented as a stdio server in [app/mcp_server.py](file:///c:/Users/NAITIK%20CHAWLA/Documents/adk-workspace/style-match/app/mcp_server.py) to manage clothes and retrieve simulated weather forecasts.
5. **Security Checkpoint Node**: An entry gate node (`security_checkpoint`) protecting the model from prompt injections and PII leaks.
6. **Agents CLI**: Scaffolding, dependency syncing, and playground testing managed via `agents-cli` toolbelt.

---

## Security Design

- **PII Scrubbing**: Standard regex filters redact phone numbers and emails to prevent leakage of user contact data to generative models.
- **Prompt Injection Detection**: String matching blocks common jailbreaks (`"ignore previous instructions"`, `"system prompt"`, etc.) and redirects flow away from LLMs.
- **Structured Audit Logging**: Decisions and security evaluations are logged using JSON formatting with severity tags (`INFO` / `CRITICAL`) for ingestion into cloud monitoring engines.
- **Domain Restriction**: Restricts recommendations under extreme weather conditions (`"hurricane"`, `"blizzard"`, etc.) for user safety.

---

## MCP Server Design

The local Model Context Protocol (MCP) server exposes 3 critical capabilities to the workflow:
1. `get_wardrobe_items()`: Retrieves the user's available wardrobe list so recommendation outfits remain grounded in reality.
2. `get_weather_forecast(location: str)`: Provides simulated weather metrics so layers matches environmental conditions.
3. `save_selected_outfit(outfit: str)`: Commits the finalized style choice to the user's diary, facilitating session persistence.

---

## HITL Flow (Human-in-the-Loop)

The `outfit_approval_checkpoint` pauses execution using ADK's `RequestInput` class:
- **Why**: Outfit styling is highly subjective. Rather than deciding on a single plan, StyleMatch requests user approval and allows revisions.
- **How**: If the user provides feedback (e.g. *"Can we change to a denim jacket"*), the workflow registers the feedback in the session state `ctx.state` and loops back to `orchestrator_agent` to regenerate suggestions.

---

## Demo Walkthrough

The project covers 3 validation test cases in the local playground:
1. **Successful suggestion**: User inputs a styling request for a meeting in London. The agent fetches clothes, reviews London's rainy forecast, and returns a cohesive outfit.
2. **Security Block**: An injection query is immediately intercepted by the security gate, producing an `Access Denied` output without running LLM nodes.
3. **Revision feedback**: A user rejects a suggested suit. The orchestrator receives the feedback and proposes a denim jacket combination instead.

---

## Impact & Value Statement

StyleMatch saves time, reduces decision fatigue, and grounds styling advice in actual user assets and current environmental states. The architecture secures user data against leaks and jailbreaks, while the feedback loop ensures the concierge adaptively aligns with specific user preferences.
