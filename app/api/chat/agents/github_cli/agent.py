from typing import List
from langchain.agents import AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
import os
import logging
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
import tiktoken

from .tools import get_github_cli_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text using tiktoken."""
    encoding = tiktoken.get_encoding("cl100k_base")  # This is used by most recent models
    return len(encoding.encode(text))

def create_github_agent(model_name: str = "llama3-8b-8192", temperature: float = 0) -> AgentExecutor:
    """Creates a GitHub CLI agent using ReAct pattern."""
    if not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY environment variable is not set")

    model = init_chat_model(model_name, model_provider="groq")
    
    tools = get_github_cli_tools()
    logger.info(f"Loaded tools: {[tool.name for tool in tools]}")
    
    # Format tools for prompt
    tool_strings = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
    
    system_prompt = f"""You are a GitHub CLI assistant that helps analyze GitHub activity.

Available tools:
{tool_strings}

Follow these rules:
1. Use the appropriate tool for each request
2. Only use real data from the tools
3. Present data clearly with verification links
4. If a tool returns an error, explain it to the user"""

    # Log token counts
    logger.info(f"System prompt token count: {count_tokens(system_prompt)}")
    logger.info(f"Tool descriptions token count: {count_tokens(tool_strings)}")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages")
    ])

    # Create the ReAct agent with memory
    memory = MemorySaver()
    agent_executor = create_react_agent(
        model,
        tools=tools,
        prompt=prompt,
        checkpointer=memory,
    )

    return agent_executor
