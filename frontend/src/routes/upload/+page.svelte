<script lang="ts">
	import UploadFlow from '$lib/components/UploadFlow.svelte';
	import { goto } from '$app/navigation';
</script>

<h1 class="mb-6 text-xl font-semibold">Beleg hochladen</h1>

<UploadFlow onSuccess={() => goto('/receipts')} />
