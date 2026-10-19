import Image from "../ui/AssetImage";
import {
  Headphones,
  TrendingUp,
  UsersRound,
  ReceiptText,
  PackageCheck,
  Megaphone,
  ArrowUpRight,
} from "lucide-react";
import Reveal from "../ui/Reveal";
import { content } from "../../lib/content";

const icons = [
  Headphones,
  TrendingUp,
  UsersRound,
  ReceiptText,
  PackageCheck,
  Megaphone,
];

export default function UseCases() {
  return (
    <section
      className="section use-cases-section"
      aria-labelledby="use-cases-title"
      data-animated-section
    >
      <div className="container">
        <Reveal className="section-heading">
          <span className="eyebrow">{content.useCases.eyebrow}</span>
          <h2 id="use-cases-title">
            {content.useCases.title}
            <br />
            <span className="accent-text">{content.useCases.accent}</span>
          </h2>
        </Reveal>
        <div className="bento-grid">
          <Reveal className="bento-featured">
            <article>
              <Image
                src="/landing-assets/images/team-journey-contained.webp"
                width={900}
                height={900}
                alt={content.useCases.imageAlt}
                sizes="(max-width: 600px) 92vw, (max-width: 900px) 60vw, 580px"
              />
              <div className="bento-featured-overlay" />
              <div className="bento-featured-copy">
                <span className="bento-featured-arrow" aria-hidden="true">
                  <ArrowUpRight strokeWidth={1.8} size={25} />
                </span>
                <h3>{content.useCases.featuredTitle}</h3>
                <p>{content.useCases.featuredText}</p>
              </div>
            </article>
          </Reveal>
          {content.useCases.items.map((item, index) => {
            const Icon = icons[index];
            return (
              <Reveal
                className="bento-small"
                delay={index * 0.06}
                key={item.title}
              >
                <article>
                  <span className="bento-corner-glow" aria-hidden="true" />
                  <Icon size={30} strokeWidth={1.8} aria-hidden="true" />
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                  </div>
                </article>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
