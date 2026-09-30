import { useState, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { motion, useReducedMotion } from 'motion/react';
import {
  IconBellRinging,
  IconBrush,
  IconChecklist,
  IconMessageChatbot,
  IconPlus,
  IconShieldCheck,
  IconSignature,
  IconTool,
  IconUserCheck,
  IconUsersGroup,
} from '@tabler/icons-react';
import { cn } from '@/lib/utils';
import { TicketCard } from '@/features/vinhomes-resident/components/ticket-ui';
import type { ResidentTicketView } from '@/features/vinhomes-resident/types';
import heroPhoto from '../assets/ocean-park-dusk.jpg';
import { destinationFor, roleLabel } from '../auth/accounts';
import { getSession } from '../auth/session';
import { PORTAL_FONT, Wordmark, accentButton, accentText, glassButton } from './brand';

const EASE = [0.16, 1, 0.3, 1] as const;

/** Fades a block up once when it scrolls into view; static under reduced motion. */
function Reveal({ children, delay = 0, className, as = 'div' }: { children: ReactNode; delay?: number; className?: string; as?: 'div' | 'li' }) {
  const reduce = useReducedMotion();
  const Tag = as === 'li' ? motion.li : motion.div;
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.7, delay, ease: EASE }}
    >
      {children}
    </Tag>
  );
}

function usePrimaryAction() {
  const [session] = useState(getSession);
  return session
    ? { label: 'Vào ứng dụng', to: destinationFor(session), who: `${session.name} (${roleLabel(session)})` }
    : { label: 'Đăng nhập', to: '/vinhomes/login' as const, who: null };
}

// ---------------------------------------------------------------------------------------------------

