import { Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { usePlatformAccess } from '@/context/platform-access';
import type { PlatformAccess } from '@/context/platform-access';

function WorkspaceMenuContent({ access }: { access: PlatformAccess }) {
	const navigate = useNavigate();
	return <>
		<DropdownMenuLabel>Không gian làm việc</DropdownMenuLabel>
		{access.workspaces.map((space) => <DropdownMenuItem key={space.id} disabled={access.pending}
			onClick={async () => {
				if (space.id === access.workspace?.id) return;
				try {
					await access.switchWorkspace(space.id);
					navigate('/', { replace: true });
				} catch { toast.error('Không đổi được không gian. Quyền hiện tại đã được tải lại; vui lòng thử lại.'); }
			}}>
			<Check className={space.id === access.workspace?.id ? '' : 'invisible'} aria-hidden="true" />
			{space.label}
		</DropdownMenuItem>)}
		<DropdownMenuSeparator />
	</>;
}

/** Also safe in the legacy admin tree, which lives outside the router. */
export function WorkspaceMenuItems() {
	const access = usePlatformAccess();
	return access ? <WorkspaceMenuContent access={access} /> : null;
}
