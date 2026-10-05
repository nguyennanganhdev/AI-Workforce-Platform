import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import {
  IconArrowUp,
  IconArrowUpRight,
  IconCheck,
  IconChevronRight,
  IconClipboardList,
  IconHome,
  IconMapPin,
  IconPaperclip,
  IconPlus,
  IconShieldCheck,
  IconSparkles,
  IconSwimming,
  IconTool,
  IconX,
} from "@tabler/icons-react";
import { Neighborhood } from "../../components/Illustrations";
import { resident } from "../../mocks/seed";
import { formOffered } from "../../services/chat-turn";
import { QuestionCard } from "./QuestionCard";
import { MAX_PHOTOS, readPhotos } from "../../services/resident-service";
import type { Draft, Photo, ResidentState } from "../../services/types";
import { RequestCard } from "../requests/Requests";

type AssistantProps = {
  connected?: boolean;
  busy?: boolean;
  residentName?: string;
  apartment?: string;
  draftFields?: ReactNode;
  state: ResidentState;
  conversation: boolean;
  onResume: () => void;
  onSend: (text: string, photos?: Photo[]) => boolean | Promise<boolean>;
  onForm?: () => void;
  /** What management is asking in this conversation right now, if anything. */
  question?: string;
  onOpen: (id: string) => void;
  onRequests: () => void;
  onSubmit: () => void;
  onEditDraft: () => void;
  onCancelDraft: () => void;
};

