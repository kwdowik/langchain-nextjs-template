import { cn } from "@/utils/cn";

interface CodeProps extends React.HTMLAttributes<HTMLPreElement> {
  children: string;
}

export function Code({ className, children, ...props }: CodeProps) {
  return (
    <pre
      className={cn(
        "rounded-md bg-secondary p-4 overflow-x-auto",
        className
      )}
      {...props}
    >
      <code>{children}</code>
    </pre>
  );
} 