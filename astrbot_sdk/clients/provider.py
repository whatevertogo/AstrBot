"""Provider discovery and specialized-provider proxy client."""

from __future__ import annotations

from typing import Any

from ..llm.entities import ProviderMeta, ProviderType
from ..llm.providers import (
    ProviderProxy,
    STTProvider,
    TTSProvider,
    provider_proxy_from_meta,
)
from ._proxy import CapabilityProxy


class ProviderClient:
    def __init__(self, proxy: CapabilityProxy) -> None:
        self._proxy = proxy

    @staticmethod
    def _provider_meta_list(items: Any) -> list[ProviderMeta]:
        if not isinstance(items, list):
            return []
        providers: list[ProviderMeta] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            provider = ProviderMeta.from_payload(item)
            if provider is not None:
                providers.append(provider)
        return providers

    async def list_all(self) -> list[ProviderMeta]:
        output = await self._proxy.call("provider.list_all", {})
        return self._provider_meta_list(output.get("providers"))

    async def list_tts(self) -> list[ProviderMeta]:
        output = await self._proxy.call("provider.list_all_tts", {})
        return self._provider_meta_list(output.get("providers"))

    async def list_stt(self) -> list[ProviderMeta]:
        output = await self._proxy.call("provider.list_all_stt", {})
        return self._provider_meta_list(output.get("providers"))

    async def list_embedding(self) -> list[ProviderMeta]:
        output = await self._proxy.call("provider.list_all_embedding", {})
        return self._provider_meta_list(output.get("providers"))

    async def list_rerank(self) -> list[ProviderMeta]:
        output = await self._proxy.call("provider.list_all_rerank", {})
        return self._provider_meta_list(output.get("providers"))

    async def _get_tts_support_stream(self, provider_id: str) -> bool:
        output = await self._proxy.call(
            "provider.tts.support_stream",
            {"provider_id": str(provider_id)},
        )
        return bool(output.get("supported", False))

    async def _build_proxy(self, meta: ProviderMeta | None) -> ProviderProxy | None:
        if meta is None:
            return None
        tts_supports_stream = None
        if meta.provider_type == ProviderType.TEXT_TO_SPEECH:
            tts_supports_stream = await self._get_tts_support_stream(meta.id)
        return provider_proxy_from_meta(
            self._proxy,
            meta,
            tts_supports_stream=tts_supports_stream,
        )

    async def get(self, provider_id: str) -> ProviderProxy | None:
        output = await self._proxy.call(
            "provider.get_by_id",
            {"provider_id": str(provider_id)},
        )
        return await self._build_proxy(ProviderMeta.from_payload(output.get("provider")))

    async def get_using_chat(self, umo: str | None = None) -> ProviderMeta | None:
        output = await self._proxy.call("provider.get_using", {"umo": umo})
        return ProviderMeta.from_payload(output.get("provider"))

    async def get_using_tts(self, umo: str | None = None) -> TTSProvider | None:
        output = await self._proxy.call("provider.get_using_tts", {"umo": umo})
        provider = await self._build_proxy(ProviderMeta.from_payload(output.get("provider")))
        return provider if isinstance(provider, TTSProvider) else None

    async def get_using_stt(self, umo: str | None = None) -> STTProvider | None:
        output = await self._proxy.call("provider.get_using_stt", {"umo": umo})
        provider = await self._build_proxy(ProviderMeta.from_payload(output.get("provider")))
        return provider if isinstance(provider, STTProvider) else None


__all__ = ["ProviderClient"]
