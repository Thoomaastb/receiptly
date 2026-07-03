export interface OCRResult {
	text: string;
	confidence: number; // 0.0 – 1.0
}

export interface OCRProvider {
	readonly name: string;
	isAvailable(): Promise<boolean>;
	recognize(file: File, onProgress?: (fraction: number) => void): Promise<OCRResult>;
}
