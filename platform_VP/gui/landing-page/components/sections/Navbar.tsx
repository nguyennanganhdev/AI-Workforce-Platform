"use client";
import { useEffect, useState } from "react";
import Image from "../ui/AssetImage";
import { ArrowUpRight, Menu, X } from "lucide-react";
import {
  AnimatePresence,
  m as motion,
  useMotionValueEvent,
  useScroll,
} from "framer-motion";
import { useMotionSettings } from "../../lib/motion";
import { pageCopy } from "../../lib/content";

export default function Navbar() {
  const [open, setOpen] = useState(false),
    [scrolled, setScrolled] = useState(false);
  const { scrollY } = useScroll();
  const { enabled } = useMotionSettings();
  useMotionValueEvent(scrollY, "change", (value) => setScrolled(value > 30));
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        document.getElementById("menu-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [open]);
  return (
    <header className={`site-header ${scrolled ? "scrolled" : ""}`}>
      <div className="container nav-inner">
        <a href="/" className="brand" aria-label="VAgents - Trang chủ">
          <Image
            src="/landing-assets/images/logo.png"
            alt=""
            width={36}
            height={36}
          />
          <span>{pageCopy.brand}</span>
        </a>
        <nav className="desktop-nav" aria-label="Điều hướng chính">
          {pageCopy.nav.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
        </nav>
        <div className="nav-actions">
          <a href="/login" className="nav-auth nav-login">
            {pageCopy.auth.login}
          </a>
          <a href="/register" className="nav-auth nav-register">
            {pageCopy.auth.register}
          </a>
          <button
            id="menu-toggle"
            className="icon-button mobile-menu-toggle"
            aria-controls="mobile-nav"
            aria-expanded={open}
            aria-label={open ? "Đóng menu" : "Mở menu"}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? <X /> : <Menu />}
          </button>
        </div>
      </div>
      <AnimatePresence>
        {open && (
          <motion.nav
            id="mobile-nav"
            className="mobile-nav"
            aria-label="Điều hướng di động"
            initial={enabled ? { opacity: 0, y: -15 } : false}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25 }}
          >
            {pageCopy.nav.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
              >
                {item.label}
                <ArrowUpRight size={17} />
              </a>
            ))}
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
