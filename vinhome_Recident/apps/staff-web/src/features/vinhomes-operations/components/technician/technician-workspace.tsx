import { useNavigate, useSearch } from '@tanstack/react-router';
import { TechnicianJobList, type JobListView } from './technician-job-list';
import { TechnicianJobDetail } from './technician-job-detail';

/** Job list ⇄ job detail, driven by `?job=` (and `?view=history`) so the phone's back button works. */
export function TechnicianWorkspace() {
  const { job, view } = useSearch({ from: '/_authed/operations/my-tasks' });
  const navigate = useNavigate({ from: '/operations/my-tasks' });
  const listView: JobListView = view === 'history' ? 'HISTORY' : 'CURRENT';

  const scrollTop = () => document.querySelector('main')?.scrollTo({ top: 0 });
  const open = (woId: string) => {
    navigate({ search: { job: woId, ...(view ? { view } : {}) } });
    scrollTop();
  };
  const back = () => navigate({ search: view ? { view } : {} });
  const changeView = (next: JobListView) => {
    navigate({ search: next === 'HISTORY' ? { view: 'history' } : {} });
    scrollTop();
  };

  return job ? (
    <TechnicianJobDetail woId={job} onBack={back} />
  ) : (
    <TechnicianJobList view={listView} onViewChange={changeView} onOpen={open} />
  );
}
