import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()  # reads .env file if it exists


def get_llm() -> ChatOpenAI:
    """
    Create and return the LLM instance.

    Raises a clear error if the API key is missing — much friendlier than
    a cryptic authentication error from deep inside a library.

    Model choice: os.getenv("MODEL_NAME") — capable enough for tool-use and reasoning,
    fast, and cheap. Swap for "gpt-4o" if you want higher quality answers.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "\nOPENAI_API_KEY is not set.\n"
            "Create a .env file in the project root with:\n"
            "  OPENAI_API_KEY=sk-...\n"
        )

    return ChatOpenAI(
        model=os.getenv("MODEL_NAME"),
        temperature=0,
        api_key=api_key,
    )
