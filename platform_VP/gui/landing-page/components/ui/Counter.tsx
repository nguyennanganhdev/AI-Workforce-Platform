"use client";
import { useEffect, useRef } from "react";
import { animate, useInView } from "framer-motion";
import { useMotionSettings } from "../../lib/motion";
export default function Counter({
  value,
  suffix = "",
  prefix = "",
}: {
  value: number;
  suffix?: string;
  prefix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const visible = useInView(ref, { once: true });
  const { enabled } = useMotionSettings();
  useEffect(() => {
    if (!visible || !enabled || !ref.current) return;
    const controls = animate(0, value, {
      duration: 1.6,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (current) => {
        if (ref.current)
          ref.current.textContent = `${prefix}${Math.round(current)}${suffix}`;
      },
    });
    return () => {
      controls.stop();
      if (ref.current) ref.current.textContent = `${prefix}${value}${suffix}`;
    };
  }, [visible, enabled, value, prefix, suffix]);
  return (
    <span ref={ref}>
      {prefix}
      {value}
      {suffix}
    </span>
  );
}
