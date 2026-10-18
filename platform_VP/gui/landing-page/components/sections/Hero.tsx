"use client";
import Image from "../ui/AssetImage";
import {
  m as motion,
  useMotionValue,
  useSpring,
  useTransform,
} from "framer-motion";
import {
  ArrowRight,
  Box,
  Check,
  ChartNoAxesCombined,
  MessageCircle,
  Play,
  PlugZap,
  Workflow,
} from "lucide-react";
import MagneticButton from "../ui/MagneticButton";
import { ease, useMotionSettings } from "../../lib/motion";
import { pageCopy } from "../../lib/content";

export default function Hero() {
  const { enabled } = useMotionSettings();
  const mx = useMotionValue(0),
    my = useMotionValue(0);
  const x = useSpring(mx, { stiffness: 65, damping: 22 }),
    y = useSpring(my, { stiffness: 65, damping: 22 });
  const fx = useTransform(x, (v) => v * -14),
    fy = useTransform(y, (v) => v * -10);
  const ix = useTransform(x, (v) => v * 18),
    iy = useTransform(y, (v) => v * 14);
  const cx = useTransform(x, (v) => v * 26),
    cy = useTransform(y, (v) => v * 20);
  return (
    <section className="hero" data-animated-section>
      <div className="hero-aurora aurora-orange" aria-hidden="true" />
      <div className="hero-aurora aurora-blue" aria-hidden="true" />
      <div className="hero-aurora aurora-cyan" aria-hidden="true" />
      <div className="hero-stars" aria-hidden="true" />
      <div className="container hero-layout">
        <div className="hero-copy">
          <motion.div
            className="hero-badge"
            initial={false}
            animate={
              enabled ? { opacity: [0, 1], y: [15, 0] } : { opacity: 1, y: 0 }
            }
            transition={{ duration: enabled ? 0.7 : 0 }}
          >
            <span>{pageCopy.hero.badge}</span>
            {pageCopy.hero.badgeText}
          </motion.div>
          <h1>
            {pageCopy.hero.lines.map((line, i) => (
              <span className="hero-line-mask" key={line}>
                <motion.span
                  className={i === 1 ? "accent-text" : ""}
                  initial={false}
                  animate={
                    enabled
                      ? {
                          y: ["110%", "0%"],
                          rotate: [3, 0],
                          filter: ["blur(10px)", "blur(0px)"],
                        }
                      : { y: "0%", rotate: 0, filter: "blur(0px)" }
                  }
                  transition={{
                    duration: enabled ? 1 : 0,
                    delay: enabled ? [0.15, 0.32, 0.5][i] : 0,
                    ease,
                  }}
                >
                  {line}
                </motion.span>
              </span>
            ))}
          </h1>
          <motion.p
            className="hero-lead"
            initial={false}
            animate={
              enabled ? { opacity: [0, 1], y: [25, 0] } : { opacity: 1, y: 0 }
            }
            transition={{
              duration: enabled ? 0.8 : 0,
              delay: enabled ? 0.7 : 0,
              ease,
            }}
          >
            {pageCopy.hero.lead}
          </motion.p>
          <motion.div
            className="hero-pillars"
            initial={false}
            animate={
              enabled ? { opacity: [0, 1], y: [20, 0] } : { opacity: 1, y: 0 }
            }
            transition={{
              duration: enabled ? 0.8 : 0,
              delay: enabled ? 0.9 : 0,
              ease,
            }}
          >
            {[Box, PlugZap, Workflow].map((Icon, i) => (
              <span key={i}>
                <Icon size={16} />
                {pageCopy.hero.pillars[i]}
              </span>
            ))}
          </motion.div>
          <motion.div
            className="hero-buttons"
            initial={false}
            animate={
              enabled ? { opacity: [0, 1], y: [20, 0] } : { opacity: 1, y: 0 }
            }
            transition={{
              duration: enabled ? 0.8 : 0,
              delay: enabled ? 1.1 : 0,
              ease,
            }}
          >
            <MagneticButton href="/register">
              {pageCopy.hero.primary}
              <ArrowRight size={18} />
            </MagneticButton>
            <a className="button button-ghost" href="#demo">
              <span className="play-ring">
                <Play size={14} fill="currentColor" />
              </span>
              {pageCopy.hero.secondary}
            </a>
          </motion.div>
        </div>
        <div
          className="hero-visual"
          onPointerMove={(event) => {
            if (!enabled || event.pointerType !== "mouse") return;
            const r = event.currentTarget.getBoundingClientRect();
            mx.set((event.clientX - r.left) / r.width - 0.5);
            my.set((event.clientY - r.top) / r.height - 0.5);
            event.currentTarget.style.setProperty(
              "--cursor-x",
              `${event.clientX - r.left}px`,
            );
            event.currentTarget.style.setProperty(
              "--cursor-y",
              `${event.clientY - r.top}px`,
            );
          }}
          onPointerLeave={() => {
            mx.set(0);
            my.set(0);
          }}
        >
          <div className="hero-spotlight" aria-hidden="true" />
          <div className="hero-orbit orbit-cyan" aria-hidden="true">
            <i />
          </div>
          <div className="hero-orbit orbit-orange" aria-hidden="true">
            <i />
          </div>
          <motion.div
            className="hero-frame gradient-border"
            style={{ x: enabled ? fx : 0, y: enabled ? fy : 0 }}
          >
            <motion.div
              className="hero-picture"
              style={{ x: enabled ? ix : 0, y: enabled ? iy : 0 }}
            >
              <Image
                src="/landing-assets/images/hero-squad-768.webp"
                alt="Năm mascot VAgents cùng đứng trên nền tảng chữ V: chăm sóc khách hàng, điều phối, kỹ sư, phân tích và dữ liệu"
                width={1254}
                height={1254}
                sizes="(max-width: 900px) 94vw, 52vw"
                fetchPriority="high"
                loading="eager"
              />
            </motion.div>
          </motion.div>
          <motion.div
            className="hero-chips"
            role="group"
            style={{ x: enabled ? cx : 0, y: enabled ? cy : 0 }}
            aria-label="Ví dụ hoạt động của Agent"
          >
            <div className="floating-chip chip-order">
              <span className="chip-icon success-icon">
                <Check size={18} />
              </span>
              <div>
                <strong>{pageCopy.hero.chips[0].title}</strong>
                <small>
                  <i className="live-dot" />
                  {pageCopy.hero.chips[0].detail}
                </small>
              </div>
            </div>
            <div className="floating-chip chip-chat">
              <span className="chip-icon orange-icon">
                <MessageCircle size={18} />
              </span>
              <div>
                <strong>{pageCopy.hero.chips[1].title}</strong>
                <small>{pageCopy.hero.chips[1].detail}</small>
              </div>
            </div>
            <div className="floating-chip chip-report">
              <span className="chip-icon blue-icon">
                <ChartNoAxesCombined size={18} />
              </span>
              <div>
                <strong>{pageCopy.hero.chips[2].title}</strong>
                <small>{pageCopy.hero.chips[2].detail}</small>
              </div>
            </div>
          </motion.div>
          <span className="hero-visual-caption">
            {pageCopy.hero.illustration}
          </span>
        </div>
      </div>
      <div className="hero-grid-floor" aria-hidden="true" />
      <a className="scroll-hint" href="#how">
        <span>
          <i />
        </span>
        {pageCopy.hero.scroll}
      </a>
    </section>
  );
}
