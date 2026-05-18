"""
  The resulting loop looks like this:

      [START]
         ↓
    [agent node]  ← LLM decides what to do
         ↓
   [should_continue]
      ↙        ↘
  "tools"       END
     ↓
  [tools node]  ← executes the chosen tool
     ↓
  [agent node]  ← LLM reads tool result and decides again
     ↓
     ...

  This loop lets the agent call multiple tools before giving a final answer.
"""

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from agent.nodes import build_agent_node, should_continue
from agent.state import AgentState
from agent.tools import compare_formations, get_player_stats, scout_role
from config import get_llm


def build_football_agent():
    """
    Build and compile the football analysis agent.

    Returns a compiled LangGraph runnable — call it with:
        await agent.ainvoke({"messages": [HumanMessage(content="...")]})
    """
    # ── 1. Tools ─────────────────────────────────────────────────────────────
    # All tools the LLM can choose from.
    tools = [get_player_stats, compare_formations, scout_role]

    # ── 2. LLM with tools bound ───────────────────────────────────────────────
    # bind_tools() tells the LLM the tool names, descriptions, and param schemas.
    # Without this the LLM wouldn't know any tools exist.
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)

    # ── 3. Build node functions ───────────────────────────────────────────────
    call_agent = build_agent_node(llm_with_tools)

    # ToolNode is LangGraph's built-in executor.
    # It reads tool_calls from the LLM message, runs the matching function,
    # and adds a ToolMessage with the result back to state.
    tool_node = ToolNode(tools)

    # ── 4. Create the graph ───────────────────────────────────────────────────
    workflow = StateGraph(AgentState)

    # Register nodes — the string name is how we reference them in edges
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", tool_node)

    # The graph starts here
    workflow.set_entry_point("agent")

    # Conditional edge: after the agent node, call should_continue() to route
    workflow.add_conditional_edges(
        "agent",          # from this node
        should_continue,  # call this router
        {
            "tools": "tools",  # if router returns "tools" → go to tools node
            END: END,          # if router returns END     → stop the graph
        },
    )

    # Unconditional edge: after tools run, always go back to the agent
    # (so the LLM can read the result and decide the next step)
    workflow.add_edge("tools", "agent")

    # Compile locks the graph and returns a runnable
    return workflow.compile()