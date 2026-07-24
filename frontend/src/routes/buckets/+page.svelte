<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	interface Bucket {
		id: string;
		name: string;
		type: string;
		visibility: string;
		is_default: boolean;
		owner_id: string;
	}

	interface Member {
		id: string;
		username: string;
		email: string;
		role: string;
	}

	interface AccessGrant {
		user_id: string;
		username: string;
		access_level: string;
	}

	let buckets: Bucket[] = [];
	let members: Member[] = [];
	let currentUserId = '';
	let isAdmin = false;
	let query = '';
	let loading = true;
	let errorMessage = '';
	let actionError = '';

	let creating = false;
	let newBucketName = '';

	let renamingId: string | null = null;
	let renameValue = '';

	let confirmDeleteId: string | null = null;

	let sharingId: string | null = null;
	let accessGrants: Record<string, AccessGrant[]> = {};
	let candidateLevel: Record<string, string> = {};

	let inviting = false;
	let inviteUsername = '';
	let inviteEmail = '';
	let invitePassword = '';
	let inviteError = '';

	onMount(async () => {
		try {
			const [meRes, bucketsRes, membersRes] = await Promise.all([
				fetch('/api/auth/me', { credentials: 'include' }),
				fetch('/api/buckets', { credentials: 'include' }),
				fetch('/api/auth/household-members', { credentials: 'include' })
			]);
			if (meRes.ok) {
				const me = await meRes.json();
				currentUserId = me.id;
				isAdmin = me.role === 'admin';
			}
			if (!bucketsRes.ok) throw new Error(`Buckets konnten nicht geladen werden (${bucketsRes.status})`);
			buckets = await bucketsRes.json();
			if (membersRes.ok) members = await membersRes.json();
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			loading = false;
		}
	});

	$: filteredBuckets = buckets.filter((b) => b.name.toLowerCase().includes(query.toLowerCase()));
	$: otherMembers = members.filter((m) => m.id !== currentUserId);

	async function createBucket() {
		if (!newBucketName.trim()) return;
		const res = await fetch('/api/buckets', {
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: newBucketName.trim() })
		});
		if (res.ok) {
			buckets = [...buckets, await res.json()];
			newBucketName = '';
			creating = false;
		}
	}

	async function togglePrivate(bucket: Bucket) {
		const nextVisibility = bucket.visibility === 'private' ? 'transparent' : 'private';
		const res = await fetch(`/api/buckets/${bucket.id}/visibility`, {
			method: 'PATCH',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ visibility: nextVisibility })
		});
		if (res.ok) {
			const updated = await res.json();
			buckets = buckets.map((b) => (b.id === bucket.id ? updated : b));
		}
	}

	function startRename(bucket: Bucket) {
		actionError = '';
		renamingId = bucket.id;
		renameValue = bucket.name;
	}

	function cancelRename() {
		renamingId = null;
	}

	async function saveRename(bucket: Bucket) {
		const name = renameValue.trim();
		if (!name) return;
		const res = await fetch(`/api/buckets/${bucket.id}`, {
			method: 'PATCH',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name })
		});
		if (res.ok) {
			const updated = await res.json();
			buckets = buckets.map((b) => (b.id === bucket.id ? updated : b));
			renamingId = null;
		} else {
			const body = await res.json().catch(() => null);
			actionError = body?.detail ?? 'Umbenennen fehlgeschlagen.';
		}
	}

	async function deleteBucket(bucket: Bucket) {
		const res = await fetch(`/api/buckets/${bucket.id}`, {
			method: 'DELETE',
			credentials: 'include'
		});
		if (res.ok || res.status === 204) {
			buckets = buckets.filter((b) => b.id !== bucket.id);
			confirmDeleteId = null;
		} else {
			const body = await res.json().catch(() => null);
			actionError = body?.detail ?? 'Löschen fehlgeschlagen.';
			confirmDeleteId = null;
		}
	}

	async function openSharing(bucket: Bucket) {
		if (sharingId === bucket.id) {
			sharingId = null;
			return;
		}
		actionError = '';
		sharingId = bucket.id;
		if (!accessGrants[bucket.id]) {
			const res = await fetch(`/api/buckets/${bucket.id}/access`, { credentials: 'include' });
			if (res.ok) accessGrants = { ...accessGrants, [bucket.id]: await res.json() };
		}
	}

	function grantableMembers(bucket: Bucket): Member[] {
		const granted = new Set((accessGrants[bucket.id] ?? []).map((g) => g.user_id));
		return otherMembers.filter((m) => m.id !== bucket.owner_id && !granted.has(m.id));
	}

	function toggleCandidateLevel(userId: string) {
		candidateLevel = {
			...candidateLevel,
			[userId]: (candidateLevel[userId] ?? 'view') === 'edit' ? 'view' : 'edit'
		};
	}

	async function addGrant(bucket: Bucket, member: Member) {
		const level = candidateLevel[member.id] ?? 'view';
		const res = await fetch(`/api/buckets/${bucket.id}/access/${member.id}`, {
			method: 'PUT',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ access_level: level })
		});
		if (res.ok) {
			const grant = await res.json();
			const current = accessGrants[bucket.id] ?? [];
			accessGrants = { ...accessGrants, [bucket.id]: [...current, grant] };
		}
	}

	async function updateGrant(bucket: Bucket, grant: AccessGrant, level: string) {
		const res = await fetch(`/api/buckets/${bucket.id}/access/${grant.user_id}`, {
			method: 'PUT',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ access_level: level })
		});
		if (res.ok) {
			const updated = await res.json();
			accessGrants = {
				...accessGrants,
				[bucket.id]: (accessGrants[bucket.id] ?? []).map((g) =>
					g.user_id === updated.user_id ? updated : g
				)
			};
		}
	}

	async function removeGrant(bucket: Bucket, grant: AccessGrant) {
		const res = await fetch(`/api/buckets/${bucket.id}/access/${grant.user_id}`, {
			method: 'DELETE',
			credentials: 'include'
		});
		if (res.ok || res.status === 204) {
			accessGrants = {
				...accessGrants,
				[bucket.id]: (accessGrants[bucket.id] ?? []).filter((g) => g.user_id !== grant.user_id)
			};
		}
	}

	async function inviteMember() {
		inviteError = '';
		if (!inviteUsername.trim() || !inviteEmail.trim() || invitePassword.length < 8) {
			inviteError = 'Bitte Benutzername, E-Mail und ein Passwort mit mind. 8 Zeichen angeben.';
			return;
		}
		const res = await fetch('/api/auth/invite', {
			method: 'POST',
			credentials: 'include',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				username: inviteUsername.trim(),
				email: inviteEmail.trim(),
				password: invitePassword
			})
		});
		if (res.ok) {
			members = [...members, await res.json()];
			inviteUsername = '';
			inviteEmail = '';
			invitePassword = '';
			inviting = false;
		} else {
			const body = await res.json().catch(() => null);
			inviteError = body?.detail ?? 'Einladen fehlgeschlagen.';
		}
	}

	function openBucket(bucket: Bucket) {
		goto(`/receipts?bucket=${bucket.id}`);
	}
