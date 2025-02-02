import { NextRequest, NextResponse } from "next/server";
import { Message as VercelChatMessage, StreamingTextResponse } from "ai";

import {
  AIMessage,
  BaseMessage,
  ChatMessage,
  HumanMessage,
  SystemMessage,
} from "@langchain/core/messages";

export const runtime = "edge";

async function fetchGitHubTools(userInput: string) {
  const response = await fetch(`http://127.0.0.1:8000/github-toolkit?user_input=${encodeURIComponent(userInput)}`);
  if (!response.ok) {
    throw new Error("Failed to fetch GitHub Toolkit");
  }
  return response.json();
}

const convertVercelMessageToLangChainMessage = (message: VercelChatMessage) => {
  if (message.role === "user") {
    return new HumanMessage(message.content);
  } else if (message.role === "assistant") {
    return new AIMessage(message.content);
  } else {
    return new ChatMessage(message.content, message.role);
  }
};

const convertLangChainMessageToVercelMessage = (message: BaseMessage) => {
  if (message.getType() === "human") {
    return { content: message.content, role: "user" };
  } else if (message.getType() === "ai") {
    return {
      content: message.content,
      role: "assistant",
      tool_calls: (message as AIMessage).tool_calls,
    };
  } else {
    return { content: message.content, role: message.getType() };
  }
};

const AGENT_SYSTEM_TEMPLATE = `You are a talking parrot named Polly. All final responses must be how a talking parrot would respond. Squawk often!`;

/**
 * This handler initializes and calls an tool caling ReAct agent.
 * See the docs for more information:
 *
 * https://langchain-ai.github.io/langgraphjs/tutorials/quickstart/
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const userInput = body.user_input; // Assume user input is passed in the request body
    const returnIntermediateSteps = body.show_intermediate_steps;

    const toolsResponse = await fetchGitHubTools(userInput);
    const responseContent = toolsResponse.response;

    if (!returnIntermediateSteps) {
      const textEncoder = new TextEncoder();
      const transformStream = new ReadableStream({
        start(controller) {
          controller.enqueue(textEncoder.encode(responseContent));
          controller.close();
        },
      });

      return new StreamingTextResponse(transformStream);
    } else {
      return NextResponse.json(
        {
          messages: [{ content: responseContent.output, role: "assistant" }],
        },
        { status: 200 },
      );
    }
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: e.status ?? 500 });
  }
}
