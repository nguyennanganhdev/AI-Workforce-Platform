"use client";
import { m as motion, useMotionValue, useSpring } from "framer-motion";
import type { CSSProperties, ReactNode } from "react";
import { useMotionSettings } from "../../lib/motion";

export default function TiltCard({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const { enabled } = useMotionSettings();
  const rx = useMotionValue(0),
    ry = useMotionValue(0);
  const x = useSpring(rx, { stiffness: 140, damping: 20 }),
    y = useSpring(ry, { stiffness: 140, damping: 20 });
  return (
    <motion.div
      className={`tilt-card ${className}`}
      style={
        {
          rotateX: enabled ? x : 0,
          rotateY: enabled ? y : 0,
          transformPerspective: 1200,
        } as CSSProperties
      }
      onPointerMove={(event) => {
        if (!enabled || event.pointerType !== "mouse") return;
        const r = event.currentTarget.getBoundingClientRect();
        const px = (event.clientX - r.left) / r.width,
          py = (event.clientY - r.top) / r.height;
        rx.set((0.5 - py) * 14);
        ry.set((px - 0.5) * 16);
        event.currentTarget.style.setProperty("--spot-x", `${px * 100}%`);
        event.currentTarget.style.setProperty("--spot-y", `${py * 100}%`);
      }}
      onPointerLeave={() => {
        rx.set(0);
        ry.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}
