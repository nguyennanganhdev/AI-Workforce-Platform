import { useNavigate, useSearch } from '@tanstack/react-router';
import { TechnicianJobList } from './technician-job-list';
import { TechnicianJobDetail } from './technician-job-detail';

/** Job list ⇄ job detail, driven by `?job=` so the phone's back button works. */
export function TechnicianWorkspace() {
  const { job } = useSearch({ from: '/_authed/operations/my-tasks' });
  const navigate = useNavigate({ from: '/operations/my-tasks' });

  const open = (woId: string) => {
    navigate({ search: { job: woId } });
    document.querySelector('main')?.scrollTo({ top: 0 });
  };
  const back = () => navigate({ search: {} });

  return job ? <TechnicianJobDetail woId={job} onBack={back} /> : <TechnicianJobList onOpen={open} />;
}
