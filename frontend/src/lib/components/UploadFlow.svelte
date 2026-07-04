<script lang="ts">
	import { onMount } from 'svelte';
	import { getOCRProvider } from '$lib/ocr';

	export let onSuccess: () => void = () => {};
	export let captureMode: 'camera' | 'file' = 'file';

	interface Bucket {
		id: string;
		name: string;
		type: string;
		visibility: string;
		is_default: boolean;
	}

	let selectedFile: File | null = null;
	let ocrProgress = 0;
	let uploadProgress = 0;
	let stage: 'idle' | 'ocr' | 'uploading' | 'done' | 'error' = 'idle';
	let errorMessage = '';

	let buckets: Bucket[] = [];
	let selectedBucketId = '';
	let bucketsLoading = true;

	onMount(async () => {
		try {
			const res = await fetch('/api/buckets', { credentials: 'include' });
			if (!res.ok) throw new Error(`Buckets konnten nicht geladen werden (${res.status})`);
			buckets = await res.json();
			selectedBucketId = buckets[0]?.id ?? '';
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Buckets konnten nicht geladen werden.';
		} finally {
			bucketsLoading = false;
		}
	});

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		selectedFile = input.files?.[0] ?? null;
		stage = 'idle';
		ocrProgress = 0;
		uploadProgress = 0;
	}

	async function handleSubmit() {
		if (!selectedFile || !selectedBucketId) return;
		errorMessage = '';

		try {
			stage = 'ocr';
			const provider = await getOCRProvider();
			const { text: ocrText, confidence: ocrConfidence } = await provider.recognize(
				selectedFile,
				(fraction) => {
					ocrProgress = Math.round(fraction * 100);
				}
			);

			stage = 'uploading';
			const formData = new FormData();
			formData.append('file', selectedFile);
			formData.append('bucket_id', selectedBucketId);
			formData.append('ocr_text', ocrText);
			formData.append('ocr_confidence', String(ocrConfidence));

			await uploadWithProgress(formData);

			stage = 'done';
			// Kurze Bestätigung sichtbar lassen, dann Aufrufer benachrichtigen
			// (Modal schließt sich, Listen aktualisieren sich — "on-the-fly")
			setTimeout(onSuccess, 900);
		} catch (err) {
			stage = 'error';
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler beim Upload.';
		}
	}

	function uploadWithProgress(formData: FormData): Promise<void> {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			xhr.open('POST', '/api/receipts/upload');
			xhr.withCredentials = true;

			xhr.upload.onprogress = (event) => {
				if (event.lengthComputable) {
					uploadProgress = Math.round((event.loaded / event.total) * 100);
				}
			};
			xhr.onload = () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					resolve();
				} else {
					reject(new Error(`Upload fehlgeschlagen (${xhr.status})`));
				}
			};
			xhr.onerror = () => reject(new Error('Netzwerkfehler beim Upload.'));
			xhr.send(formData);
		});
	}
</script>

<div class="max-w-md rounded-lg border border-border bg-surface-raised p-6">
	{#if bucketsLoading}
		<p class="mb-4 text-sm text-text-muted">Buckets werden geladen …</p>
	{:else if buckets.length > 1}
		<label class="mb-4 block text-sm">
			<span class="mb-1 block text-text-muted">Bucket</span>
			<select bind:value={selectedBucketId} class="w-full rounded border border-border bg-surface p-2">
				{#each buckets as bucket (bucket.id)}
					<option value={bucket.id}>{bucket.name}{bucket.is_default ? ' (Haushalt)' : ''}</option>
				{/each}
			</select>
		</label>
	{:else if buckets.length === 1}
		<p class="mb-4 text-sm text-text-muted">Bucket: {buckets[0].name}</p>
	{:else if !errorMessage}
		<p class="mb-4 text-sm text-red-500">Kein Bucket verfügbar — bitte einloggen.</p>
	{/if}

	<input
		type="file"
		accept="application/pdf,image/jpeg,image/png"
		capture={captureMode === 'camera' ? 'environment' : undefined}
		on:change={handleFileSelect}
		class="mb-4 block w-full text-sm text-text-muted"
	/>
	{#if captureMode === 'camera'}
		<p class="mb-4 text-xs text-text-muted">
			Öffnet auf dem Smartphone direkt die Kamera. Auf dem Desktop erscheint stattdessen der
			normale Datei-Dialog (Browser-Einschränkung, kein Bug).
		</p>
	{/if}

	{#if selectedFile}
		<p class="mb-4 text-sm text-text-muted">Gewählt: {selectedFile.name}</p>
	{/if}

	{#if stage === 'ocr'}
		<p class="mb-2 text-sm">Texterkennung läuft (on-device) … {ocrProgress}%</p>
		<div class="h-2 rounded-full bg-border">
			<div class="h-2 rounded-full bg-accent" style="width: {ocrProgress}%"></div>
		</div>
	{:else if stage === 'uploading'}
		<p class="mb-2 text-sm">Hochladen … {uploadProgress}%</p>
		<div class="h-2 rounded-full bg-border">
			<div class="h-2 rounded-full bg-accent" style="width: {uploadProgress}%"></div>
		</div>
	{:else if stage === 'done'}
		<p class="text-sm text-accent">Beleg erfolgreich hochgeladen.</p>
	{:else if stage === 'error'}
		<p class="text-sm text-red-500">{errorMessage}</p>
	{/if}

	<button
		on:click={handleSubmit}
		disabled={!selectedFile || !selectedBucketId || stage === 'ocr' || stage === 'uploading'}
		class="mt-4 rounded-lg bg-accent px-4 py-2 text-sm text-accent-contrast disabled:opacity-50"
	>
		Hochladen
	</button>
</div>
