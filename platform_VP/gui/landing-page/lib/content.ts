export const content = {
  marquee: [
    "Trả lời khách hàng 24/7",
    "Xử lý đơn hàng",
    "Tổng hợp báo cáo",
    "Soạn & gửi email",
    "Đặt lịch hẹn",
    "Đồng bộ dữ liệu",
    "Sàng lọc hồ sơ ứng viên",
    "Đối soát chứng từ",
  ],
  how: {
    eyebrow: "Cách hoạt động",
    title: "Từ ý tưởng đến quy trình chạy thật",
    accent: "chỉ trong 3 bước.",
    steps: [
      {
        number: "01",
        title: "Tạo Agent",
        description:
          "Mô tả công việc bằng tiếng Việt tự nhiên. VAgents dựng agent với vai trò, kỹ năng và giới hạn rõ ràng.",
      },
      {
        number: "02",
        title: "Kết nối công cụ",
        description:
          "Cắm agent vào email, bảng tính, CRM, kênh chat và cơ sở dữ liệu mà đội bạn đang dùng hằng ngày.",
      },
      {
        number: "03",
        title: "Vận hành quy trình",
        description:
          "Các agent phối hợp, chuyển việc cho nhau và báo cáo lại. Bạn chỉ cần duyệt những bước quan trọng.",
      },
    ],
  },
  team: {
    eyebrow: "Gặp gỡ đội ngũ",
    title: "Năm agent,",
    accent: "một tinh thần đồng đội.",
    lead: "Rê chuột lên từng thẻ để gặp các thành viên. Mỗi agent có chuyên môn riêng, và luôn biết lúc nào cần chuyển việc cho đồng đội.",
    members: [
      {
        id: "cskh",
        role: "Chăm sóc khách hàng",
        name: "Agent CSKH",
        description:
          "Trả lời khách trên mọi kênh, đúng giọng thương hiệu, không để ai phải chờ.",
        tags: ["Chat", "Email", "Hotline"],
        alt: "Agent CSKH đeo tai nghe, giơ ngón tay cái chào khách hàng",
        badge: "",
      },
      {
        id: "dieu-phoi",
        role: "Điều phối",
        name: "Agent Điều phối",
        description:
          "Nhận yêu cầu, chia việc cho đúng người và theo dõi tiến độ đến khi xong.",
        tags: ["Phân việc", "Nhắc hạn"],
        alt: "Agent Điều phối cầm bộ đàm để kết nối đội ngũ",
        badge: "",
      },
      {
        id: "ky-su",
        role: "Xây dựng quy trình",
        name: "Agent Kỹ sư",
        description:
          "Dựng, kết nối và vận hành quy trình tự động, giữ cho mọi thứ chạy trơn tru.",
        tags: ["Workflow", "Tích hợp"],
        alt: "Agent Kỹ sư đội mũ bảo hộ màu cam và cầm cờ lê",
        badge: "TRƯỞNG NHÓM",
      },
      {
        id: "phan-tich",
        role: "Phân tích",
        name: "Agent Phân tích",
        description:
          "Đọc số liệu, phát hiện xu hướng và đề xuất hành động tiếp theo.",
        tags: ["Báo cáo", "Dự báo"],
        alt: "Agent Phân tích đeo kính và xem số liệu trên máy tính bảng",
        badge: "",
      },
      {
        id: "du-lieu",
        role: "Dữ liệu",
        name: "Agent Dữ liệu",
        description: "Thu thập, làm sạch và đồng bộ dữ liệu giữa các hệ thống.",
        tags: ["ETL", "Đồng bộ"],
        alt: "Agent Dữ liệu đeo kính, sẵn sàng đồng bộ thông tin giữa các hệ thống",
        badge: "",
      },
    ],
  },
  integrations: {
    eyebrow: "Tích hợp",
    title: "Kết nối mọi công cụ",
    accent: "bạn đang dùng.",
    lead: "Agent đọc, ghi và hành động trực tiếp trong hệ thống của bạn, không bắt cả đội phải đổi thói quen.",
    visualLabel: "VAgents kết nối các nhóm công cụ trong doanh nghiệp",
    features: [
      {
        title: "Kênh giao tiếp",
        description: "Email, chat nội bộ, kênh nhắn tin với khách hàng.",
      },
      {
        title: "Dữ liệu & tài liệu",
        description:
          "Bảng tính, cơ sở dữ liệu, kho tài liệu và lưu trữ đám mây.",
      },
      {
        title: "Kinh doanh & vận hành",
        description:
          "CRM, bán hàng, kế toán, kho vận. [Bổ sung danh sách tích hợp chính thức]",
      },
    ],
    nodes: [
      "Chat",
      "Email",
      "Bảng tính",
      "Thanh toán",
      "Cơ sở dữ liệu",
      "Tài liệu",
      "Lịch",
      "Báo cáo",
      "Bán hàng",
      "Đám mây",
      "Đội ngũ",
      "Marketing",
    ],
  },
  useCases: {
    eyebrow: "Ứng dụng",
    title: "Một nền tảng.",
    accent: "Mọi phòng ban.",
    featuredTitle: "Mỗi phòng ban một đội agent riêng",
    featuredText:
      "Từ chăm sóc khách hàng đến kho vận, các agent kết nối thành một mạng lưới làm việc liền mạch.",
    imageAlt:
      "Đội ngũ agent cùng tiến về cổng VAgents giữa các không gian công việc",
    items: [
      {
        title: "Chăm sóc khách hàng",
        description: "Giải đáp, theo dõi đơn, xử lý khiếu nại.",
      },
      {
        title: "Bán hàng",
        description: "Chấm điểm khách tiềm năng, gửi báo giá, nhắc chốt đơn.",
      },
      {
        title: "Nhân sự",
        description: "Sàng lọc hồ sơ, hẹn lịch phỏng vấn, hỗ trợ hội nhập.",
      },
      {
        title: "Kế toán",
        description: "Đối soát chứng từ, nhắc công nợ, lập báo cáo.",
      },
      {
        title: "Vận hành & kho",
        description: "Theo dõi tồn kho, điều phối giao nhận.",
      },
      {
        title: "Marketing",
        description: "Lên lịch nội dung, đo hiệu quả chiến dịch.",
      },
    ],
  },
  stats: [
    {
      value: 24,
      suffix: "/7",
      placeholder: "",
      label: "Agent làm việc không nghỉ",
    },
    { value: 5, suffix: "", placeholder: "", label: "Vai trò agent sẵn sàng" },
    { value: 3, suffix: "", placeholder: "", label: "Bước để bắt đầu" },
    {
      value: 0,
      suffix: "",
      placeholder: "[X]+",
      label: "[Số doanh nghiệp đang dùng]",
    },
  ],
  faq: {
    eyebrow: "Câu hỏi thường gặp",
    title: "Bạn hỏi,",
    accent: "chúng tôi trả lời.",
    items: [
      {
        question: "VAgents là gì?",
        answer:
          "VAgents là nền tảng giúp bạn tạo một đội ngũ AI agent, kết nối chúng với các công cụ đang dùng và để chúng cùng vận hành quy trình công việc.",
      },
      {
        question: "Tôi có cần biết lập trình để dùng không?",
        answer: "[Câu trả lời]",
      },
      {
        question: "VAgents kết nối được với những công cụ nào?",
        answer: "[Câu trả lời]",
      },
      {
        question: "Dữ liệu của doanh nghiệp có được bảo mật không?",
        answer: "[Câu trả lời]",
      },
      {
        question: "Tôi có thể dùng thử trước khi trả phí không?",
        answer: "[Câu trả lời]",
      },
    ],
  },
} as const;

