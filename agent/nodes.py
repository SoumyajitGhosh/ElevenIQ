from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END

from agent.state import AgentState

# ── System Prompt ─────────────────────────────────────────────────────────────
# This is the "personality" of the analyst.
# Clear, detailed prompts = better tool selection and better answers.

SYSTEM_PROMPT = """You are an expert football analyst and scout with deep knowledge of:
- Player statistics, strengths, and weaknesses
- Tactical formations and systems (4-3-3, 4-2-3-1, 3-4-3, 4-4-2)
- Positional roles and the specific attributes they demand

You think and speak like a real analyst — you reference actual numbers, draw
tactical comparisons, and explain your reasoning clearly and confidently.

Guidelines:
- Always use your tools to ground your answers in real data.
- Be direct: lead with the key insight, then support it with stats.
- Keep responses concise but insightful — like a proper scout report.
- If asked a follow-up, use the conversation history to maintain context.
"""


# ── Agent Node ────────────────────────────────────────────────────────────────

def build_agent_node(llm_with_tools: BaseChatModel):
    """
    Factory that returns the agent node function with the LLM baked in.

    CONCEPT: The agent node is where the LLM reads the conversation history
    and decides: "Should I call a tool, or do I have enough to answer?"

    We use a factory pattern so the node function closes over `llm_with_tools`
    without needing it as an argument — keeping the signature clean for LangGraph.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
    ])

    async def call_agent(state: AgentState) -> dict:
        """
        The agent node: format the conversation history, call the LLM,
        and return the response to be appended to state.
        """
        formatted_messages = prompt.format_messages(messages=state["messages"])
        response = await llm_with_tools.ainvoke(formatted_messages)
        # Returning {"messages": [response]} tells LangGraph to append this
        # to the existing messages list in state (not replace it).
        return {"messages": [response]}

    return call_agent


# ── Router Function ───────────────────────────────────────────────────────────

def should_continue(state: AgentState) -> str:
    """
    CONCEPT: The router / control-flow function.

    After the LLM responds, LangGraph calls this to decide what happens next.
    It inspects the last message:
      - Tool calls present → route to "tools" node (LLM needs more data)
      - No tool calls      → route to END (LLM has a final answer)

    This tiny function is what creates the agent LOOP. The agent can call
    multiple tools in sequence before it's satisfied it has enough to answer.

    Returns:
        "tools" — send execution to the ToolNode
        END     — stop the graph and return the final answer
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END