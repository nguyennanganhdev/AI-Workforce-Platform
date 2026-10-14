import { useEffect, useState } from "react";
import { IconBook2, IconCheck, IconCopy, IconLoader2, IconClock, IconChevronDown } from "@tabler/icons-react";
import type { ChatMessage, ReceptionStage, TurnState } from "../../services/types";
import "./chat-experience.css";

const labels: Record<ReceptionStage["stage"], string> = {
  context: "Đang xem thông tin cuộc trò chuyện",
  searching: "Đang tra cứu tài liệu khu dân cư",
  request: "Đang kiểm tra yêu cầu của bạn",
  status: "Đang xem tiến độ yêu cầu",
  responding: "Đang chuẩn bị phản hồi",
};
const seconds = (ms: number) => `${(Math.max(0,ms)/1000).toLocaleString("vi-VN",{maximumFractionDigits:1})} giây`;

export function ProcessingStatus({ turn }: { turn?: TurnState }) {
  const [now,setNow]=useState(Date.now());
  useEffect(() => { const timer=setInterval(() => setNow(Date.now()),1000); return () => clearInterval(timer); },[]);
  const started=turn?.startedAt ? Date.parse(turn.startedAt) : NaN;
  const elapsed=Number.isFinite(started) ? Math.max(0,now-started) : turn?.elapsedMs ?? 0;
  const stage=turn?.steps.at(-1)?.stage;
  const text=turn?.status === "waiting_platform" ? "Đang chờ phản hồi từ bộ phận xử lý" :
    turn?.status === "queued" ? "Tin nhắn đã gửi, đang chờ trợ lý" : labels[stage ?? "responding"];
  return <div className="reception-processing">
    <div role="status"><IconLoader2 className="reception-spinner" size={18} aria-hidden="true" /><span>{text}</span></div>
    <span className="reception-elapsed" aria-hidden="true">{seconds(elapsed)}</span>
    {elapsed>20000 && <p>Phản hồi đang mất nhiều thời gian hơn. Bạn có thể tiếp tục đọc các tin trước.</p>}
  </div>;
}

/** A footer is hidden only when the structured, persisted citations replace it. */
export function answerText(message: ChatMessage) {
  return message.reception?.citations?.length ? message.text.replace(/\n\(Nguồn(?: tham khảo)?: [\s\S]*\)\s*$/,"") : message.text;
}

export function MessageDetails({ message }: { message: ChatMessage }) {
  const [copy,setCopy]=useState("");
  const info=message.reception;
  const stages=(info?.steps ?? []).filter((s,i,a) => i===0 || s.stage!==a[i-1].stage);
  const time=message.createdAt && !Number.isNaN(Date.parse(message.createdAt)) ?
    new Date(message.createdAt).toLocaleTimeString("vi-VN",{hour:"2-digit",minute:"2-digit"}) : "";
  return <div className="message-footer">
    <div className="message-meta">
      {time && <time dateTime={message.createdAt}>{time}</time>}
      {message.role==="resident" ? <span><IconCheck size={14} aria-hidden="true" />{message.delivery==="answered" ? "Đã phản hồi" : "Đã gửi"}</span> : <>
        {!!message.text && <button type="button" aria-label="Sao chép câu trả lời" title="Sao chép câu trả lời" onClick={async () => {
          try { await navigator.clipboard.writeText(message.text);setCopy("Đã sao chép"); }
          catch {setCopy("Không sao chép được. Bạn có thể chọn nội dung để sao chép.");}
        }}><IconCopy size={15} aria-hidden="true" /></button>}
      </>}
    </div>
    {message.role==="assistant" && (!!info?.citations?.length || !!stages.length || typeof info?.latencyMs==="number") && <details className="message-insights">
      <summary><IconBook2 size={15} aria-hidden="true" /><span>{info?.citations?.length ? `Nguồn & chi tiết (${info.citations.length})` : "Chi tiết phản hồi"}</span><IconChevronDown size={15} aria-hidden="true" /></summary>
      <div className="message-insights-content">
      {typeof info?.latencyMs==="number" && <p className="reception-latency"><IconClock size={14} aria-hidden="true" />Thời gian xử lý: {seconds(info.latencyMs)}</p>}
      {!!info?.citations?.length && <div className="reception-sources" aria-label="Nguồn trả lời">
      <span className="reception-sources-label"><IconBook2 size={15} aria-hidden="true" /> Nguồn trả lời</span>
      {info.citations.map((source,i) => <details key={`${source.documentId ?? source.title}-${i}`}>
        <summary><span>{source.title}</span><small>{source.status==="approved" ? "Đã xác nhận" : "Tham khảo"}</small><IconChevronDown size={16} aria-hidden="true" /></summary>
        <div className="reception-source-content">
          {source.excerpt && <blockquote>{source.excerpt}</blockquote>}
          {source.documentReference && <p>Văn bản: {source.documentReference}</p>}
          {source.effectiveFrom && <p>Hiệu lực từ: {source.effectiveFrom}</p>}
          {source.status!=="approved" && <p>Thông tin tham khảo; cần xác nhận nội dung hiện hành với Ban quản lý.</p>}
        </div>
      </details>)}
      </div>}
      {!!stages.length && <div className="reception-activity"><p>Hoạt động của trợ lý</p><ol>{stages.map((s,i) => <li key={i}>{labels[s.stage]}</li>)}</ol></div>}
      </div>
    </details>}
    {copy && <p className="copy-status" role="status">{copy}</p>}
  </div>;
}
