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

	let buckets: Bucket[] = [];
	let currentUserId = '';
	let query = '';
	let loading = true;
	let errorMessage = '';

	let creating = false;
	let newBucketName = '';

	onMount(async () => {
		try {
			const [meRes, bucketsRes] = await Promise.all([
				fetch('/api/auth/me', { credentials: 'include' }),
				fetch('/api/buckets', { credentials: 'include' })
			]);
			if (meRes.ok) currentUserId = (await meRes.json()).id;
			if (!bucketsRes.ok) throw new Error(`Buckets konnten nicht geladen werden (${bucketsRes.status})`);
			buckets = await bucketsRes.json();
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler.';
		} finally {
			loading = false;
		}
	});

	$: filteredBuckets = buckets.filter((b) => b.name.toLowerCase().includes(query.toLowerCase()));

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

	function openBucket(bucket: Bucket) {
		goto(`/receipts?bucket=${bucket.id}`);
	}
</script>

<h1 class="mb-6 text-xl font-semibold">Buckets</h1>

<div class="relative mb-5 max-w-md">
	<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" aria-hidden="true">
		<circle cx="11" cy="11" r="7" />
		<path d="M21 21l-4.3-4.3" stroke-linecap="round" />
	</svg>
	<input
		type="text"
		bind:value={query}
		placeholder="Buckets durchsuchen"
		class="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm"
	/>
</div>

{#if loading}
	<p class="text-sm text-text-muted">Wird geladen …</p>
{:else if errorMessage}
	<p class="text-sm text-red-500">{errorMessage}</p>
{:else}
	<ul class="mb-5 flex max-w-md flex-col gap-2">
		{#each filteredBuckets as bucket (bucket.id)}
			<li class="flex items-center gap-3 rounded-lg border border-border bg-surface-raised p-3">
				<button on:click={() => openBucket(bucket)} class="flex flex-1 items-center gap-3 text-left">
					<span
						class="h-2.5 w-2.5 flex-none rounded-full"
						style="background: {bucket.is_default ? 'var(--color-bucket-household)' : 'var(--color-accent)'}"
					></span>
					<span class="flex-1">
						<span class="block text-sm font-medium">{bucket.name}</span>
						{#if bucket.visibility === 'private' && bucket.owner_id !== currentUserId}
							<span class="block text-xs text-text-muted">Nur Ansicht</span>
						{/if}
					</span>
					{#if bucket.visibility === 'private'}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-text-muted" aria-hidden="true">
							<rect x="5" y="11" width="14" height="10" rx="1" />
							<path d="M8 11V7a4 4 0 018 0v4" />
						</svg>
					{/if}
				</button>
				{#if !bucket.is_default && bucket.owner_id === currentUserId}
					<button
						on:click={() => togglePrivate(bucket)}
						class="text-xs text-text-muted transition-colors hover:text-text"
						title={bucket.visibility === 'private' ? 'Auf transparent umschalten' : 'Auf privat umschalten'}
					>
						{bucket.visibility === 'private' ? 'Privat' : 'Transparent'}
					</button>
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
				class="flex-1 rounded-lg border border-border bg-surface p-2 text-sm"
				on:keydown={(e) => e.key === 'Enter' && createBucket()}
			/>
			<button on:click={createBucket} class="rounded-lg bg-accent px-4 py-2 text-sm text-accent-contrast">
				Anlegen
			</button>
		</div>
	{:else}
		<button on:click={() => (creating = true)} class="text-sm font-medium text-accent">
			+ Eigenen Bucket anlegen
		</button>
	{/if}

	<p class="mt-6 max-w-md text-xs text-text-muted">
		Weitere Haushaltsmitglieder (z. B. ein „Nur Ansicht"-Bucket einer anderen Person) erscheinen
		hier automatisch, sobald die Einladungsfunktion für zusätzliche Nutzer existiert.
	</p>
{/if}
