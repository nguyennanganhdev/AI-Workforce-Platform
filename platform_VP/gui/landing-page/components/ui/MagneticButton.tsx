"use client";
import { m as motion, useMotionValue, useSpring } from "framer-motion";
import type { ReactNode, MouseEvent } from "react";
import { useMotionSettings } from "../../lib/motion";

export default function MagneticButton({
  children,
  href,
  className = "",
  onClick,
  type = "button",
  disabled = false,
}: {
  children: ReactNode;
  href?: string;
  className?: string;
  onClick?: (event: MouseEvent<HTMLElement>) => void;
  type?: "button" | "submit";
  disabled?: boolean;
}) {
  const { enabled } = useMotionSettings();
  const x = useMotionValue(0),
    y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 260, damping: 20 }),
    sy = useSpring(y, { stiffness: 260, damping: 20 });
  const move = (event: MouseEvent<HTMLElement>) => {
    if (!enabled || !window.matchMedia("(pointer: fine)").matches) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    x.set((event.clientX - bounds.left - bounds.width / 2) * 0.22);
    y.set((event.clientY - bounds.top - bounds.height / 2) * 0.3);
  };
  const props = {
    className: `button button-primary ${className}`,
    style: { x: enabled ? sx : 0, y: enabled ? sy : 0 },
    onMouseMove: move,
    onMouseLeave: () => {
      x.set(0);
      y.set(0);
    },
    onClick,
  };
  return href ? (
    <motion.a {...props} href={href}>
      {children}
    </motion.a>
  ) : (
    <motion.button {...props} type={type} disabled={disabled}>
      {children}
    </motion.button>
  );
}
