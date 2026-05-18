from typing import Annotated, List, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Flows through every node in the LangGraph graph.

    messages: The full conversation history — HumanMessages, AIMessages,
              ToolMessages — everything the LLM needs to reason about.

    Why Annotated + Sequence?
      LangGraph uses the type hint to know how to merge state updates.
      A plain list would be replaced on each update; Sequence with an
      annotation tells LangGraph to *append* new messages instead.
    """

    messages: Annotated[List[BaseMessage], add_messages]
