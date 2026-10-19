"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { LazyMotion, MotionConfig } from "framer-motion";

const loadMotionFeatures = () =>
  import("./motion-features").then((module) => module.default);

export const ease = [0.2, 0.8, 0.2, 1] as const;
export const revealVariants = {
  hidden: { opacity: 0, y: 40, filter: "blur(8px)" },
  visible: { opacity: 1, y: 0, filter: "blur(0px)" },
};
const MotionSettings = createContext({
  enabled: true,
  toggle: () => {},
  reduced: false,
});
export function useMotionSettings() {
  return useContext(MotionSettings);
}

export function MotionProvider({ children }: { children: ReactNode }) {
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(false);
  const enabled = !paused && !reduced;
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.motion = enabled ? "active" : "paused";
    if (
      !enabled ||
      !window.matchMedia(
        "(min-width: 901px) and (hover: hover) and (pointer: fine)",
      ).matches
    )
      return;
    let cancelled = false;
    let dispose: (() => void) | undefined;
    // Native touch scrolling avoids downloading desktop scroll physics on phones.
    void Promise.all([
      import("lenis"),
      import("gsap"),
      import("gsap/ScrollTrigger"),
    ]).then(([{ default: Lenis }, { gsap }, { ScrollTrigger }]) => {
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      const lenis = new Lenis({
        duration: 1.05,
        anchors: { offset: -88 },
        smoothWheel: true,
        syncTouch: false,
      });
      lenis.on("scroll", ScrollTrigger.update);
      const tick = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(tick);
      dispose = () => {
        gsap.ticker.remove(tick);
        lenis.destroy();
      };
    });
    return () => {
      cancelled = true;
      dispose?.();
    };
  }, [enabled]);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          (entry.target as HTMLElement).dataset.inView = entry.isIntersecting
            ? "true"
            : "false";
        });
      },
      { rootMargin: "80px", threshold: 0 },
    );
    document
      .querySelectorAll("[data-animated-section]")
      .forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return (
    <MotionSettings.Provider
      value={{ enabled, reduced, toggle: () => setPaused((v) => !v) }}
    >
      <MotionConfig reducedMotion="user">
        <LazyMotion features={loadMotionFeatures}>{children}</LazyMotion>
      </MotionConfig>
    </MotionSettings.Provider>
  );
}
