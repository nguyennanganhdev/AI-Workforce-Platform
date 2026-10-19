"use client";
import { m as motion } from "framer-motion";
import type { ReactNode } from "react";
import { ease, useMotionSettings } from "../../lib/motion";

export default function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const { enabled } = useMotionSettings();
  return (
    <motion.div
      className={className}
      initial={false}
      whileInView={
        enabled
          ? { opacity: [0, 1], y: [32, 0], filter: ["blur(6px)", "blur(0px)"] }
          : undefined
      }
      viewport={{ once: true, amount: 0.12 }}
      transition={{ duration: 0.85, delay, ease }}
    >
      {children}
    </motion.div>
  );
}
