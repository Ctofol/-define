from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.schemas import AssistantChatRequest, AssistantChatResponse, AssistantSource, SpeciesEntry
from app.services.species_service import SpeciesService, get_species_service
from app.settings import Settings, get_settings


class EcologyAssistantService:
    def __init__(self, species_service: SpeciesService | None = None, settings: Settings | None = None) -> None:
        self.species_service = species_service or get_species_service()
        self.settings = settings or get_settings()

    def chat(self, request: AssistantChatRequest) -> AssistantChatResponse:
        question = request.question.strip()
        if not question:
            return AssistantChatResponse(
                answer="请先输入一个和广西保护动植物、识别结果或物种特征有关的问题。",
                review_notice=self._review_notice(),
                suggested_questions=self._default_questions(),
            )

        species = self._find_species(question, request.context_species_id)
        if not species:
            return AssistantChatResponse(
                answer=(
                    "暂时没有在本地知识库中匹配到足够明确的物种。可以补充中文名、学名、保护等级、"
                    "识别画面中的关键特征，或先在知识库中选择一个物种后再追问。"
                ),
                review_notice=self._review_notice(),
                suggested_questions=self._default_questions(),
            )

        llm_answer = self._chat_with_llm(request, species)
        if llm_answer:
            primary = species[0]
            return AssistantChatResponse(
                answer=llm_answer,
                mode="llm_knowledge",
                review_notice=self._review_notice(),
                sources=[self._source_for(item, question) for item in species[:3]],
                suggested_questions=self._suggest_questions(primary),
            )

        primary = species[0]
        answer = self._build_answer(question, primary, species[1:3])
        return AssistantChatResponse(
            answer=answer,
            review_notice=self._review_notice(),
            sources=[self._source_for(item, question) for item in species[:3]],
            suggested_questions=self._suggest_questions(primary),
        )

    def _chat_with_llm(self, request: AssistantChatRequest, species: list[SpeciesEntry]) -> str | None:
        if not self.settings.llm_api_key.strip():
            return None

        context = "\n\n".join(self._species_context(entry) for entry in species[:5]) or "本次问题未匹配到明确物种，请基于生态监测常识保守回答。"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是广西动植物识别平台的生态知识助手。回答要面向巡护、监测和科普场景，"
                    "优先使用给定的本地物种知识库内容；涉及物种判定时必须提醒结合原图、地点、连续帧和人工复核。"
                    "不要把候选识别说成确定结论。回答使用简洁中文。"
                ),
            },
            {"role": "system", "content": f"本地知识库相关条目：\n{context}"},
            *[
                {"role": message.role, "content": message.content}
                for message in request.messages[-6:]
                if message.role in {"user", "assistant"} and message.content.strip()
            ],
            {"role": "user", "content": request.question.strip()},
        ]
        payload = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 900,
        }

        try:
            http_request = Request(
                self.settings.llm_base_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urlopen(http_request, timeout=self.settings.llm_timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None

        choices = response_payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str) and content.strip():
                return content.strip()
        return None

    def _species_context(self, species: SpeciesEntry) -> str:
        return "\n".join(
            [
                f"中文名：{species.cn_name}",
                f"学名：{species.latin_name or '暂无学名资料'}",
                f"分类：{' / '.join(part for part in [species.taxon_group, species.order, species.family, species.genus] if part)}",
                f"保护等级：{species.protection_level}",
                f"生境：{species.habitat}",
                f"习性：{species.habits}",
                f"食性：{species.diet}",
                f"识别特征：{'；'.join(species.features[:6])}",
                f"相似物种：{'、'.join(species.similar_species[:6])}",
                f"复核建议：{species.review_tips}",
            ]
        )

    def _find_species(self, question: str, context_species_id: str | None) -> list[SpeciesEntry]:
        entries = self.species_service.list_species()
        if context_species_id:
            context_entry = self.species_service.get_species(context_species_id)
            if context_entry:
                return [context_entry]

        query = question.lower()
        scored: list[tuple[int, SpeciesEntry]] = []
        for entry in entries:
            score = 0
            fields = [
                entry.cn_name,
                entry.latin_name or "",
                entry.category,
                entry.taxon_group or "",
                entry.order or "",
                entry.family or "",
                entry.genus or "",
                entry.protection_level,
                entry.habits,
                entry.diet,
                entry.habitat,
                entry.monitoring_value,
                entry.review_tips,
                " ".join(entry.features),
                " ".join(entry.similar_species),
                " ".join(entry.tags),
            ]
            for field in fields:
                value = field.lower()
                if value and value in query:
                    score += 6
                if value and query in value:
                    score += 4
            for token in self._tokens(query):
                if len(token) >= 2 and any(token in field.lower() for field in fields):
                    score += 1
            if score:
                scored.append((score, entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:5]]

    def _build_answer(self, question: str, species: SpeciesEntry, alternatives: list[SpeciesEntry]) -> str:
        sections = [
            f"{species.cn_name}（{species.latin_name or '学名待补充'}）属于{species.order or '目级信息待补充'}、{species.family or '科级信息待补充'}、{species.genus or '属级信息待补充'}。",
            f"保护等级：{species.protection_level}。主要生境：{species.habitat}",
        ]
        if species.features:
            sections.append(f"识别特征可优先看：{'；'.join(species.features[:4])}。")
        if species.habits:
            sections.append(f"习性：{species.habits}")
        if species.diet:
            sections.append(f"食性：{species.diet}")
        if species.similar_species:
            sections.append(f"容易混淆的对象包括：{'、'.join(species.similar_species[:5])}。")
        if alternatives:
            sections.append(f"本次问题还匹配到这些相关条目，可作为对照：{'、'.join(item.cn_name for item in alternatives)}。")
        if "复核" in question or "准确" in question or "是不是" in question:
            sections.append(f"复核建议：{species.review_tips}")
        return "\n".join(sections)

    def _source_for(self, species: SpeciesEntry, question: str) -> AssistantSource:
        matched_fields = []
        query = question.lower()
        field_map = {
            "中文名": species.cn_name,
            "学名": species.latin_name or "",
            "分类": " ".join(filter(None, [species.order, species.family, species.genus])),
            "保护等级": species.protection_level,
            "特征": " ".join(species.features),
            "生境": species.habitat,
            "习性": species.habits,
            "食性": species.diet,
        }
        for label, value in field_map.items():
            if value and (value.lower() in query or any(token in value.lower() for token in self._tokens(query))):
                matched_fields.append(label)
        return AssistantSource(
            species_id=species.species_id,
            cn_name=species.cn_name,
            latin_name=species.latin_name,
            protection_level=species.protection_level,
            matched_fields=matched_fields or ["知识库条目"],
        )

    def _suggest_questions(self, species: SpeciesEntry) -> list[str]:
        return [
            f"{species.cn_name}和相似物种怎么区分？",
            f"{species.cn_name}有哪些稳定识别特征？",
            f"识别到{species.cn_name}时应该怎么复核？",
        ]

    def _default_questions(self) -> list[str]:
        return [
            "大灵猫有哪些识别特征？",
            "黑熊和其他大型兽类怎么复核？",
            "识别结果置信度低时应该怎么处理？",
        ]

    def _review_notice(self) -> str:
        return "助手回答基于本地知识库生成；涉及物种判定时仍应结合原图、地点、连续帧和人工复核。"

    def _tokens(self, value: str) -> list[str]:
        return [token.strip(" ，。！？；;,.()（）") for token in value.split() if token.strip()]


def get_ecology_assistant_service() -> EcologyAssistantService:
    return EcologyAssistantService()
