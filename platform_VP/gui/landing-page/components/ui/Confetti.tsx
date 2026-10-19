"use client";
import { m as motion } from "framer-motion";
import { useMotionSettings } from "../../lib/motion";
export default function Confetti({ active }: { active: boolean }) {
  const { enabled } = useMotionSettings();
  return active && enabled ? (
    <span className="confetti" aria-hidden="true">
      {Array.from({ length: 14 }, (_, i) => {
        const angle = (Math.PI * 2 * i) / 14;
        return (
          <motion.i
            key={i}
            style={{ background: ["#e46921", "#f4ae43", "#217eaa"][i % 3] }}
            initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
            animate={{
              x: Math.cos(angle) * 150,
              y: Math.sin(angle) * 150 - 30,
              opacity: 0,
              rotate: 160 + i * 30,
              scale: 0.4,
            }}
            transition={{ duration: 1.1, ease: "easeOut" }}
          />
        );
      })}
    </span>
  ) : null;
}
