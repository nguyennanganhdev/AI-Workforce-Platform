"use client";
import { useEffect, useRef, useState } from "react";
import Image from "../ui/AssetImage";
import { ArrowRight } from "lucide-react";
import Reveal from "../ui/Reveal";
import MagneticButton from "../ui/MagneticButton";
import Confetti from "../ui/Confetti";
import { useMotionSettings } from "../../lib/motion";
import { pageCopy } from "../../lib/content";

export default function FinalCTA() {
  const [burst, setBurst] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { enabled } = useMotionSettings();
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  return (
    <section
      id="cta"
      className="section final-cta-section"
      data-animated-section
    >
      <div className="container">
        <Reveal className="final-panel">
          <div className="cta-beams" aria-hidden="true">
            {[-58, -35, -12, 12, 35, 58].map((angle, i) => (
              <i
                key={angle}
                style={{
                  transform: `rotate(${angle}deg)`,
                  animationDelay: `${i * -0.7}s`,
                }}
              />
            ))}
          </div>
          <div className="final-copy">
            <span className="eyebrow">{pageCopy.cta.eyebrow}</span>
            <h2>
              {pageCopy.cta.heading[0]}
              <br />
              <span className="accent-text">{pageCopy.cta.heading[1]}</span>
            </h2>
            <p>{pageCopy.cta.lead}</p>
            <div className="confetti-anchor">
              <MagneticButton
                href="/register"
                onClick={(event) => {
                  if (
                    event.metaKey ||
                    event.ctrlKey ||
                    event.shiftKey ||
                    !enabled
                  )
                    return;
                  event.preventDefault();
                  if (timer.current) return;
                  setBurst(true);
                  timer.current = setTimeout(() => {
                    window.location.assign("/register");
                  }, 1100);
                }}
              >
                {pageCopy.start}
                <ArrowRight size={20} />
              </MagneticButton>
              <Confetti active={burst} />
            </div>
            <a href="#contact" className="cta-secondary">
              {pageCopy.cta.secondary}
            </a>
          </div>
          <div className="cta-mascots">
            {pageCopy.mascotImages.map((image, i) => (
              <Image
                key={image}
                src={`/landing-assets/images/${image.replace(".webp", "-240.webp")}`}
                alt={pageCopy.mascotNames[i]}
                width={170}
                height={170}
                sizes="(max-width: 600px) 18vw, 150px"
                className={`cta-mascot cta-mascot-${i}`}
              />
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
