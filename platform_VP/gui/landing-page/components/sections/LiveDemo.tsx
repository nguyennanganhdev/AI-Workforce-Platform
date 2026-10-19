"use client";
import { useEffect, useRef, useState } from "react";
import Image from "../ui/AssetImage";
import { AnimatePresence, m as motion, useInView } from "framer-motion";
import {
  Check,
  CheckCheck,
  RotateCcw,
  Terminal,
  Play,
  Pause,
} from "lucide-react";
import Reveal from "../ui/Reveal";
import { useMotionSettings } from "../../lib/motion";
import { pageCopy } from "../../lib/content";

export default function LiveDemo() {
  const section = useRef<HTMLElement>(null);
  const visible = useInView(section, { amount: 0.2 });
  const { enabled } = useMotionSettings();
  const [characters, setCharacters] = useState(0),
    [step, setStep] = useState(0),
    [running, setRunning] = useState(true),
    [cycle, setCycle] = useState(0);
  const prompt = pageCopy.demo.prompt;
  const finishedTyping = characters >= prompt.length;
  useEffect(() => {
    if (!visible || !enabled || !running) return;
    if (characters < prompt.length) {
      const timer = setTimeout(() => setCharacters((v) => v + 1), 34);
      return () => clearTimeout(timer);
    }
    if (step < 5) {
      const timer = setTimeout(() => setStep((v) => v + 1), 1100);
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => {
      setCharacters(0);
      setStep(0);
      setCycle((v) => v + 1);
    }, 4000);
    return () => clearTimeout(timer);
  }, [visible, enabled, running, characters, step, prompt.length, cycle]);
  // Static final state preserves the full example for reduced motion and pauses.
  const displayStep = enabled ? step : 5;
  const displayPrompt = enabled ? prompt.slice(0, characters) : prompt;
  const status =
    displayStep === 5
      ? pageCopy.demo.statuses[2]
      : finishedTyping
        ? pageCopy.demo.statuses[1]
        : pageCopy.demo.statuses[0];
  const restart = () => {
    setCharacters(0);
    setStep(0);
    setRunning(true);
    setCycle((v) => v + 1);
  };
  return (
    <section
      id="demo"
      className="section demo-section"
      ref={section}
      data-animated-section
    >
      <div className="container">
        <Reveal className="section-heading centered">
          <span className="eyebrow">{pageCopy.demo.eyebrow}</span>
          <h2>
            {pageCopy.demo.heading[0]}
            <br />
            <span className="blue-text">{pageCopy.demo.heading[1]}</span>
          </h2>
          <p className="demo-disclaimer">{pageCopy.demo.disclaimer}</p>
        </Reveal>
        <div className="demo-layout">
          <Reveal className="demo-console">
            <div className="console-titlebar">
              <div className="traffic-lights" aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
              <span>{pageCopy.demo.windowTitle}</span>
              <Terminal size={16} />
            </div>
            <div className="console-body">
              <div className="console-prompt">
                <span className="prompt-arrow" aria-hidden="true">
                  ›
                </span>
                <p>
                  <span className="sr-only">{prompt}</span>
                  <span aria-hidden="true">
                    {displayPrompt}
                    <span className="typing-caret" />
                  </span>
                </p>
              </div>
              <div
                className="demo-messages"
                role="log"
                aria-live="polite"
                aria-atomic="false"
                aria-label="Kết quả mô phỏng từng Agent"
              >
                <AnimatePresence initial={false}>
                  {pageCopy.demo.messages
                    .slice(0, displayStep)
                    .map((message, i) => (
                      <motion.div
                        className="agent-message"
                        key={`${cycle}-${i}`}
                        initial={
                          enabled
                            ? { opacity: 0, y: 16, filter: "blur(5px)" }
                            : false
                        }
                        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                        transition={{ duration: 0.45 }}
                      >
                        <span className="message-avatar">
                          <Image
                            src={`/landing-assets/images/${message.image}`}
                            width={44}
                            height={44}
                            alt=""
                          />
                        </span>
                        <div>
                          <strong>{message.agent}</strong>
                          <p>{message.text}</p>
                        </div>
                        <Check size={17} className="message-check" />
                      </motion.div>
                    ))}
                </AnimatePresence>
              </div>
            </div>
            <div className="console-status">
              <span>
                <i className="live-dot" />
                {status}
              </span>
              <span>{displayStep}/5 bước</span>
            </div>
          </Reveal>
          <Reveal className="workflow-panel" delay={0.15}>
            <div className="workflow-panel-heading">
              <CheckCheck size={23} />
              <h3>{pageCopy.demo.flowTitle}</h3>
              <button
                className="icon-button"
                aria-label={running ? "Tạm dừng demo" : "Tiếp tục demo"}
                onClick={() => setRunning((v) => !v)}
                disabled={!enabled}
              >
                {running ? <Pause size={17} /> : <Play size={17} />}
              </button>
            </div>
            <ol className="workflow-nodes">
              {pageCopy.demo.nodes.map((node, i) => (
                <li key={node} className={i < displayStep ? "is-complete" : ""}>
                  <span className="workflow-number">
                    {i < displayStep ? <Check size={16} /> : i + 1}
                  </span>
                  <span>{node}</span>
                  {i < 4 && <i className="workflow-drip" aria-hidden="true" />}
                </li>
              ))}
            </ol>
            <button className="button button-replay" onClick={restart}>
              <RotateCcw size={17} />
              {pageCopy.demo.replay}
            </button>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
