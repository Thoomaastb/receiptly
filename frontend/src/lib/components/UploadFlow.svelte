<script lang="ts">
	import { onMount } from 'svelte';
	import { Capacitor } from '@capacitor/core';
	import { Camera } from '@capacitor/camera';
	import { getOCRProvider } from '$lib/ocr';
	import { extractHeuristics, type HeuristicResult } from '$lib/ocr/heuristics';
	import { autoCropEnabled } from '$lib/autoCrop';
	import { getEdgeDetectionProvider, type EdgeDetectionProvider, type Point } from '$lib/edge-detection';
	import { imageCorners, isPlausibleQuad } from '$lib/edge-detection/geometry';
	import { m } from '$lib/i18n';
	import CustomSelect from './CustomSelect.svelte';
	import ReceiptCropCorrector from './ReceiptCropCorrector.svelte';

	export let onSuccess: () => void = () => {};
	export let captureMode: 'camera' | 'file' = 'file';

	interface Bucket {
		id: string;
		name: string;
		type: string;
		visibility: string;
		is_default: boolean;
		access_level: 'owner' | 'edit' | 'view';
	}

	let selectedFile: File | null = null;
	// Rohbild direkt aus Kamera/Datei-Input, bevor die optionale Kantenerkennung/Zuschnitt-
	// Korrektur (siehe maybeStartCropDetection()) läuft. `selectedFile` bleibt die Variable,
	// die OCR/Upload tatsächlich verwenden -- wird erst gesetzt, wenn die Erkennung
	// abgeschlossen/übersprungen/fehlgeschlagen ist.
	let capturedFile: File | null = null;
	let detectedQuad: Point[] | null = null;
	// Dezenter, NICHT-blockierender Hinweis bei Fehlern in der Kantenerkennung selbst --
	// bewusst getrennt von errorMessage, das für echte Upload-Fehler reserviert bleibt.
	let cropDetectionNotice = '';
	let ocrProgress = 0;
	let uploadProgress = 0;
	let stage: 'idle' | 'detecting' | 'blurWarning' | 'cropping' | 'ocr' | 'uploading' | 'done' | 'error' = 'idle';
	let errorMessage = '';

	let buckets: Bucket[] = [];
	let hasReadOnlyBuckets = false;
	let selectedBucketId = '';
	let bucketsLoading = true;

	onMount(async () => {
		try {
			const res = await fetch('/api/buckets', { credentials: 'include' });
			if (!res.ok) throw new Error(`Buckets konnten nicht geladen werden (${res.status})`);
			const allBuckets: Bucket[] = await res.json();
			// Nur Buckets mit Schreibrecht anbieten — sonst würde der Upload erst nach
			// OCR/Fortschrittsanzeige mit einem generischen 403 scheitern (siehe
			// backend/app/api/receipts.py, access_level-Prüfung).
			buckets = allBuckets.filter((b) => b.access_level !== 'view');
			hasReadOnlyBuckets = buckets.length < allBuckets.length;
			selectedBucketId = buckets[0]?.id ?? '';
		} catch (err) {
			errorMessage = err instanceof Error ? err.message : 'Buckets konnten nicht geladen werden.';
		} finally {
			bucketsLoading = false;
		}
	});

	function resetCaptureState() {
		selectedFile = null;
		detectedQuad = null;
		cropDetectionNotice = '';
		stage = 'idle';
		ocrProgress = 0;
		uploadProgress = 0;
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		capturedFile = input.files?.[0] ?? null;
		resetCaptureState();
		if (capturedFile) void maybeStartCropDetection();
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
			capturedFile = new File([blob], `scan-${Date.now()}.jpg`, { type: blob.type || 'image/jpeg' });
			resetCaptureState();
			await maybeStartCropDetection();
		} catch (err) {
			// Nutzer hat z.B. den Kamera-Dialog abgebrochen — kein Fehler-UI dafür nötig
			if (err instanceof Error && !err.message.toLowerCase().includes('cancel')) {
				errorMessage = 'Kamera konnte nicht geöffnet werden: ' + err.message;
			}
		}
	}

	// Auto-Crop-Einstiegspunkt nach jeder neuen Aufnahme (Kamera oder Datei-Input). Läuft
	// nur, wenn die Einstellung aktiv ist und es sich nicht um ein PDF handelt (Kanten-
	// erkennung/Unschärfe-Check ergeben für PDFs keinen Sinn). Bei ausgeschalteter
	// Einstellung oder PDF bleibt das Verhalten 1:1 wie vor diesem Feature.
	async function maybeStartCropDetection() {
		if (!capturedFile) return;

		if (!$autoCropEnabled || capturedFile.type === 'application/pdf') {
			selectedFile = capturedFile;
			stage = 'idle';
			return;
		}

		stage = 'detecting';
		cropDetectionNotice = '';
		try {
			const provider = await getEdgeDetectionProvider();

			const blurBitmap = await createImageBitmap(capturedFile, { imageOrientation: 'from-image' });
			let blur;
			try {
				blur = await provider.detectBlur(blurBitmap);
			} finally {
				blurBitmap.close();
			}

			if (blur.isBlurry) {
				// Nicht blockierend: Nutzer entscheidet zwischen Neu-Aufnahme und Weiterverwenden
				// (siehe useBlurryPhotoAnyway()/retakePhoto()) -- die eigentliche Kantenerkennung
				// läuft erst danach.
				stage = 'blurWarning';
				return;
			}

			await runEdgeDetectionAndShowCropper(provider);
		} catch (err) {
			console.error('Kantenerkennung fehlgeschlagen:', err);
			skipCropDetectionAfterFailure();
		}
	}

	async function runEdgeDetectionAndShowCropper(provider: EdgeDetectionProvider) {
		if (!capturedFile) return;
		const bitmap = await createImageBitmap(capturedFile, { imageOrientation: 'from-image' });
		try {
			const rawQuad = await provider.detectEdges(bitmap);
			detectedQuad =
				rawQuad && isPlausibleQuad(rawQuad, bitmap.width, bitmap.height)
					? rawQuad
					: imageCorners(bitmap.width, bitmap.height);
			stage = 'cropping';
		} finally {
			bitmap.close();
		}
	}

	function skipCropDetectionAfterFailure() {
		cropDetectionNotice = m.upload.cropDetectionUnavailable;
		selectedFile = capturedFile;
		stage = 'idle';
	}

	function retakePhoto() {
		capturedFile = null;
		resetCaptureState();
	}

	async function useBlurryPhotoAnyway() {
		stage = 'detecting';
		try {
			const provider = await getEdgeDetectionProvider();
			await runEdgeDetectionAndShowCropper(provider);
		} catch (err) {
			console.error('Kantenerkennung fehlgeschlagen:', err);
			skipCropDetectionAfterFailure();
		}
	}

	function handleCropConfirm(event: CustomEvent<File>) {
		selectedFile = event.detail;
		stage = 'idle';
	}

	function handleCropCancel() {
		selectedFile = capturedFile;
		stage = 'idle';
	}

	async function handleSubmit() {
		if (!selectedFile || !selectedBucketId) return;
		errorMessage = '';

		try {
			let ocrText: string | null = null;
			let ocrConfidence: number | null = null;
			let heuristics: HeuristicResult | null = null;

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
				heuristics = extractHeuristics(ocrText);
				stage = 'uploading';
			}

			const formData = new FormData();
			formData.append('file', selectedFile);
			formData.append('bucket_id', selectedBucketId);
			if (ocrText !== null) formData.append('ocr_text', ocrText);
			if (ocrConfidence !== null) formData.append('ocr_confidence', String(ocrConfidence));
			if (heuristics?.receiptDate) formData.append('heuristic_receipt_date', heuristics.receiptDate);
			if (heuristics?.totalAmount !== null && heuristics?.totalAmount !== undefined) {
				formData.append('heuristic_total_amount', String(heuristics.totalAmount));
			}
			if (heuristics?.currency) formData.append('heuristic_currency', heuristics.currency);

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
		<p class="mb-4 text-sm text-danger">
			{hasReadOnlyBuckets
				? 'Kein Bucket mit Schreibrecht verfügbar — du hast auf alle sichtbaren Buckets nur Lesezugriff.'
				: 'Kein Bucket verfügbar — bitte einloggen.'}
		</p>
	{/if}

	{#if stage !== 'cropping'}
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
	{/if}

	{#if stage === 'cropping' && capturedFile}
		<ReceiptCropCorrector
			image={capturedFile}
			initialQuad={detectedQuad ?? []}
			on:confirm={handleCropConfirm}
			on:cancel={handleCropCancel}
		/>
	{:else}
		{#if selectedFile}
			<p class="mb-4 text-sm text-hifi-text-muted">Gewählt: {selectedFile.name}</p>
			{#if selectedFile.type === 'application/pdf'}
				<p class="mb-4 text-xs text-hifi-text-muted">
					Texterkennung für PDFs läuft nach dem Hochladen automatisch auf dem Server.
				</p>
			{/if}
		{/if}

		{#if stage === 'detecting'}
			<p class="mb-2 text-sm text-hifi-text-muted">{m.upload.detecting}</p>
			<div class="h-2 overflow-hidden rounded-full bg-hifi-border">
				<div class="h-2 w-1/3 animate-pulse rounded-full bg-hifi-accent"></div>
			</div>
		{:else if stage === 'blurWarning'}
			<div class="mb-4 rounded-[10px] border border-status-warning-border bg-status-warning-bg p-3">
				<p class="mb-3 text-sm text-status-warning">{m.upload.blurWarningMessage}</p>
				<div class="flex flex-wrap gap-2">
					<button
						type="button"
						on:click={retakePhoto}
						class="rounded-[8px] border border-hifi-border px-3 py-1.5 text-[13px] font-medium text-hifi-text"
					>
						{m.upload.blurRetakeButton}
					</button>
					<button
						type="button"
						on:click={useBlurryPhotoAnyway}
						class="rounded-[8px] bg-hifi-accent px-3 py-1.5 text-[13px] font-medium text-white"
					>
						{m.upload.blurUseAnywayButton}
					</button>
				</div>
			</div>
		{:else if stage === 'ocr'}
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

		{#if cropDetectionNotice}
			<p class="mb-4 text-xs text-hifi-text-muted">{cropDetectionNotice}</p>
		{/if}

		<button
			on:click={handleSubmit}
			disabled={!selectedFile || !selectedBucketId || stage === 'ocr' || stage === 'uploading' || stage === 'detecting' || stage === 'blurWarning'}
			class="mt-4 w-full rounded-[10px] bg-hifi-accent px-4 py-2 text-sm text-white disabled:opacity-50"
		>
			Hochladen
		</button>
	{/if}
</div>
