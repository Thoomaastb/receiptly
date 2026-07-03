<script lang="ts">
	export let name: string;
	export let isDefault: boolean;
</script>

<span
	class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs"
	class:bg-bucket-household={isDefault}
	class:text-accent-contrast={isDefault}
	class:bg-surface-raised={!isDefault}
	class:text-text-muted={!isDefault}
	class:border={!isDefault}
	class:border-border={!isDefault}
>
	{name}
</span>
