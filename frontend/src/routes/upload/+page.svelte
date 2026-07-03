<script lang="ts">
	import { getOCRProvider } from '$lib/ocr';

	let selectedFile: File | null = null;
	let ocrProgress = 0;
	let uploadProgress = 0;
	let stage: 'idle' | 'ocr' | 'uploading' | 'done' | 'error' = 'idle';
	let errorMessage = '';

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		selectedFile = input.files?.[0] ?? null;
		stage = 'idle';
		ocrProgress = 0;
		uploadProgress = 0;
	}

	async function handleSubmit() {
		if (!selectedFile) return;
		errorMessage = '';

		try {
			// 1) OCR läuft on-device — das Originalbild verlässt das Gerät nie
			stage = 'ocr';
			const provider = await getOCRProvider();
			const { text, confidence } = await provider.recognize(selectedFile, (fraction) => {
				ocrProgress = Math.round(fraction * 100);
			});
			console.debug('OCR-Ergebnis (Konfidenz):', confidence, text.slice(0, 80));

			// 2) Datei-Upload an die API (nur die Datei selbst, kein OCR-Text-Body hier —
			//    Text-Verarbeitung/Tagging folgt in einem späteren KI-Paket)
			stage = 'uploading';
			const formData = new FormData();
			formData.append('file', selectedFile);
			// TODO: bucket_id kommt aus dem Bucket-Switcher, sobald der existiert (v0.2.0+ Buckets-Paket).
			// Bis dahin Platzhalter für den Default-Household-Bucket.
			formData.append('bucket_id', '');

			await uploadWithProgress(formData);

			stage = 'done';
		} catch (err) {
			stage = 'error';
			errorMessage = err instanceof Error ? err.message : 'Unbekannter Fehler beim Upload.';
		}
	}

	function uploadWithProgress(formData: FormData): Promise<void> {
		return new Promise((resolve, reject) => {
			const xhr = new XMLHttpRequest();
			xhr.open('POST', '/api/receipts/upload');
			xhr.withCredentials = true; // HTTP-Only Session-Cookie mitschicken

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

<h1 class="mb-6 text-xl font-semibold">Beleg hochladen</h1>

<div class="max-w-md rounded-lg border border-border bg-surface-raised p-6">
	<input
		type="file"
		accept="application/pdf,image/jpeg,image/png"
		on:change={handleFileSelect}
		class="mb-4 block w-full text-sm text-text-muted"
	/>

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
		disabled={!selectedFile || stage === 'ocr' || stage === 'uploading'}
		class="mt-4 rounded-lg bg-accent px-4 py-2 text-sm text-accent-contrast disabled:opacity-50"
	>
		Hochladen
	</button>
</div>
