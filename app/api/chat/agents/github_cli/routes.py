from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import json
import logging
import tiktoken
from .agent import create_github_agent, count_tokens

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def convert_message_for_agent(msg: dict) -> dict:
    """Convert message to format expected by agent, preserving tool_call_id if present."""
    if msg["role"] == "tool":
        try:
            content_dict = json.loads(msg["content"])
            return {
                "role": "tool",
                "content": msg["content"],
                "tool_call_id": content_dict.get("tool_call_id"),
                "name": content_dict.get("tool_name")
            }
        except json.JSONDecodeError:
            logger.warning(f"Could not parse tool message content: {msg['content']}")
            return msg
    return msg

@router.post("/api/chat/github-cli/analyze")
async def analyze_github_activity(request: Request):
    """Endpoint to analyze GitHub activity using the CLI agent.
    
    Expects a JSON body with:
    - messages: List of chat messages with role and content
    - config: Optional configuration for the agent
    
    Returns a streaming response with the agent's replies.
    """
    try:
        body = await request.json()
        messages = body.get("messages", [])
        session_id = body.get("session_id", "")
        show_intermediate_steps = body.get("show_intermediate_steps", True)  # Default to True
        
        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
        # Convert messages to format expected by agent
        converted_messages = [convert_message_for_agent(msg) for msg in messages]
        
        # Count tokens in messages
        total_message_tokens = 0
        for msg in messages:
            token_count = count_tokens(msg["content"])
            logger.info(f"Message token count: {token_count} for message: {msg['role']}")
            total_message_tokens += token_count
        
        logger.info(f"Total message history token count: {total_message_tokens}")
        
        # Create agent
        agent_executor = create_github_agent()
        
        async def response_generator():
            try:
                # Use all messages for context
                input_data = {
                    "messages": converted_messages
                }
                logger.info(f"Sending to agent: {json.dumps(input_data, indent=2)}")
                
                async for chunk in agent_executor.astream(
                    input_data,
                    {"configurable": {"thread_id": session_id}}
                ):
                    logger.info(f"Streaming chunk type: {type(chunk)}")
                    logger.info(f"Streaming chunk content: {json.dumps(chunk, default=str, indent=2)}")
                    
                    if isinstance(chunk, dict) and "agent" in chunk and "messages" in chunk["agent"]:
                        msg = chunk["agent"]["messages"][-1]  # Get the latest message
                        logger.info(f"Processing message: {json.dumps(msg, default=str, indent=2)}")
                        
                        # Handle tool selection (AI message with tool_calls)
                        if hasattr(msg, "additional_kwargs") and msg.additional_kwargs.get("tool_calls"):
                            logger.info("Found tool calls in message")
                            tool_calls = msg.additional_kwargs["tool_calls"]
                            for tool_call in tool_calls:
                                try:
                                    # Check if the content is a JSON string and parse it
                                    content = msg.content
                                    if content and content.startswith('I called the tool'):
                                        try:
                                            # Extract the JSON part from the message
                                            json_start = content.find('{')
                                            json_end = content.rfind('}') + 1
                                            if json_start != -1 and json_end != -1:
                                                content = content[json_start:json_end]
                                                content = json.loads(content)
                                                if isinstance(content, dict):
                                                    tool_step = content
                                                    tool_step["tool_call_id"] = tool_call["id"]
                                        except (json.JSONDecodeError, ValueError) as e:
                                            logger.warning(f"Failed to parse tool call content as JSON: {e}")
                                    
                                    if not content or not isinstance(content, dict):
                                        tool_step = {
                                            "thought": msg.content if msg.content else "Selecting tool...",
                                            "tool_name": tool_call["function"]["name"],
                                            "tool_input": json.loads(tool_call["function"]["arguments"]),
                                            "tool_call_id": tool_call["id"]
                                        }
                                    
                                    logger.info(f"Processing tool call: {json.dumps(tool_step, indent=2)}")
                                    
                                    if show_intermediate_steps:
                                        response = {
                                            "messages": [{
                                                "role": "tool",
                                                "content": json.dumps(tool_step, indent=2),
                                                "tool_call_id": tool_call["id"],
                                                "name": tool_call["function"]["name"]
                                            }]
                                        }
                                        logger.info(f"Yielding tool call: {json.dumps(response, indent=2)}")
                                        yield json.dumps(response) + "\n"
                                except Exception as e:
                                    logger.error(f"Error processing tool call: {e}", exc_info=True)
                        
                        # Handle tool response
                        elif hasattr(msg, "additional_kwargs") and "name" in msg.additional_kwargs:
                            try:
                                tool_call_id = getattr(msg, "tool_call_id", None)
                                if not tool_call_id and hasattr(msg, "additional_kwargs"):
                                    tool_call_id = msg.additional_kwargs.get("tool_call_id")
                                
                                content = msg.content
                                # Check if the content is a JSON string and parse it
                                if content and content.startswith('I called the tool'):
                                    try:
                                        # Extract the JSON part from the message
                                        json_start = content.find('{')
                                        json_end = content.rfind('}') + 1
                                        if json_start != -1 and json_end != -1:
                                            content = content[json_start:json_end]
                                    except (ValueError) as e:
                                        logger.warning(f"Failed to extract JSON from tool response: {e}")
                                
                                tool_response = {
                                    "tool_name": msg.additional_kwargs["name"],
                                    "tool_output": content,
                                    "tool_call_id": tool_call_id
                                }
                                
                                try:
                                    tool_response["tool_output"] = json.loads(content)
                                except json.JSONDecodeError:
                                    pass  # Keep as string if not JSON
                                
                                if show_intermediate_steps and tool_call_id:
                                    response = {
                                        "messages": [{
                                            "role": "tool",
                                            "content": json.dumps(tool_response, indent=2),
                                            "tool_call_id": tool_call_id,
                                            "name": msg.additional_kwargs["name"]
                                        }]
                                    }
                                    logger.info(f"Yielding tool response: {json.dumps(response, indent=2)}")
                                    yield json.dumps(response) + "\n"
                            except Exception as e:
                                logger.error(f"Error processing tool response: {e}", exc_info=True)
                        
                        # Handle final response
                        elif hasattr(msg, "content") and msg.content:
                            logger.info("Found final response")
                            response = {
                                "messages": [{
                                    "role": "assistant",
                                    "content": msg.content
                                }]
                            }
                            logger.info(f"Yielding final response: {json.dumps(response, indent=2)}")
                            yield json.dumps(response) + "\n"
                    else:
                        logger.warning(f"Unexpected chunk format: {chunk}")
                
            except Exception as e:
                logger.error(f"Error in agent execution: {str(e)}", exc_info=True)
                error_message = str(e)
                
                # Parse Groq error for tool use failures
                if "tool_use_failed" in error_message:
                    try:
                        error_data = json.loads(error_message.split(" - ", 1)[1])
                        failed_generation = error_data["error"].get("failed_generation", "")
                        
                        # Extract tool call details
                        if "<tool-use>" in failed_generation:
                            tool_data = json.loads(failed_generation.replace("<tool-use>", "").strip())
                            if tool_data.get("tool_calls"):
                                tool_call = tool_data["tool_calls"][0]
                                tool_name = tool_call["function"]["name"]
                                parameters = tool_call.get("parameters", {})
                                
                                # Create user-friendly error message
                                missing_params = [k for k, v in parameters.items() if v is None]
                                if missing_params:
                                    error_message = (
                                        f"I need more information to use the {tool_name} tool. "
                                        f"Please provide values for: {', '.join(missing_params)}"
                                    )
                                else:
                                    error_message = (
                                        f"There was an issue with the {tool_name} tool parameters. "
                                        f"Please check the values provided: {json.dumps(parameters, indent=2)}"
                                    )
                    except Exception as parse_error:
                        logger.error(f"Error parsing tool error: {parse_error}", exc_info=True)
                
                yield json.dumps({
                    "messages": [{
                        "role": "assistant",
                        "content": error_message
                    }]
                }) + "\n"
        
        return StreamingResponse(
            response_generator(),
            media_type="text/event-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 