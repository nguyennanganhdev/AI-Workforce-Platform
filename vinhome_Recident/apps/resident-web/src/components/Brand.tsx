/** Use the supplied Vinhomes artwork consistently, without recreating the mark. */
export function Brand({ compact = false }: { compact?: boolean }) {
  return <span className={`vinhomes-brand${compact ? " is-compact" : ""}`}>
    <img src="/images/vinhomes-official.png" alt="Vinhomes" width={124} height={56} />
    {!compact && <span>Cổng dịch vụ cư dân</span>}
  </span>;
}
