import '../operations.css';
import { useEffect, useState } from 'react';
import { Outlet } from '@tanstack/react-router';
import { OperationsSidebar } from './operations-sidebar';
import { OperationsHeader } from './operations-header';
import { OperationsProvider } from '../hooks/use-operations-data';
import { exitOperationsPreview, previewAccount } from '../auth/demo-access';

export function OperationsLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [, refreshAccount] = useState(0);
  useEffect(() => {
    const checkAccount = () => { if (!previewAccount()) exitOperationsPreview(); else refreshAccount(n => n + 1); };
    window.addEventListener('storage', checkAccount);
    window.addEventListener('operations-workspace-change', checkAccount);
    return () => { window.removeEventListener('storage', checkAccount); window.removeEventListener('operations-workspace-change', checkAccount); };
  }, []);
  useEffect(() => {
    const originalTitle = document.title;
    const originalLanguage = document.documentElement.lang;
    const originalTranslate = document.documentElement.getAttribute('translate');
    const alreadyNotranslate = document.documentElement.classList.contains('notranslate');
    const existingGoogleMeta = document.head.querySelector<HTMLMetaElement>('meta[name="google"]');
    const googleMeta = existingGoogleMeta || document.createElement('meta');

    document.title = 'Vinhomes Operations Platform';
    document.documentElement.lang = 'vi';
    document.documentElement.setAttribute('translate', 'no');
    document.documentElement.classList.add('notranslate');

    if (!existingGoogleMeta) {
      googleMeta.name = 'google';
      googleMeta.content = 'notranslate';
      document.head.appendChild(googleMeta);
    }

    return () => {
      document.title = originalTitle;
      document.documentElement.lang = originalLanguage;
      if (originalTranslate === null) {
        document.documentElement.removeAttribute('translate');
      } else {
        document.documentElement.setAttribute('translate', originalTranslate);
      }
      if (!alreadyNotranslate) {
        document.documentElement.classList.remove('notranslate');
      }
      if (!existingGoogleMeta) {
        googleMeta.remove();
      }
    };
  }, []);

  return (
    <OperationsProvider>
      <div
        lang="vi"
        translate="no"
        className="operations-app notranslate flex h-[100dvh] w-full overflow-hidden font-sans"
      >
        {/* Sidebar Backdrop (mobile overlay) */}
        {menuOpen && (
          <div
            className="operations-sidebar-backdrop"
            onClick={() => setMenuOpen(false)}
            aria-hidden="true"
          />
        )}

        <OperationsSidebar open={menuOpen} onNavigate={() => setMenuOpen(false)} />

        {/* Main Container */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          <div className="flex items-center justify-between gap-3 bg-blue-50 px-4 py-2 text-xs text-blue-900 border-b border-blue-100" role="status">
            <span>Bản trải nghiệm · Hồ sơ và công việc là dữ liệu mẫu</span>
            <button type="button" onClick={exitOperationsPreview} className="shrink-0 min-h-10 px-2 font-semibold underline underline-offset-4">Thoát trải nghiệm</button>
          </div>
          <OperationsHeader menuOpen={menuOpen} onToggleMenu={() => setMenuOpen(!menuOpen)} />

          {/* Dynamic Page Content */}
          <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6 xl:p-8">
            <div className="operations-content w-full min-w-0 max-w-full">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </OperationsProvider>
  );
}
