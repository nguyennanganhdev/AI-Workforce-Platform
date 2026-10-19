import Image from "../ui/AssetImage";
import Reveal from "../ui/Reveal";
import TiltCard from "../ui/TiltCard";
import { content } from "../../lib/content";

export default function Team() {
  return (
    <section
      id="team"
      className="section team-section"
      aria-labelledby="team-title"
      data-animated-section
    >
      <div className="container">
        <Reveal className="section-heading section-heading-split">
          <div>
            <span className="eyebrow">{content.team.eyebrow}</span>
            <h2 id="team-title">
              {content.team.title}
              <br />
              <span className="accent-text">{content.team.accent}</span>
            </h2>
          </div>
          <p className="section-lead">{content.team.lead}</p>
        </Reveal>
        <div className="team-grid">
          {content.team.members.map((member, index) => (
            <Reveal delay={index * 0.1} key={member.id}>
              <TiltCard
                className={`team-card${member.badge ? " team-card-featured" : ""}`}
              >
                <article>
                  <div className="team-image-wrap">
                    <span className="team-halo" aria-hidden="true" />
                    {member.badge && (
                      <span className="team-leader-badge">{member.badge}</span>
                    )}
                    <Image
                      src={`/landing-assets/images/agent-${member.id}-480.webp`}
                      width={400}
                      height={400}
                      alt={member.alt}
                      className="team-image"
                      sizes="(max-width: 600px) 44vw, (max-width: 1100px) 28vw, 220px"
                    />
                  </div>
                  <div className="team-card-copy">
                    <span className="team-role">{member.role}</span>
                    <h3>{member.name}</h3>
                    <p>{member.description}</p>
                    <ul
                      className="agent-tags"
                      aria-label={`Chuyên môn ${member.name}`}
                    >
                      {member.tags.map((tag) => (
                        <li key={tag}>{tag}</li>
                      ))}
                    </ul>
                  </div>
                </article>
              </TiltCard>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
