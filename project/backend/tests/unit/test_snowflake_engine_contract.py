from .service_contract_helpers import load_module, require_async_method, require_class


def _get_topone_gateway_class():
    module = load_module("app.llm.topone_gateway")
    return require_class(module, "ToponeGateway")


def _get_llm_engine_class():
    module = load_module("app.services.llm_engine")
    return require_class(module, "LLMEngine")


def _get_local_story_engine_class():
    module = load_module("app.services.llm_engine")
    return require_class(module, "LocalStoryEngine")


def test_topone_gateway_has_generate_act_list():
    gateway_cls = _get_topone_gateway_class()
    require_async_method(gateway_cls, "generate_act_list")


def test_topone_gateway_has_generate_chapter_list():
    gateway_cls = _get_topone_gateway_class()
    require_async_method(gateway_cls, "generate_chapter_list")


def test_topone_gateway_has_generate_story_anchors():
    gateway_cls = _get_topone_gateway_class()
    require_async_method(gateway_cls, "generate_story_anchors")


def test_llm_engine_has_step5_methods():
    engine_cls = _get_llm_engine_class()
    for name in (
        "generate_act_list",
        "generate_chapter_list",
        "generate_story_anchors",
    ):
        require_async_method(engine_cls, name)


def test_local_story_engine_has_step5_methods():
    engine_cls = _get_local_story_engine_class()
    for name in (
        "generate_act_list",
        "generate_chapter_list",
        "generate_story_anchors",
    ):
        require_async_method(engine_cls, name)
