import Counter from "../ui/Counter";
import Reveal from "../ui/Reveal";
import { content } from "../../lib/content";

export default function Stats() {
  return (
    <section
      className="stats-section"
      aria-label="VAgents qua những con số"
      data-animated-section
    >
      <div className="container stats-grid">
        {content.stats.map((stat, index) => (
          <Reveal className="stat-card" delay={index * 0.1} key={stat.label}>
            <div className="stat-value">
              {stat.placeholder || (
                <Counter value={stat.value} suffix={stat.suffix} />
              )}
            </div>
            <p>{stat.label}</p>
            <span className="stat-underline" aria-hidden="true" />
          </Reveal>
        ))}
      </div>
    </section>
  );
}