export const pageCopy = {
  start: "Bắt đầu ngay",
  nav: [
    { label: "Cách hoạt động", href: "#how" },
    { label: "Đội ngũ Agent", href: "#team" },
    { label: "Demo", href: "#demo" },
    { label: "Tích hợp", href: "#connect" },
    { label: "FAQ", href: "#faq" },
  ],
  hero: {
    badge: "MỚI",
    badgeText: "Nền tảng AI Agent cho doanh nghiệp Việt",
    lines: ["Một ý tưởng.", "Cả đội ngũ AI", "cùng hành động."],
    lead: "Giao một mục tiêu, VAgents tự lập đội agent chuyên trách, kết nối công cụ bạn đang dùng và vận hành quy trình từ đầu đến cuối.",
    pillars: ["Tạo Agent", "Kết nối công cụ", "Vận hành mọi quy trình"],
    primary: "Tạo đội Agent đầu tiên",
    secondary: "Xem demo",
    scroll: "Cuộn",
    illustration: "Minh họa hoạt động của đội Agent",
    chips: [
      { title: "Đơn hàng đã xử lý", detail: "Tự động · vừa xong" },
      { title: "Agent CSKH", detail: "Đang trả lời khách…" },
      { title: "Báo cáo ngày đã sẵn sàng", detail: "Agent Phân tích" },
    ],
  },
  demo: {
    eyebrow: "Xem đội agent làm việc",
    heading: ["Bạn ra lệnh một câu.", "Cả đội cùng xử lý."],
    disclaimer:
      "Mô phỏng minh họa. Không gửi yêu cầu hoặc thay đổi dữ liệu thật.",
    windowTitle: "vagents · không gian làm việc",
    prompt:
      "Mỗi khi có đơn hàng mới: kiểm tra tồn kho, xác nhận với khách và cập nhật báo cáo doanh thu.",
    messages: [
      {
        agent: "Agent Điều phối",
        text: "Đã nhận yêu cầu, chia việc cho cả đội.",
        image: "agent-dieu-phoi-240.webp",
      },
      {
        agent: "Agent Dữ liệu",
        text: "Đã kiểm tra kho: mặt hàng còn đủ.",
        image: "agent-du-lieu-240.webp",
      },
      {
        agent: "Agent CSKH",
        text: "Đã gửi tin xác nhận đơn cho khách.",
        image: "agent-cskh-240.webp",
      },
      {
        agent: "Agent Phân tích",
        text: "Đã cập nhật báo cáo doanh thu trong ngày.",
        image: "agent-phan-tich-240.webp",
      },
      {
        agent: "Agent Kỹ sư",
        text: "Quy trình đã lưu và sẽ chạy tự động.",
        image: "agent-ky-su-240.webp",
      },
    ],
    statuses: [
      "Đang nhập yêu cầu…",
      "Đội agent đang xử lý…",
      "Hoàn tất · quy trình đang chạy tự động",
    ],
    flowTitle: "Luồng quy trình",
    replay: "Chạy lại demo",
    nodes: [
      "Nhận đơn hàng mới",
      "Kiểm tra tồn kho",
      "Xác nhận với khách",
      "Cập nhật báo cáo",
      "Lưu quy trình tự động",
    ],
  },
  mascotImages: [
    "agent-cskh.webp",
    "agent-dieu-phoi.webp",
    "agent-ky-su.webp",
    "agent-phan-tich.webp",
    "agent-du-lieu.webp",
  ],
  mascotNames: [
    "Agent CSKH",
    "Agent Điều phối",
    "Agent Kỹ sư",
    "Agent Phân tích",
    "Agent Dữ liệu",
  ],
  cta: {
    eyebrow: "Cùng bắt đầu hành trình mới",
    heading: ["Sẵn sàng giao việc cho", "đội ngũ AI của bạn?"],
    lead: "Một ý tưởng là đủ để bắt đầu. Phần còn lại, cứ để các agent lo.",
    secondary: "hoặc đặt lịch demo cùng đội ngũ",
  },
  footer: {
    tagline: "Tạo Agent · Kết nối công cụ · Vận hành mọi quy trình.",
    newsletterLabel: "Nhận tin mới từ VAgents",
    subscribe: "Đăng ký",
    newsletterHelp:
      "Form chưa kết nối dịch vụ nhận tin; email chưa được gửi hoặc lưu.",
    newsletterPending:
      "Chưa thể đăng ký: [Kết nối dịch vụ nhận tin]. Email của bạn chưa được gửi.",
    columns: [
      {
        title: "Sản phẩm",
        items: [
          { label: "Cách hoạt động", href: "#how" },
          { label: "Đội ngũ Agent", href: "#team" },
          { label: "Tích hợp", href: "#connect" },
        ],
      },
      {
        title: "Tài nguyên",
        items: [
          { label: "FAQ", href: "#faq" },
          { label: "Demo", href: "#demo" },
          { label: "[Tài liệu]", href: "" },
          { label: "[Blog]", href: "" },
        ],
      },
      {
        title: "Liên hệ",
        items: [
          { label: "[Email]", href: "" },
          { label: "[Số điện thoại]", href: "" },
          { label: "[Địa chỉ]", href: "" },
        ],
      },
    ],
    copyright: "© 2026 VAgents. [Tên pháp nhân]",
    termsLabel: "Điều khoản",
    privacyLabel: "Bảo mật",
    terms: "[Điều khoản sử dụng]",
    privacy: "[Chính sách bảo mật]",
  },
} as const;
