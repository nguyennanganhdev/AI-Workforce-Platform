import { usePlatformAccess } from '@/context/platform-access';

/** UI affordances only; every mutation still needs the server capability gate. */
export function useCatalogManagement() {
	const access = usePlatformAccess();
	return access === null || access.view?.capabilities['catalog.manage'] === true;
}

/** Private provider CRUD is independent of managing the shared catalog. */
export function usePrivateProviderManagement() {
	const access = usePlatformAccess();
	return access === null || access.view?.capabilities['providers.private.manage'] === true;
}