</script>

<h1 class="mb-6 text-[26px] font-extrabold tracking-tight text-hifi-text">Buckets</h1>

<div class="relative mb-4 max-w-md">
	<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-hifi-text-faint" aria-hidden="true">
		<circle cx="10" cy="10" r="6" />
		<path d="M20 20l-5.5-5.5" />
	</svg>
	<input
		type="text"
		bind:value={query}
		placeholder="Buckets durchsuchen"
		class="w-full rounded-[12px] border border-hifi-border bg-hifi-surface py-3 pl-11 pr-4 text-[14px] text-hifi-text placeholder:text-hifi-text-faint focus:border-hifi-accent focus:outline-none"
	/>
</div>

{#if loading}
	<p class="text-sm text-hifi-text-muted">Wird geladen …</p>
{:else if errorMessage}
	<p class="text-sm text-danger">{errorMessage}</p>
{:else}
	{#if actionError}
		<p class="mb-4 max-w-md text-sm text-danger">{actionError}</p>
	{/if}

	<ul class="mb-5 flex max-w-md flex-col gap-2">
		{#each filteredBuckets as bucket (bucket.id)}
			<li class="rounded-[14px] border border-hifi-border bg-hifi-surface p-4">
				{#if renamingId === bucket.id}
					<div class="flex items-center gap-2">
						<input
							type="text"
							bind:value={renameValue}
							class="flex-1 rounded-[9px] border border-hifi-border bg-hifi-surface p-1.5 text-sm text-hifi-text"
							on:keydown={(e) => e.key === 'Enter' && saveRename(bucket)}
						/>
						<button on:click={() => saveRename(bucket)} class="text-xs font-semibold text-hifi-accent-text">
							Speichern
						</button>
						<button on:click={cancelRename} class="text-xs text-hifi-text-muted hover:text-hifi-text">
							Abbrechen
						</button>
					</div>
				{:else}
					<div class="flex flex-wrap items-center gap-3">
						<button on:click={() => openBucket(bucket)} class="flex flex-1 items-center gap-3 text-left">
							<span
								class="h-2.5 w-2.5 flex-none rounded-full"
								style="background: var(--color-accent-hifi)"
							></span>
							<span class="flex-1">
								<span class="block text-[13.5px] font-bold text-hifi-text">{bucket.name}</span>
								{#if bucket.visibility === 'private' && bucket.owner_id !== currentUserId}
									<span class="block text-[12px] text-hifi-text-muted">Nur Ansicht</span>
								{/if}
							</span>
							{#if bucket.visibility === 'private'}
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="text-hifi-text-faint" aria-hidden="true">
									<rect x="5" y="11" width="14" height="10" rx="1" />
									<path d="M8 11V7a4 4 0 018 0v4" />
								</svg>
							{/if}
						</button>

						{#if bucket.owner_id === currentUserId}
							<!-- w-full erzwingt bis sm einen Zeilenumbruch der Aktionen unterhalb des
							     Bucket-Namens statt eines gequetschten Nebeneinander von bis zu 4
							     Text-Buttons; flex-wrap zusätzlich als Sicherheitsnetz bei sehr
							     schmalen Screens (320px) mit gesetztem "Sicher?"-Bestätigungsdialog. -->
							<div class="flex w-full flex-wrap items-center gap-2.5 text-xs sm:w-auto">

								<button on:click={() => openSharing(bucket)} class="font-medium text-hifi-text-muted hover:text-hifi-text">
									Teilen
								</button>
								{#if !bucket.is_default}
									<button
										on:click={() => togglePrivate(bucket)}
										class="text-hifi-text-muted hover:text-hifi-text"
										title={bucket.visibility === 'private' ? 'Auf transparent umschalten' : 'Auf privat umschalten'}
									>
										{bucket.visibility === 'private' ? 'Privat' : 'Transparent'}
									</button>
									<button on:click={() => startRename(bucket)} class="text-hifi-text-muted hover:text-hifi-text">
										Umbenennen
									</button>
									{#if confirmDeleteId === bucket.id}
										<span class="text-hifi-text-muted">Sicher?</span>
										<button on:click={() => deleteBucket(bucket)} class="font-semibold text-danger">Ja</button>
										<button on:click={() => (confirmDeleteId = null)} class="text-hifi-text-muted hover:text-hifi-text">
											Nein
										</button>
									{:else}
										<button on:click={() => (confirmDeleteId = bucket.id)} class="text-hifi-text-muted hover:text-danger">
											Löschen
										</button>
									{/if}
								{/if}
							</div>
						{/if}
					</div>

					{#if sharingId === bucket.id}
						<div class="mt-3 border-t border-hifi-border pt-3">
							<div class="mb-2 text-xs font-semibold uppercase tracking-wide text-hifi-text-faint">
								Freigegeben für
							</div>
							{#if (accessGrants[bucket.id] ?? []).length === 0}
								<p class="mb-2 text-xs text-hifi-text-muted">Noch mit niemandem geteilt.</p>
							{:else}
								<ul class="mb-3 flex flex-col gap-1.5">
									{#each accessGrants[bucket.id] as grant (grant.user_id)}
										<li class="flex items-center justify-between text-xs text-hifi-text">
											<span>{grant.username}</span>
											<span class="flex items-center gap-2">
												<button
													on:click={() => updateGrant(bucket, grant, grant.access_level === 'edit' ? 'view' : 'edit')}
													class="text-hifi-text-muted hover:text-hifi-text"
												>
													{grant.access_level === 'edit' ? 'Bearbeiten' : 'Ansehen'}
												</button>
												<button on:click={() => removeGrant(bucket, grant)} class="text-hifi-text-muted hover:text-danger">
													Entfernen
												</button>
											</span>
										</li>
									{/each}
								</ul>
							{/if}

							{#each grantableMembers(bucket) as member (member.id)}
								<div class="mb-1.5 flex items-center justify-between text-xs text-hifi-text">
									<span>{member.username}</span>
									<span class="flex items-center gap-2">
										<button on:click={() => toggleCandidateLevel(member.id)} class="text-hifi-text-muted hover:text-hifi-text">
											{(candidateLevel[member.id] ?? 'view') === 'edit' ? 'Bearbeiten' : 'Ansehen'}
										</button>
										<button on:click={() => addGrant(bucket, member)} class="font-semibold text-hifi-accent-text">
											Hinzufügen
										</button>
									</span>
								</div>
							{:else}
								<p class="text-xs text-hifi-text-muted">
									{otherMembers.length === 0
										? 'Noch keine weiteren Haushaltsmitglieder — lade zuerst jemanden ein.'
										: 'Bereits mit allen Haushaltsmitgliedern geteilt.'}
								</p>
							{/each}
						</div>
					{/if}
				{/if}
			</li>
		{/each}
	</ul>

	{#if creating}
		<div class="flex max-w-md gap-2">
			<input
				type="text"
				bind:value={newBucketName}
				placeholder="Name des Buckets"
				class="flex-1 rounded-[10px] border border-hifi-border bg-hifi-surface p-2 text-sm text-hifi-text placeholder:text-hifi-text-faint"
				on:keydown={(e) => e.key === 'Enter' && createBucket()}
			/>
			<button on:click={createBucket} class="rounded-[10px] bg-hifi-accent px-4 py-2 text-sm font-semibold text-white">
				Anlegen
			</button>
		</div>
	{:else}
		<button on:click={() => (creating = true)} class="text-sm font-medium text-hifi-accent-text">
			+ Eigenen Bucket anlegen
		</button>
	{/if}

	<div class="mt-8 max-w-md border-t border-hifi-border pt-6">
		<div class="mb-3 text-[13.5px] font-bold text-hifi-text">Haushaltsmitglieder</div>
		{#if members.length > 0}
			<ul class="mb-3 flex flex-col gap-1.5">
				{#each members as member (member.id)}
					<li class="flex items-center justify-between text-[12px] text-hifi-text-muted">
						<span>{member.username}{member.id === currentUserId ? ' (Du)' : ''}</span>
						<span>{member.role === 'admin' ? 'Admin' : 'Mitglied'}</span>
					</li>
				{/each}
			</ul>
		{/if}

		{#if isAdmin}
			{#if inviting}
				<div class="flex flex-col gap-2">
					<input type="text" bind:value={inviteUsername} placeholder="Benutzername" class="rounded-[10px] border border-hifi-border bg-hifi-surface p-2 text-sm text-hifi-text placeholder:text-hifi-text-faint" />
					<input type="email" bind:value={inviteEmail} placeholder="E-Mail" class="rounded-[10px] border border-hifi-border bg-hifi-surface p-2 text-sm text-hifi-text placeholder:text-hifi-text-faint" />
					<input type="password" bind:value={invitePassword} placeholder="Passwort (mind. 8 Zeichen)" class="rounded-[10px] border border-hifi-border bg-hifi-surface p-2 text-sm text-hifi-text placeholder:text-hifi-text-faint" />
					{#if inviteError}
						<p class="text-xs text-danger">{inviteError}</p>
					{/if}
					<div class="flex gap-2">
						<button on:click={inviteMember} class="rounded-[10px] bg-hifi-accent px-4 py-2 text-sm font-semibold text-white">
							Einladen
						</button>
						<button on:click={() => (inviting = false)} class="text-sm text-hifi-text-muted hover:text-hifi-text">
							Abbrechen
						</button>
					</div>
				</div>
			{:else}
				<button on:click={() => (inviting = true)} class="text-sm font-medium text-hifi-accent-text">
					+ Haushaltsmitglied einladen
				</button>
			{/if}
		{/if}
	</div>
{/if}
