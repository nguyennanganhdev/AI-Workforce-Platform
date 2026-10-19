import Navbar from "../components/sections/Navbar";
import Hero from "../components/sections/Hero";
import Marquee from "../components/sections/Marquee";
import HowItWorks from "../components/sections/HowItWorks";
import Team from "../components/sections/Team";
import LiveDemo from "../components/sections/LiveDemo";
import Integrations from "../components/sections/Integrations";
import UseCases from "../components/sections/UseCases";
import Stats from "../components/sections/Stats";
import FAQ from "../components/sections/FAQ";
import FinalCTA from "../components/sections/FinalCTA";
import Footer from "../components/sections/Footer";
import ScrollProgress from "../components/ui/ScrollProgress";

export default function App() {
  return (
    <>
      <a href="#main" className="skip-link">
        Đến nội dung chính
      </a>
      <ScrollProgress />
      <Navbar />
      <main id="main">
        <Hero />
        <Marquee />
        <HowItWorks />
        <Team />
        <LiveDemo />
        <Integrations />
        <UseCases />
        <Stats />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