export function Assistant({
  connected = false,
  busy = false,
  residentName = "An",
  apartment = resident.apartment,
  draftFields,
  state,
  conversation,
  onResume,
  onSend,
  onForm,
  question,
  onOpen,
  onRequests,
  onSubmit,
  onEditDraft,
  onCancelDraft,
}: AssistantProps) {
  const end = useRef<HTMLDivElement>(null);
  const prevMessages = useRef(state.messages.length);
  useEffect(() => {
    if (conversation && prevMessages.current !== state.messages.length) {
      end.current?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "end",
      });
      prevMessages.current = state.messages.length;
    }
  }, [state.messages.length, conversation]);
  const current =
    state.requests.find((r) => r.status === "confirmation") ??
    state.requests.find((r) => r.status !== "completed");
  const started = conversation;
  const offerForm = !!onForm && formOffered(state.messages);
  return (
    <div className={`assistant-content ${started ? "started" : ""}`}>
      {!started && (
        <>
          <div className="greeting">
            <span className="eyebrow">KHÔNG GIAN CƯ DÂN</span>
            <h1>
              Chào {residentName.split(" ").at(-1)}, hôm nay
              <br /> bạn cần hỗ trợ gì?{" "}
              <span className="greeting-sun" aria-hidden="true">
                ✳
              </span>
            </h1>
            <p>Mình ở đây để cuộc sống ở nhà dễ dàng hơn.</p>
          </div>
          {state.messages.length > 0 && (
            <button className="resume-conversation" onClick={onResume}>
              <IconSparkles size={20} />
              <span>
                <strong>Tiếp tục cuộc trò chuyện</strong>
                <small>
                  {state.draft
                    ? "Bạn có một phản ánh đang soạn"
                    : "Xem lại lịch sử trao đổi của bạn"}
                </small>
              </span>
              <IconChevronRight size={18} />
            </button>
          )}
          <section className="hero-card">
            <div className="hero-copy">
              <span className="hero-tag">
                <span />
                TRỢ LÝ CỦA RIÊNG BẠN
              </span>
              <h2>
                Chuyện ở nhà,
                <br />
                cứ để mình lo.
              </h2>
              <p>
                Hỏi thông tin, báo sự cố.
                <br />
                Chỉ cần một tin nhắn.
              </p>
              <button onClick={() => onSend("Báo sự cố")}>
                Bắt đầu trò chuyện <IconArrowUpRight size={17} />
              </button>
            </div>
            <Neighborhood />
          </section>
          <div className="section-heading">
            <h3>Bạn muốn làm gì?</h3>
            <span className="small muted">Mình giúp nhé</span>
          </div>
          <div className="quick-actions">
            {[
              {
                icon: IconTool,
                label: "Báo sự cố",
                description: "Có mình hỗ trợ",
                color: "coral",
                text: "Báo sự cố",
              },
              {
                icon: IconClipboardList,
                label: "Yêu cầu của tôi",
                description: "Theo dõi tiến độ",
                color: "blue",
                text: "Xem yêu cầu của tôi",
              },
              {
                icon: IconSwimming,
                label: "Hỏi về tiện ích",
                description: "Khám phá quanh nhà",
                color: "teal",
                text: "Hỏi về tiện ích",
              },
              {
                icon: IconHome,
                label: "Thông tin tòa nhà",
                description: "Những điều cần biết",
                color: "orange",
                text: "Thông tin tòa nhà",
              },
            ].map(({ icon: Icon, label, description, color, text }) => (
              <button key={label} onClick={() => onSend(text)}>
                <span className={`icon-tile ${color}`}>
                  <Icon size={23} stroke={1.65} />
                </span>
                <span>
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
                <IconArrowUpRight size={15} className="action-arrow" />
              </button>
            ))}
          </div>
          {current && (
            <section className="recent-section">
              <div className="section-heading">
                <h3>
                  Yêu cầu gần đây <span className="section-dot" />
                </h3>
                <button className="inline-link" onClick={onRequests}>
                  Xem tất cả <IconChevronRight size={14} />
                </button>
              </div>
              <RequestCard request={current} onOpen={onOpen} compact />
            </section>
          )}
          <p className="welcome-footnote">
            <IconShieldCheck size={16} />
            Được lắng nghe. Được quan tâm. Ngay tại nhà.
          </p>
        </>
      )}
      {started && (
        <>
          <div className="chat-day">
            <span>Cuộc trò chuyện của bạn</span>
          </div>
          <div className="chat-intro">
            <span className="assistant-avatar">
              <IconSparkles size={21} />
            </span>
            <div>
              <strong>Nhà — Trợ lý cư dân</strong>
              <p>Mình sẵn sàng lắng nghe. Bạn cần hỗ trợ gì hôm nay?</p>
            </div>
          </div>
          <div
            className="messages"
            role="log"
            aria-label="Cuộc trò chuyện"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {state.messages
              // The open question is drawn below as a card to answer, not twice.
              .filter((message) => !(question && message.role === "assistant" && message.text === question))
              .map((message) => (
              <div key={message.id} className={`message ${message.role}`}>
                {message.role === "assistant" && (
                  <span className="assistant-avatar small-avatar">
                    <IconSparkles size={15} />
                  </span>
                )}
                <div className="message-body">
                  <div className="message-bubble">
                    {message.text && <p>{message.text}</p>}
                    {!!message.photos?.length && (
                      <div className="photo-grid">
                        {message.photos.map((photo) => (
                          <a
                            key={photo.id}
                            href={photo.url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <img src={photo.url} alt={photo.name} />
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                  {message.requestId &&
                    (() => {
                      const request = state.requests.find(
                        (r) => r.id === message.requestId,
                      );
                      return request ? (
                        <RequestCard
                          request={request}
                          onOpen={onOpen}
                          compact
                        />
                      ) : null;
                    })()}
                </div>
              </div>
            ))}
            {state.awaitingReply && (
              <div className="message assistant">
                <span className="assistant-avatar small-avatar">
                  <IconSparkles size={15} />
                </span>
                <div className="message-body">
                  <div className="message-bubble message-waiting">
                    <p>Trợ lý đang trả lời…</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
      {started && question && !state.awaitingReply && (
        <QuestionCard key={question} question={question} busy={busy} onAnswer={(text) => onSend(text)} />
      )}
      {started && connected && state.draft && state.draft.step !== "review" && (
        <p className="edit-draft-note" role="status">
          {state.draft.step === "description"
            ? "Hãy mô tả sự cố và đính kèm ảnh nếu có."
            : "Sự cố xảy ra ở đâu? Nhập tầng, căn hộ hoặc vị trí cụ thể."}
        </p>
      )}
      {started &&
        state.draft?.step === "description" &&
        state.draft.description && (
          <div className="edit-draft-note">
            <strong>Sửa nội dung phản ánh</strong>
            <p>Nội dung hiện tại: {state.draft.description}</p>
            <p>
              Nhập mô tả mới vào ô tin nhắn bên dưới. Ảnh đã đính kèm sẽ được
              giữ lại.
            </p>
          </div>
        )}
      {started && state.draft?.step === "location" && (
        <div className="suggestion-row">
          <button onClick={() => onSend(`Căn hộ ${apartment}`)}>
            <IconMapPin size={16} />
            Căn hộ của tôi · {apartment}
          </button>
        </div>
      )}
      {started && state.draft?.step === "review" && (
        <DraftCard
          draft={state.draft}
          connected={connected}
          busy={busy}
          fields={draftFields}
          onSubmit={onSubmit}
          onEdit={onEditDraft}
          onCancel={onCancelDraft}
        />
      )}
      {started && state.draft && state.draft.step !== "review" && (
        <button className="text-button cancel-draft" onClick={onCancelDraft}>
          Hủy phản ánh đang soạn
        </button>
      )}
      {started && !state.draft && (
        <div className="suggestion-row">
          {!connected && (
            <button onClick={() => onSend("Báo sự cố")}>
              <IconPlus size={15} />
              Báo sự cố
            </button>
          )}
          <button onClick={() => onSend("Xem yêu cầu của tôi")}>
            <IconClipboardList size={15} />
            Xem tiến độ
          </button>
          {offerForm && (
            <button onClick={onForm}>
              <IconClipboardList size={15} />
              Gửi bằng biểu mẫu
            </button>
          )}
        </div>
      )}
      <div ref={end} className="scroll-end" />
    </div>
  );
}

function DraftCard({
  connected,
  busy,
  fields,
  draft,
  onSubmit,
  onEdit,
  onCancel,
}: {
  connected?: boolean;
  busy?: boolean;
  fields?: ReactNode;
  draft: Draft;
  onSubmit: () => void;
  onEdit: () => void;
  onCancel: () => void;
}) {
  return (
    <section className="draft-card">
      <div className="draft-heading">
        <span className="icon-tile coral">
          <IconClipboardList size={22} />
        </span>
        <div>
          <span className="eyebrow">KIỂM TRA TRƯỚC KHI GỬI</span>
          <h3>Phản ánh của bạn</h3>
        </div>
      </div>
      <dl>
        <dt>Nội dung</dt>
        <dd className="preserve">{draft.description}</dd>
        <dt>Vị trí</dt>
        <dd>
          <IconMapPin size={15} />
          {draft.location}
        </dd>
      </dl>
      {draft.photos.length > 0 && (
        <div className="photo-grid">
          {draft.photos.map((p) => (
            <img key={p.id} src={p.url} alt={p.name} />
          ))}
        </div>
      )}
      {fields}
      <p className="small muted">
        {connected
          ? "Phản ánh sẽ được gửi tới Ban quản lý."
          : "Bản trải nghiệm · Chỉ lưu trên thiết bị này."}
      </p>
      <button
        className="primary-button full"
        disabled={busy}
        onClick={onSubmit}
      >
        <IconCheck size={19} />
        Gửi phản ánh
      </button>
      <div className="button-row">
        <button className="text-button" onClick={onEdit}>
          Sửa nội dung
        </button>
        <button className="text-button muted" onClick={onCancel}>
          Hủy phản ánh
        </button>
      </div>
    </section>
  );
}

export function Composer({
  connected = false,
  busy = false,
  onSend,
  draft,
  initialInput,
  onInputChange,
}: {
  onSend: (text: string, photos?: Photo[]) => boolean | Promise<boolean>;
  connected?: boolean;
  busy?: boolean;
  draft: Draft | null;
  initialInput?: { text: string; photos: Photo[] };
  onInputChange?: (value: { text: string; photos: Photo[] }) => void;
}) {
  const [text, setText] = useState(initialInput?.text ?? "");
  const [photos, setPhotos] = useState<Photo[]>(initialInput?.photos ?? []);
  useEffect(() => {
    onInputChange?.({ text, photos });
  }, [text, photos, onInputChange]);
  const [error, setError] = useState("");
  const [reading, setReading] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  async function send(event?: FormEvent) {
    event?.preventDefault();
    if (busy || reading || (!text.trim() && !photos.length)) return;
    if (await onSend(text, photos)) {
      setText("");
      setPhotos([]);
      setError("");
    }
  }
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = "auto";
      const height = textarea.current.scrollHeight;
      textarea.current.style.height = `${Math.min(height + 2, 110)}px`;
      textarea.current.style.overflowY = height > 108 ? "auto" : "hidden";
    }
  }, [text]);
  return (
    <div className="composer-area">
      {error && (
        <p role="alert" className="composer-error">
          {error}
        </p>
      )}
      {photos.length > 0 && (
        <div className="attachment-strip">
          {photos.map((photo) => (
            <div key={photo.id}>
              <img src={photo.url} alt={photo.name} />
              <button
                aria-label={`Bỏ ảnh ${photo.name}`}
                onClick={() =>
                  setPhotos(photos.filter((p) => p.id !== photo.id))
                }
              >
                <IconX size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
      <form className="composer" onSubmit={send}>
        <input
          ref={input}
          className="sr-only"
          aria-label="Chọn ảnh đính kèm"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          tabIndex={-1}
          disabled={reading || busy}
          onChange={async (event) => {
            const files = Array.from(event.target.files ?? []);
            event.target.value = "";
            if (!files.length) return;
            setReading(true);
            setError("");
            try {
              if (
                files.length + photos.length + (draft?.photos.length ?? 0) >
                MAX_PHOTOS
              )
                throw new Error("Mỗi phản ánh tối đa 3 ảnh.");
              const selected = await readPhotos(files);
              setPhotos((prev) => [...prev, ...selected]);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Không đọc được ảnh.");
            } finally {
              setReading(false);
            }
          }}
        />
        <button
          className="attach-button"
          type="button"
          aria-label="Đính kèm ảnh (tối đa 3 ảnh, 10 MB mỗi ảnh; tự động thu nhỏ)"
          disabled={reading || busy}
          onClick={() => input.current?.click()}
        >
          <IconPaperclip size={23} stroke={1.7} />
        </button>
        <textarea
          ref={textarea}
          rows={1}
          aria-label="Tin nhắn cho trợ lý"
          placeholder={
            draft?.step === "location"
              ? "Nhập vị trí xảy ra sự cố…"
              : "Nhắn điều bạn cần, mình ở đây…"
          }
          value={text}
          maxLength={2000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing &&
              matchMedia("(pointer: fine)").matches
            ) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button
          className="send-button"
          type="submit"
          aria-label="Gửi tin nhắn"
          disabled={busy || reading || (!text.trim() && !photos.length)}
        >
          <IconArrowUp size={21} stroke={2} />
        </button>
      </form>
      <p className="composer-caption">
        {reading
          ? "Đang đọc ảnh…"
          : busy
            ? "Đang gửi…"
            : connected
              ? "Tin nhắn được lưu vào cuộc trò chuyện của bạn"
              : "Bản trải nghiệm · Chưa gửi thông tin đến Ban quản lý"}
      </p>
    </div>
  );
}
