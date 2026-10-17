import type { CSSProperties } from "react";
import {
  MessageCircle,
  Mail,
  Sheet,
  Wallet,
  Database,
  FileText,
  CalendarDays,
  ChartNoAxesCombined,
  ShoppingCart,
  Cloud,
  UsersRound,
  Megaphone,
  MessagesSquare,
  FolderSync,
  Boxes,
} from "lucide-react";
import Image from "../ui/AssetImage";
import Reveal from "../ui/Reveal";
import { content } from "../../lib/content";

const nodeIcons = [
  MessageCircle,
  Mail,
  Sheet,
  Wallet,
  Database,
  FileText,
  CalendarDays,
  ChartNoAxesCombined,
  ShoppingCart,
  Cloud,
  UsersRound,
  Megaphone,
];
const featureIcons = [MessagesSquare, FolderSync, Boxes];

export default function Integrations() {
  return (
    <section
      id="connect"
      className="section integrations-section"
      aria-labelledby="connect-title"
      data-animated-section
    >
      <div className="container integrations-grid">
        <Reveal className="orbit-wrap">
          <div
            className="integration-orbit"
            role="group"
            aria-label={content.integrations.visualLabel}
          >
            <div className="orbit-beams" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            {[0, 1, 2].map((ring) => (
              <div className={`orbit-track orbit-track-${ring + 1}`} key={ring}>
                {nodeIcons.slice(ring * 4, ring * 4 + 4).map((Icon, index) => {
                  const label = content.integrations.nodes[ring * 4 + index];
                  return (
                    <span
                      className="orbit-node-position"
                      style={
                        {
                          "--node-angle": `${index * 90 + ring * 25}deg`,
                        } as CSSProperties
                      }
                      key={label}
                    >
                      <span className="orbit-node-counter">
                        <span
                          className="orbit-node"
                          role="img"
                          tabIndex={0}
                          aria-label={label}
                        >
                          <Icon
                            size={24}
                            strokeWidth={1.8}
                            aria-hidden="true"
                          />
                          <span className="orbit-tooltip" aria-hidden="true">
                            {label}
                          </span>
                        </span>
                      </span>
                    </span>
                  );
                })}
              </div>
            ))}
            <div className="orbit-center">
              <Image
                src="/landing-assets/images/logo.png"
                width={64}
                height={64}
                alt="VAgents"
              />
              <span className="orbit-center-ring" aria-hidden="true" />
            </div>
          </div>
        </Reveal>
        <Reveal className="integrations-copy">
          <span className="eyebrow">{content.integrations.eyebrow}</span>
          <h2 id="connect-title">
            {content.integrations.title}
            <br />
            <span className="accent-text">{content.integrations.accent}</span>
          </h2>
          <p className="section-lead">{content.integrations.lead}</p>
          <div className="integration-features">
            {content.integrations.features.map((feature, index) => {
              const Icon = featureIcons[index];
              return (
                <div className="integration-feature" key={feature.title}>
                  <span className="feature-icon">
                    <Icon size={24} strokeWidth={1.8} aria-hidden="true" />
                  </span>
                  <div>
                    <h3>{feature.title}</h3>
                    <p>{feature.description}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
