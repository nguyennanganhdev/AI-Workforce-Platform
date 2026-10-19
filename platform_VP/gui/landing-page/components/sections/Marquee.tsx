import {
  Headphones,
  ShoppingBag,
  ChartNoAxesCombined,
  Mail,
  CalendarDays,
  RefreshCw,
  UsersRound,
  ReceiptText,
} from "lucide-react";
import { content } from "../../lib/content";

const icons = [
  Headphones,
  ShoppingBag,
  ChartNoAxesCombined,
  Mail,
  CalendarDays,
  RefreshCw,
  UsersRound,
  ReceiptText,
];

export default function Marquee() {
  return (
    <section
      className="marquee-section"
      aria-label="Khả năng của đội ngũ agent"
      data-animated-section
    >
      <div className="marquee-track">
        {[0, 1].map((copy) => (
          <div
            className="marquee-group"
            key={copy}
            aria-hidden={copy === 1 ? true : undefined}
          >
            {content.marquee.map((label, index) => {
              const Icon = icons[index];
              return (
                <span className="marquee-item" key={label}>
                  <Icon size={19} strokeWidth={1.8} aria-hidden="true" />
                  {label}
                  <span className="marquee-separator" aria-hidden="true" />
                </span>
              );
            })}
          </div>
        ))}
      </div>
    </section>
  );
}
