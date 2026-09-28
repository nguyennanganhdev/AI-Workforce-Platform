import { useEffect } from 'react';
import { Outlet } from '@tanstack/react-router';
import { OperationsSidebar } from './operations-sidebar';
import { OperationsHeader } from './operations-header';
import { OperationsProvider } from '../hooks/use-operations-data';

export function OperationsLayout() {
  useEffect(() => {
    const originalTitle = document.title;
    document.title = 'Vinhomes Operations Platform';
    return () => {
      document.title = originalTitle;
    };
  }, []);

  return (
    <OperationsProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-slate-50 font-sans">
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
