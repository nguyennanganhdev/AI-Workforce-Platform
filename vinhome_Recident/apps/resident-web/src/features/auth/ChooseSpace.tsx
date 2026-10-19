import { useEffect, useRef } from "react";
import { IconBuildingCommunity } from "@tabler/icons-react";
import "./auth.css";
import { Brand } from "../../components/Brand";

/** One account that is both a resident's and a staff member's: asked once where to go. */
export function ChooseSpace({ operationsHref }: { operationsHref: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = "Chọn không gian | Vinhomes";
    heading.current?.focus();
  }, []);
  return (
    <main className="resident-auth-status">
      <a className="resident-auth-status-brand" href="/login">
        <Brand />
      </a>
      <section>
        <span className="resident-auth-status-icon">
          <IconBuildingCommunity size={36} />
        </span>
        <h1 tabIndex={-1} ref={heading}>
          Bạn muốn vào đâu?
        </h1>
        <p>Tài khoản này dùng được cả không gian cư dân và không gian vận hành.</p>
        <a className="resident-auth-status-action" href="/resident">
          Không gian cư dân
        </a>
        <a className="resident-auth-status-action" href={operationsHref}>
          Không gian vận hành
        </a>
      </section>
    </main>
  );
}
