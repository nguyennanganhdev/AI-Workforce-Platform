import { useState } from "react";
import { m as motion } from "framer-motion";
import { Plus } from "lucide-react";
import Reveal from "../ui/Reveal";
import { content } from "../../lib/content";
import { useMotionSettings } from "../../lib/motion";

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const { enabled } = useMotionSettings();
  return (
    <section
      id="faq"
      className="section faq-section"
      aria-labelledby="faq-title"
    >
      <div className="container faq-grid">
        <Reveal className="section-heading">
          <span className="eyebrow">{content.faq.eyebrow}</span>
          <h2 id="faq-title">
            {content.faq.title}
            <br />
            <span className="accent-text">{content.faq.accent}</span>
          </h2>
        </Reveal>
        <div className="faq-list">
          {content.faq.items.map((item, index) => (
            <Reveal delay={index * 0.05} key={item.question}>
              <article
                className={`faq-item${open === index ? " is-open" : ""}`}
              >
                <h3>
                  <button
                    type="button"
                    id={`faq-question-${index}`}
                    aria-expanded={open === index}
                    aria-controls={`faq-answer-${index}`}
                    onClick={() =>
                      setOpen((current) => (current === index ? null : index))
                    }
                  >
                    {item.question}
                    <motion.span
                      animate={{ rotate: open === index ? 135 : 0 }}
                      transition={
                        enabled
                          ? { type: "spring", stiffness: 300, damping: 20 }
                          : { duration: 0 }
                      }
                    >
                      <Plus size={21} strokeWidth={1.8} aria-hidden="true" />
                    </motion.span>
                  </button>
                </h3>
                <div
                  className="faq-answer-grid"
                  id={`faq-answer-${index}`}
                  role="region"
                  aria-labelledby={`faq-question-${index}`}
                  aria-hidden={open !== index}
                >
                  <div>
                    <p>{item.answer}</p>
                  </div>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
