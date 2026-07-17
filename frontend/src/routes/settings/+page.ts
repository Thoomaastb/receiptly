import { redirect } from '@sveltejs/kit';

// /settings hat keinen eigenen Inhalt — leitet auf den ersten Menüpunkt weiter.
export const load = () => {
	throw redirect(307, '/settings/security');
};
