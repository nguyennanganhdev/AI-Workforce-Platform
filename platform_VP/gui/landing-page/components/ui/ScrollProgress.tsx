"use client";
import { m as motion, useScroll, useSpring } from "framer-motion";
import { useMotionSettings } from "../../lib/motion";
export default function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 120, damping: 28 });
  const { enabled } = useMotionSettings();
  return (
    <motion.div
      className="scroll-progress"
      style={{ scaleX: enabled ? scaleX : scrollYProgress }}
      aria-hidden="true"
    />
  );
}