function Hero() {
  const reduce = useReducedMotion();
  const primary = usePrimaryAction();
  const enter = (i: number) =>
    reduce
      ? {}
      : { initial: { opacity: 0, y: 18 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.8, delay: 0.25 + i * 0.09, ease: EASE } };

  return (
    <section className="relative isolate flex min-h-[100dvh] flex-col overflow-hidden bg-zinc-950 text-white">
      <motion.img
        src={heroPhoto}
        alt="Toàn cảnh khu đô thị Vinhomes Ocean Park lúc hoàng hôn, nhìn từ trên cao"
        fetchPriority="high"
        className="absolute inset-0 -z-20 size-full object-cover object-[62%_center]"
        initial={reduce ? false : { scale: 1.08 }}
        animate={{ scale: 1 }}
        transition={{ duration: 2.4, ease: EASE }}
      />
      {/* Scrims: left for the copy, bottom for the CTAs. */}
      <div className="absolute inset-0 -z-10 bg-gradient-to-r from-zinc-950/75 via-zinc-950/30 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 -z-10 h-1/2 bg-gradient-to-t from-zinc-950/80 to-transparent" />
      <div className="absolute inset-x-0 top-0 -z-10 h-32 bg-gradient-to-b from-zinc-950/50 to-transparent" />

      <header className="mx-auto flex h-18 w-full max-w-7xl items-center justify-between gap-6 px-4 sm:px-6">
        <Wordmark onPhoto />
        <nav aria-label="Mục trên trang" className="hidden items-center gap-7 text-sm text-white/80 md:flex">
          <a href="#hanh-trinh" className="hover:text-white">Hành trình</a>
          <a href="#cu-dan" className="hover:text-white">Cư dân</a>
          <a href="#nhan-vien" className="hover:text-white">Nhân viên</a>
          <a href="#hoi-dap" className="hover:text-white">Hỏi đáp</a>
        </nav>
        <Link to={primary.to} className={cn(glassButton, 'h-10 px-5 text-sm')}>
          {primary.label}
        </Link>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-1 items-end px-4 pt-16 pb-16 sm:px-6 md:pb-24">
        <div className="max-w-3xl">
          <motion.p {...enter(0)} className="mb-5 text-xs font-medium uppercase tracking-[0.18em] text-teal-200">
            Cổng cư dân và vận hành Vinhomes
          </motion.p>
          <motion.h1 {...enter(1)} className="text-4xl leading-[1.08] font-semibold tracking-tight text-balance md:text-5xl lg:text-6xl">
            Báo sự cố một lần, theo dõi đến khi xong.
          </motion.h1>
          <motion.p {...enter(2)} className="mt-5 max-w-xl text-base leading-relaxed text-white/80 md:text-lg">
            Nhắn cho trợ lý, Ban quản lý giao việc ngay, nhân viên xử lý và bạn xác nhận kết quả trên điện thoại.
          </motion.p>
          <motion.div {...enter(3)} className="mt-8 flex flex-wrap gap-3">
            <Link to={primary.to} className={accentButton}>
              {primary.label}
            </Link>
            <Link to="/vinhomes/register" className={glassButton}>
              Đăng ký cư dân
            </Link>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------

const JOURNEY = [
  { icon: IconMessageChatbot, title: 'Nhắn cho trợ lý', body: 'Mô tả sự cố, gửi ảnh. Trợ lý hỏi thêm vị trí rồi tạo yêu cầu cho bạn.' },
  { icon: IconUserCheck, title: 'Ban quản lý xác nhận', body: 'Yêu cầu tới đúng Ban quản lý tòa của bạn và được giao cho nhân viên phù hợp.' },
  { icon: IconTool, title: 'Nhân viên xử lý', body: 'Bạn được báo khi nhân viên nhận việc, đến nơi và gửi danh mục sửa chữa.' },
  { icon: IconSignature, title: 'Bạn xác nhận', body: 'Xem ảnh kết quả, ký xác nhận hoặc báo chưa đạt ngay trên điện thoại.' },
];

function Journey() {
  return (
    <section id="hanh-trinh" className="scroll-mt-8 bg-background py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-balance md:text-4xl">Luôn biết yêu cầu đang ở bước nào</h2>
        </Reveal>
        <ol className="relative mt-14 grid gap-10 md:grid-cols-4 md:gap-8">
          {/* Connector across the four steps on desktop. */}
          <span aria-hidden className="absolute top-6 right-[calc(25%-3rem)] left-6 hidden h-px bg-border md:block" />
          {JOURNEY.map(({ icon: Icon, title, body }, i) => (
            <Reveal key={title} as="li" delay={i * 0.08} className="relative flex gap-4 md:flex-col md:gap-5">
                <span className="relative flex size-12 shrink-0 items-center justify-center rounded-2xl border bg-background">
                  <Icon className={cn('size-6', accentText)} stroke={1.5} />
                </span>
                <div>
                  <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
                  <p className="mt-2 max-w-[32ch] text-[15px] leading-relaxed text-muted-foreground">{body}</p>
                </div>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------

const quote = (total: number) => ({
  lines: [],
  agreedLines: [],
  additionalLines: [],
  laborCost: 0,
  total,
  warrantyMonths: 3,
  noCharge: false,
});

/** Sample data rendered through the real resident TicketCard component (not a mock-up). */
const SAMPLE_TICKETS: ResidentTicketView[] = [
  {
    caseId: 'sample-1',
    code: 'YC-4K7Q2M',
    title: 'Vòi nước dưới bồn rửa bếp bị rò rỉ',
    description: '',
    location: '',
    photos: [],
    status: 'waiting_you',
    statusLabel: 'Chờ bạn',
    tone: 'attention',
    detail: 'Xem danh mục sửa chữa và bấm đồng ý.',
    teamLabel: 'Đội kỹ thuật nước',
    assignee: null,
    pendingAction: { type: 'AGREE_QUOTE', woId: 'sample', version: 1, channel: 'APP', quote: quote(265000) },
    resolution: null,
    events: [],
    isOpen: true,
    createdAt: '',
    updatedAt: '',
  },
  {
    caseId: 'sample-2',
    code: 'YC-4K2B9T',
    title: 'Đèn hành lang tầng 12 nhấp nháy',
    description: '',
    location: '',
    photos: [],
    status: 'on_the_way',
    statusLabel: 'Nhân viên đang đến',
    tone: 'info',
    detail: 'Anh Hùng đang tới chỗ bạn.',
    teamLabel: 'Đội kỹ thuật điện',
    assignee: null,
    pendingAction: null,
    resolution: null,
    events: [],
    isOpen: true,
    createdAt: '',
    updatedAt: '',
  },
  {
    caseId: 'sample-3',
    code: 'YC-4JX81D',
    title: 'Sảnh tầng 1 sàn trơn sau mưa',
    description: '',
    location: '',
    photos: [],
    status: 'completed',
    statusLabel: 'Hoàn tất',
    tone: 'success',
    detail: 'Khu vực đã được làm sạch.',
    teamLabel: 'Đội vệ sinh',
    assignee: null,
    pendingAction: null,
    resolution: null,
    events: [],
    isOpen: false,
    createdAt: '',
    updatedAt: '',
  },
];

const RESIDENT_POINTS = [
  { icon: IconPlus, text: 'Mỗi cuộc trò chuyện theo dõi một yêu cầu, không lẫn với việc khác.' },
  { icon: IconChecklist, text: 'Duyệt danh mục sửa chữa và ký xác nhận ngay trên app, không cần chờ nhân viên đưa máy.' },
  { icon: IconBellRinging, text: 'Có tiến triển mới là trợ lý nhắn bạn trong đúng cuộc trò chuyện đó.' },
];

function ResidentSection() {
  return (
    <section id="cu-dan" className="scroll-mt-8 bg-muted/40 py-20 md:py-28">
      <div className="mx-auto grid max-w-7xl items-center gap-14 px-4 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-20">
        <Reveal>
          <h2 className="text-3xl font-semibold tracking-tight text-balance md:text-4xl">Trợ lý cư dân nằm gọn trong điện thoại</h2>
          <p className="mt-4 max-w-[52ch] text-base leading-relaxed text-muted-foreground md:text-lg">
            Hỏi nội quy, báo hỏng hóc hay xem tiến độ đều bắt đầu bằng một tin nhắn.
          </p>
          <ul className="mt-8 flex flex-col gap-5">
            {RESIDENT_POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3.5">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-teal-700/10 dark:bg-teal-300/15">
                  <Icon className={cn('size-5', accentText)} stroke={1.75} />
                </span>
                <p className="pt-1.5 text-[15px] leading-relaxed">{text}</p>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.1}>
          <figure className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-teal-50 via-background to-sky-50 p-5 sm:p-8 dark:from-teal-950/60 dark:via-background dark:to-sky-950/40">
            <p className="mb-4 text-sm font-medium">Yêu cầu của tôi</p>
            {/* Real TicketCard components with sample data; presentational only here. */}
            <div inert aria-hidden className="flex flex-col gap-3">
              {SAMPLE_TICKETS.map((t, i) => (
                <div key={t.caseId} className={cn(i === 1 && 'sm:ml-6', i === 2 && 'opacity-80 sm:ml-12')}>
                  <TicketCard ticket={t} onOpen={() => {}} />
                </div>
              ))}
            </div>
            <figcaption className="sr-only">Ví dụ danh sách yêu cầu trong app cư dân: một yêu cầu chờ bạn duyệt, một yêu cầu nhân viên đang đến, một yêu cầu đã hoàn tất.</figcaption>
          </figure>
        </Reveal>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------

function StaffSection() {
  return (
    <section id="nhan-vien" className="scroll-mt-8 bg-background py-20 md:py-28">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <Reveal>
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-balance md:text-4xl">Mỗi vai trò mở đúng màn hình của mình</h2>
          <p className="mt-4 max-w-[60ch] text-base leading-relaxed text-muted-foreground md:text-lg">
            Nhân viên đăng nhập bằng tài khoản do Ban quản lý cấp, hệ thống tự mở phần việc theo vai trò.
          </p>
        </Reveal>

        <div className="mt-12 grid gap-4 md:grid-cols-3 md:grid-rows-[repeat(2,minmax(15rem,auto))_auto]">
          {/* Ban quản lý: large photo tile. */}
          <Reveal className="md:col-span-2 md:row-span-2">
            <article className="group relative isolate flex h-full min-h-80 flex-col justify-end overflow-hidden rounded-2xl p-6 text-white md:p-8">
              <img
                src={heroPhoto}
                alt=""
                loading="lazy"
                className="absolute inset-0 -z-20 size-full scale-125 object-cover object-[78%_35%] transition-transform duration-700 group-hover:scale-[1.3]"
              />
              <div className="absolute inset-0 -z-10 bg-gradient-to-t from-zinc-950/90 via-zinc-950/45 to-zinc-950/10" />
              <IconUsersGroup className="mb-auto size-7 text-teal-200" stroke={1.5} />
              <h3 className="text-2xl font-semibold tracking-tight">Ban quản lý</h3>
              <p className="mt-2 max-w-md text-[15px] leading-relaxed text-white/80">
                Xác nhận phản ánh, theo dõi sự cố và duyệt chi phí. Việc cần người quyết định được gom về một hộp.
              </p>
            </article>
          </Reveal>

          <Reveal delay={0.06}>
            <article className="flex h-full flex-col rounded-2xl bg-teal-700 p-6 text-white dark:bg-teal-900/70">
              <IconTool className="size-7 text-teal-100" stroke={1.5} />
              <h3 className="mt-auto pt-10 text-xl font-semibold tracking-tight">Kỹ thuật viên</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-teal-50/85">Nhận việc, lập danh mục vật tư, chụp ảnh trước và sau, mời cư dân ký.</p>
            </article>
          </Reveal>

          <Reveal delay={0.12}>
            <article className="flex h-full flex-col rounded-2xl border bg-muted/50 p-6">
              <IconBrush className={cn('size-7', accentText)} stroke={1.5} />
              <h3 className="mt-auto pt-10 text-xl font-semibold tracking-tight">Nhân viên vệ sinh</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">Làm đúng thứ tự: ảnh trước, đặt biển cảnh báo, làm sạch, ảnh sau.</p>
            </article>
          </Reveal>

          {/* An ninh: wide strip across the grid. */}
          <Reveal delay={0.08} className="md:col-span-3">
            <article className="relative isolate flex min-h-44 flex-col justify-center overflow-hidden rounded-2xl p-6 text-white md:flex-row md:items-center md:justify-between md:gap-10 md:p-8">
              <img src={heroPhoto} alt="" loading="lazy" className="absolute inset-0 -z-20 size-full scale-150 object-cover object-[25%_85%]" />
              <div className="absolute inset-0 -z-10 bg-gradient-to-r from-zinc-950/90 via-zinc-950/70 to-zinc-950/40" />
              <div className="flex items-center gap-4">
                <IconShieldCheck className="size-8 shrink-0 text-teal-200" stroke={1.5} />
                <h3 className="text-xl font-semibold tracking-tight">Nhân viên an ninh</h3>
              </div>
              <p className="mt-3 max-w-xl text-[15px] leading-relaxed text-white/80 md:mt-0">
                Đến hiện trường, ghi kết quả nhắc nhở và chuyển Ban quản lý khi hộ không hợp tác. Danh tính người phản ánh luôn được giữ kín.
              </p>
            </article>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------

const FAQ = [
  {
    q: 'Tài khoản nhân viên lấy ở đâu?',
    a: 'Tài khoản Ban quản lý và nhân viên do quản trị viên cấp. Đăng nhập xong, hệ thống tự mở đúng phần việc theo vai trò của bạn.',
  },
  {
    q: 'Cư dân đăng ký cần những gì?',
    a: 'Họ tên, số điện thoại, tòa và số căn hộ. Thông tin căn hộ giúp yêu cầu tới đúng Ban quản lý phụ trách tòa của bạn.',
  },
  {
    q: 'Ai xem được yêu cầu tôi gửi?',
    a: 'Chỉ bạn, Ban quản lý tòa và nhân viên được giao việc. Tên và số điện thoại chỉ dùng để nhân viên liên hệ khi đến xử lý.',
  },
  {
    q: 'Nếu tôi chưa kịp xác nhận kết quả thì sao?',
    a: 'Bạn có 72 giờ để xác nhận hoặc báo chưa đạt. Sau thời gian đó yêu cầu tự hoàn tất. Việc khẩn cấp như cháy, ngập, kẹt thang máy, bạn gọi ngay hotline trực của tòa nhà.',
  },
];

function Faq() {
  return (
    <section id="hoi-dap" className="scroll-mt-8 border-t bg-background py-20 md:py-28">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 sm:px-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,7fr)] lg:gap-20">
        <Reveal className="lg:sticky lg:top-12 lg:self-start">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Câu hỏi thường gặp</h2>
        </Reveal>
        <Reveal delay={0.08}>
          <div className="flex flex-col gap-3">
            {FAQ.map(({ q, a }, i) => (
              <details key={q} open={i === 0} className="group rounded-2xl border bg-card px-5 open:bg-muted/40">
                <summary className="flex min-h-16 cursor-pointer list-none items-center justify-between gap-4 text-base font-medium [&::-webkit-details-marker]:hidden">
                  {q}
                  <IconPlus className="size-5 shrink-0 text-muted-foreground transition-transform duration-300 group-open:rotate-45" stroke={1.5} />
                </summary>
                <p className="max-w-[65ch] pb-5 text-[15px] leading-relaxed text-muted-foreground">{a}</p>
              </details>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------------

function ClosingCta() {
  const primary = usePrimaryAction();
  return (
    <section className="mx-auto max-w-7xl bg-background px-4 pb-20 sm:px-6 md:pb-28">
      <Reveal>
        <div className="relative isolate overflow-hidden rounded-2xl px-6 py-16 text-white sm:px-12 md:py-24">
          <img src={heroPhoto} alt="" loading="lazy" className="absolute inset-0 -z-20 size-full object-cover object-[40%_60%]" />
          <div className="absolute inset-0 -z-10 bg-gradient-to-r from-zinc-950/85 via-zinc-950/45 to-zinc-950/10" />
          <h2 className="max-w-xl text-3xl font-semibold tracking-tight text-balance md:text-4xl">Căn hộ của bạn, một tin nhắn là có người lo.</h2>
          {primary.who && <p className="mt-3 text-sm text-white/75">Đang đăng nhập: {primary.who}</p>}
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to={primary.to} className={accentButton}>
              {primary.label}
            </Link>
            <Link to="/vinhomes/register" className={glassButton}>
              Đăng ký cư dân
            </Link>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t bg-background">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 text-sm text-muted-foreground sm:px-6 md:flex-row md:items-center md:justify-between">
        <Wordmark />
        <p>Bản trải nghiệm. Tài khoản và dữ liệu chỉ lưu trên trình duyệt này.</p>
      </div>
    </footer>
  );
}

export function LandingPage() {
  return (
    <div lang="vi" className={cn(PORTAL_FONT, 'min-h-[100dvh] bg-background text-foreground antialiased')}>
      <Hero />
      <main>
        <Journey />
        <ResidentSection />
        <StaffSection />
        <Faq />
        <ClosingCta />
      </main>
      <Footer />
    </div>
  );
}
