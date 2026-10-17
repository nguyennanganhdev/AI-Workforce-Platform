"use client";
import Image from "../ui/AssetImage";
import { useState } from "react";
import { ArrowUpRight, ArrowRight, Pause, Play } from "lucide-react";
import { pageCopy } from "../../lib/content";
import { useMotionSettings } from "../../lib/motion";

export default function Footer() {
  const [email, setEmail] = useState(""),
    [status, setStatus] = useState("");
  const { enabled, toggle } = useMotionSettings();
  return (
    <footer id="contact" className="site-footer">
      <div className="container footer-grid">
        <div className="footer-brand-block">
          <a className="brand" href="/" aria-label="VAgents - Trang chủ">
            <Image
              src="/landing-assets/images/logo.png"
              width={36}
              height={36}
              alt=""
            />
            <span>{pageCopy.brand}</span>
          </a>
          <p>{pageCopy.footer.tagline}</p>
          <form
            className="newsletter"
            onSubmit={(event) => {
              event.preventDefault();
              setStatus(pageCopy.footer.newsletterPending);
            }}
          >
            <label htmlFor="newsletter-email">
              {pageCopy.footer.newsletterLabel}
            </label>
            <div>
              <input
                id="newsletter-email"
                name="email"
                autoComplete="email"
                type="email"
                required
                placeholder="ban@congty.vn"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setStatus("");
                }}
              />
              <button type="submit" aria-label="Đăng ký nhận tin">
                <span>{pageCopy.footer.subscribe}</span>
                <ArrowRight size={17} />
              </button>
            </div>
            <p className="newsletter-help">{pageCopy.footer.newsletterHelp}</p>
            <p className="form-status" role="status">
              {status}
            </p>
          </form>
        </div>
        {pageCopy.footer.columns.map((column) => (
          <div className="footer-column" key={column.title}>
            <h3>{column.title}</h3>
            {column.items.map((item) =>
              item.href ? (
                <a href={item.href} key={item.label}>
                  {item.label}
                  <ArrowUpRight size={13} />
                </a>
              ) : (
                <span className="placeholder-text" key={item.label}>
                  {item.label}
                </span>
              ),
            )}
          </div>
        ))}
      </div>
      <div className="container footer-wordmark" aria-hidden="true">
        {pageCopy.brand}
      </div>
      <div className="container footer-bottom">
        <span>{pageCopy.footer.copyright}</span>
        <div>
          <button
            className="motion-toggle"
            onClick={toggle}
            aria-pressed={!enabled}
          >
            {enabled ? <Pause size={16} /> : <Play size={16} />}
            {enabled ? pageCopy.motion.pause : pageCopy.motion.play}
          </button>
          <details className="policy-disclosure">
            <summary>{pageCopy.footer.termsLabel}</summary>
            <p>{pageCopy.footer.terms}</p>
          </details>
          <details className="policy-disclosure">
            <summary>{pageCopy.footer.privacyLabel}</summary>
            <p>{pageCopy.footer.privacy}</p>
          </details>
        </div>
      </div>
    </footer>
  );
}
