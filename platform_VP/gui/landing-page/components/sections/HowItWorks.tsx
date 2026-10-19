import { useEffect, useRef } from "react";
import { Bot, Cable, Workflow } from "lucide-react";
import { useInView } from "framer-motion";
import Reveal from "../ui/Reveal";
import { content } from "../../lib/content";
import { useMotionSettings } from "../../lib/motion";

const icons = [Bot, Cable, Workflow];

export default function HowItWorks() {
  const ref = useRef<HTMLElement>(null);
  const played = useRef(false);
  const near = useInView(ref, { margin: "200px 0px", once: true });
  const { enabled } = useMotionSettings();

  useEffect(() => {
    if (
      !ref.current ||
      !enabled ||
      !near ||
      played.current ||
      !window.matchMedia("(min-width: 901px)").matches
    )
      return;
    let cancelled = false;
    let revert: (() => void) | undefined;
    void Promise.all([import("gsap"), import("gsap/ScrollTrigger")]).then(
      ([{ gsap }, { ScrollTrigger }]) => {
        if (cancelled) return;
        gsap.registerPlugin(ScrollTrigger);
        const ctx = gsap.context(() => {
          const timeline = gsap.timeline({
            scrollTrigger: {
              trigger: ref.current,
              start: "top 75%",
              once: true,
              onEnter: () => {
                played.current = true;
              },
            },
          });
          timeline.fromTo(
            ".steps-track-fill",
            { scaleX: 0 },
            { scaleX: 1, duration: 2.2, ease: "power2.inOut" },
            0,
          );
          timeline.fromTo(
            ".step-card",
            { y: 30, scale: 0.96, opacity: 0 },
            {
              y: 0,
              scale: 1,
              opacity: 1,
              duration: 0.7,
              stagger: 0.7,
              ease: "power3.out",
            },
            0.3,
          );
        }, ref);
        revert = () => ctx.revert();
      },
    );
    return () => {
      cancelled = true;
      revert?.();
    };
  }, [enabled, near]);

  return (
    <section
      id="how"
      ref={ref}
      className="section how-section"
      aria-labelledby="how-title"
      data-animated-section
    >
      <div className="container">
        <Reveal className="section-heading">
          <span className="eyebrow">{content.how.eyebrow}</span>
          <h2 id="how-title">
            {content.how.title}
            <br />
            <span className="accent-text">{content.how.accent}</span>
          </h2>
        </Reveal>
        <div className="steps-grid">
          <div className="steps-track" aria-hidden="true">
            <div className="steps-track-fill" />
            <span className="steps-travel-dot" />
          </div>
          {content.how.steps.map((step, index) => {
            const Icon = icons[index];
            return (
              <article className="step-card" key={step.number}>
                <div className="step-icon">
                  <Icon size={34} strokeWidth={1.8} aria-hidden="true" />
                  <span className="step-number">{step.number}</span>
                </div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
