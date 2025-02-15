import { Message } from "ai";
import { Code } from "./ui/code";

export function IntermediateStep({ message }: { message: Message }) {
  try {
    const toolData = JSON.parse(message.content);
    return (
      <div className="mx-auto mb-8 max-w-[768px]">
        <div className="rounded-lg border bg-muted p-4">
          <div className="mb-2 flex items-center">
            <span className="mr-2 text-sm font-semibold">🛠️ Tool Execution:</span>
            <code className="rounded bg-primary px-1 py-0.5 text-sm">
              {toolData.tool_name}
            </code>
          </div>

          <div className="mb-4">
            <div className="text-sm font-semibold text-muted-foreground">Input:</div>
            <Code className="mt-1 text-sm">{JSON.stringify(toolData.tool_input, null, 2)}</Code>
          </div>

          <div>
            <div className="text-sm font-semibold text-muted-foreground">Output:</div>
            <Code className="mt-1 text-sm">
              {typeof toolData.tool_output === 'string' 
                ? toolData.tool_output 
                : JSON.stringify(toolData.tool_output, null, 2)}
            </Code>
          </div>
        </div>
      </div>
    );
  } catch (error) {
    console.error("Error parsing tool data:", error);
    return null;
  }
}
