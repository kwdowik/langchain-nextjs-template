from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json
import logging
import asyncio
from .agent import create_github_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/api/chat/github-cli/analyze")
async def analyze_github_activity(request: Request):
    """Endpoint to analyze GitHub activity using the CLI agent."""
    try:
        # Parse request body
        body = await request.json()
        messages = body.get("messages", [])
        config = body.get("config", {})
        
        # Get the last message as input
        user_input = messages[-1]["content"] if messages else ""
        
        # Create agent
        agent_executor = create_github_agent()
        
        async def response_generator():
            try:
                # Run the agent
                result = await agent_executor.ainvoke(
                    {
                        "messages": user_input  # All messages except the last one
                    },
                    config
                )
                
                logger.info(f"Agent result: {result}")
                
                # Extract the final response
                if isinstance(result, dict):
                    if "output" in result:
                        response_content = result["output"]
                    elif "messages" in result:
                        # Get the last non-tool message from the conversation
                        for msg in reversed(result["messages"]):
                            if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_call_id"):
                                response_content = msg.content
                                break
                        else:
                            response_content = "I was unable to process your request properly."
                    else:
                        logger.error(f"Unexpected result format: {result}")
                        response_content = "I was unable to process your request properly."
                else:
                    logger.error(f"Unexpected result type: {type(result)}")
                    response_content = "I was unable to process your request properly."
                
                response = {
                    "messages": [{
                        "role": "assistant",
                        "content": response_content
                    }]
                }
                yield json.dumps(response) + "\n"
                
            except Exception as e:
                logger.error(f"Error in agent execution: {str(e)}", exc_info=True)
                error_response = {
                    "messages": [{
                        "role": "assistant",
                        "content": f"An error occurred: {str(e)}"
                    }]
                }
                yield json.dumps(error_response) + "\n"
        
        return StreamingResponse(
            response_generator(),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {"error": str(e)} 