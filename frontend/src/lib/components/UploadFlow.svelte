<script lang="ts">
	import { onMount } from 'svelte';
	import { Capacitor } from '@capacitor/core';
	import { Camera } from '@capacitor/camera';
	import { getOCRProvider } from '$lib/ocr';
	import CustomSelect from './CustomSelect.svelte';

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

	const isNativeApp = Capacitor.isNativePlatform();

	async function openNativeCamera() {
		errorMessage = '';
		try {
			const result = await Camera.takePhoto({
				quality: 90,
				saveToGallery: false,
				correctOrientation: true
			});
			if (!result.webPath) throw new Error('Kein Foto erhalten.');
			const blob = await (await fetch(result.webPath)).blob();
			selectedFile = new File([blob], `scan-${Date.now()}.jpg`, { type: blob.type || 'image/jpeg' });
			stage = 'idle';
			ocrProgress = 0;
			uploadProgress = 0;
		} catch (err) {
			// Nutzer hat z.B. den Kamera-Dialog abgebrochen — kein Fehler-UI dafür nötig
			if (err instanceof Error && !err.message.toLowerCase().includes('cancel')) {
				errorMessage = 'Kamera konnte nicht geöffnet werden: ' + err.message;
			}
		}
	}

	async function handleSubmit() {
		if (!selectedFile || !selectedBucketId) return;
		errorMessage = '';

		try {
			let ocrText: string | null = null;
			let ocrConfidence: number | null = null;

			if (selectedFile.type === 'application/pdf') {
				// TesseractJS kann nur Rasterbilder dekodieren, keine PDFs — der Versuch ließ den
				// Upload bisher schon im OCR-Schritt mit einer irreführenden "Upload fehlgeschlagen"-
				// Meldung abbrechen, bevor die Datei überhaupt gesendet wurde. OCR hier bewusst
				// überspringen statt den Upload daran scheitern zu lassen.
				stage = 'uploading';
			} else {
				stage = 'ocr';
				const provider = await getOCRProvider();
				const result = await provider.recognize(selectedFile, (fraction) => {
					ocrProgress = Math.round(fraction * 100);
				});
				ocrText = result.text;
				ocrConfidence = result.confidence;
				stage = 'uploading';
			}

			const formData = new FormData();
			formData.append('file', selectedFile);
			formData.append('bucket_id', selectedBucketId);
			if (ocrText !== null) formData.append('ocr_text', ocrText);
			if (ocrConfidence !== null) formData.append('ocr_confidence', String(ocrConfidence));

			await uploadWithProgress(formData);

			stage = 'done';
			// Kurze Bestätigung sichtbar lassen, dann Aufrufer benachrichtigen
			// (Modal schließt sich, Listen aktualisieren sich — "on-the-fly")
			setTimeout(onSuccess, 900);
		} catch (err) {
			stage = 'error';
			console.error('Upload fehlgeschlagen:', err);
			errorMessage = err instanceof Error ? err.message : `Unbekannter Fehler beim Upload: ${String(err)}`;
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

<div class="w-full max-w-2xl rounded-[14px] border border-hifi-border bg-hifi-surface p-6">
	{#if bucketsLoading}
		<p class="mb-4 text-sm text-hifi-text-muted">Buckets werden geladen …</p>
	{:else if buckets.length > 1}
		<div class="mb-4">
			<span id="bucket-select-label" class="mb-1 block text-sm text-hifi-text-muted">Bucket</span>
			<CustomSelect
				bind:value={selectedBucketId}
				labelledBy="bucket-select-label"
				options={buckets.map((b) => ({ value: b.id, label: b.name + (b.is_default ? ' (Haushalt)' : '') }))}
			/>
		</div>
	{:else if buckets.length === 1}
		<p class="mb-4 text-sm text-hifi-text-muted">Bucket: {buckets[0].name}</p>
	{:else if !errorMessage}
		<p class="mb-4 text-sm text-danger">Kein Bucket verfügbar — bitte einloggen.</p>
	{/if}

	{#if isNativeApp && captureMode === 'camera'}
		<button
			on:click={openNativeCamera}
			class="mb-4 flex w-full items-center justify-center gap-2 rounded-[10px] border border-hifi-border bg-hifi-surface py-3 text-sm font-medium"
		>
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<rect x="3" y="7" width="18" height="13" rx="2" />
				<circle cx="12" cy="13.5" r="3.5" />
			</svg>
			Kamera öffnen
		</button>
	{:else}
		<label
			class="mb-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-[10px] border border-hifi-border bg-hifi-surface py-3 text-sm font-medium transition-colors hover:bg-hifi-accent-tint hover:text-hifi-accent-text"
		>
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M12 16V4M8 8l4-4 4 4" />
				<path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3" />
			</svg>
			{selectedFile ? 'Andere Datei wählen' : 'Datei auswählen'}
			<input
				type="file"
				accept={captureMode === 'camera' ? 'image/*' : 'application/pdf,image/jpeg,image/png'}
				capture={captureMode === 'camera' ? 'environment' : undefined}
				on:change={handleFileSelect}
				class="sr-only"
			/>
		</label>
	{/if}
	{#if captureMode === 'camera'}
		<p class="mb-4 text-xs text-hifi-text-muted">
			{#if isNativeApp}
				Öffnet die native Kamera-App direkt.
			{:else}
				Öffnet auf dem Smartphone-Browser die Kamera. PDFs sind im Scan-Modus bewusst
				ausgeschlossen — ein Dateityp ohne Kamerabezug im accept-Attribut lässt Browser laut
				Spezifikation das gesamte capture-Verhalten ignorieren. Für PDFs bitte „Hochladen" nutzen.
			{/if}
		</p>
	{/if}

	{#if selectedFile}
		<p class="mb-4 text-sm text-hifi-text-muted">Gewählt: {selectedFile.name}</p>
		{#if selectedFile.type === 'application/pdf'}
			<p class="mb-4 text-xs text-hifi-text-muted">
				Texterkennung für PDFs läuft nach dem Hochladen automatisch auf dem Server.
			</p>
		{/if}
	{/if}

	{#if stage === 'ocr'}
		<p class="mb-2 text-sm">Texterkennung läuft (on-device) … {ocrProgress}%</p>
		<div class="h-2 rounded-full bg-hifi-border">
			<div class="h-2 rounded-full bg-hifi-accent" style="width: {ocrProgress}%"></div>
		</div>
	{:else if stage === 'uploading'}
		<p class="mb-2 text-sm">Hochladen … {uploadProgress}%</p>
		<div class="h-2 rounded-full bg-hifi-border">
			<div class="h-2 rounded-full bg-hifi-accent" style="width: {uploadProgress}%"></div>
		</div>
	{:else if stage === 'done'}
		<p class="text-sm text-hifi-accent-text">Beleg erfolgreich hochgeladen.</p>
	{:else if stage === 'error'}
		<p class="text-sm text-danger">{errorMessage}</p>
	{/if}

	<button
		on:click={handleSubmit}
		disabled={!selectedFile || !selectedBucketId || stage === 'ocr' || stage === 'uploading'}
		class="mt-4 w-full rounded-[10px] bg-hifi-accent px-4 py-2 text-sm text-white disabled:opacity-50"
	>
		Hochladen
	</button>
</div>
