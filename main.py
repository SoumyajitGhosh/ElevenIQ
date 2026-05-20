import asyncio

from langchain_core.messages import HumanMessage

from agent.graph import build_football_agent
from config import get_llm

async def chat() -> None:
    """Run an interactive CLI chat session with the football analysis agent."""

    print("\n" + "=" * 56)
    print("  ⚽  ElevenIQ: Football Analysis Agent")
    print("  Powered by LangGraph + G", get_llm().model_name)
    print("=" * 56)
    print("Ask me about players, formations, or tactical roles.")
    print("The agent will use tools to ground every answer in data.")
    print("Type 'quit' or 'exit' to end the session.\n")

    # Build the agent graph once — reuse it across the whole conversation
    agent = build_football_agent()

    # This list IS the agent's memory.
    # CONCEPT: We pass the full history on every invocation so the LLM
    # always has context for follow-up questions.
    conversation_history = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye! ⚽")
            break

        # Append the new human message to history
        conversation_history.append(HumanMessage(content=user_input))

        # Invoke the agent with the full conversation history as state.
        # The graph will loop (agent → tools → agent → ...) until it reaches END.
        result = await agent.ainvoke({"messages": conversation_history})

        # Update history with everything the agent did this turn
        # (its reasoning, tool calls, tool results, and final answer)
        conversation_history = list(result["messages"])

        # The last message is always the final AI response
        final_response = result["messages"][-1].content
        print(f"\nAnalyst: {final_response}\n")


if __name__ == "__main__":
    asyncio.run(chat())
