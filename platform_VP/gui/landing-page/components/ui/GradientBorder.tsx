import type { ReactNode } from "react";
export default function GradientBorder({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`gradient-border ${className}`}>
      <div className="gradient-border-inner">{children}</div>
    </div>
  );
}
