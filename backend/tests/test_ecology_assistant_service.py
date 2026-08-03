from app.schemas import AssistantChatRequest
from app.services.ecology_assistant_service import EcologyAssistantService


def test_ecology_assistant_answers_from_species_knowledge():
    response = EcologyAssistantService().chat(AssistantChatRequest(question="大灵猫有哪些识别特征？"))

    assert "大灵猫" in response.answer
    assert response.sources
    assert response.sources[0].cn_name == "大灵猫"
    assert response.review_notice


def test_ecology_assistant_keeps_unknown_questions_conservative():
    response = EcologyAssistantService().chat(AssistantChatRequest(question="这张完全看不清的图片是什么？"))

    assert "暂时没有" in response.answer
    assert response.sources == []
    assert response.suggested_questions
