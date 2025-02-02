from fastapi import FastAPI, Query
from langchain_community.agent_toolkits.github.toolkit import GitHubToolkit
from langchain_community.utilities.github import GitHubAPIWrapper
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from langchain import hub
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Define a Pydantic model for the tool
class ToolModel(BaseModel):
    name: str
    description: str
    args_schema: str  # Adjust the type if needed
    mode: str


@app.get("/github-toolkit")
def get_github_toolkit(user_input: str = Query(..., description="User input for the agent")):
    github = GitHubAPIWrapper(
        github_app_id=os.getenv("GITHUB_APP_ID"),
        github_app_private_key=os.getenv("GITHUB_APP_PRIVATE_KEY"),
        github_repository='kwdowik/eisenhower'
        # github_repository=os.getenv("GITHUB_REPOSITORY"),
    )
    toolkit = GitHubToolkit.from_github_api_wrapper(github)
    tools = toolkit.get_tools()
    
    # Print all keys of the first tool object
    print("Successfully retrieved tools")

    # Construct the ReAct agent
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    # Invoke the agent with user input
    response = agent_executor.invoke({"input": user_input})
    print(response)
    
    # Return the response
    return {"response": response}


