<script lang="ts">
	export let name: string;
	export let isDefault: boolean;
</script>

<span
	class="inline-flex items-center rounded-full px-2.5 py-0.5 text-[11.5px] font-medium"
	class:bg-hifi-accent={isDefault}
	class:text-white={isDefault}
	class:bg-hifi-accent-tint={!isDefault}
	class:text-hifi-accent-text={!isDefault}
>
	{name}
</span>
