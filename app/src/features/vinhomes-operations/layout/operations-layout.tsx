import { useEffect } from 'react';
import { Outlet } from '@tanstack/react-router';
import { OperationsSidebar } from './operations-sidebar';
import { OperationsHeader } from './operations-header';
import { OperationsProvider } from '../hooks/use-operations-data';

export function OperationsLayout() {
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
        className="operations-app notranslate flex h-screen w-screen overflow-hidden bg-slate-50 font-sans"
      >
        {/* BistroPulse Left Sidebar */}
        <OperationsSidebar />

        {/* Main Container */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* BistroPulse Top Header */}
          <OperationsHeader />

          {/* Dynamic Page Content */}
          <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-slate-50/80">
            <div className="max-w-7xl mx-auto">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </OperationsProvider>
  );
}
