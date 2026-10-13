from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from openai import OpenAI
import logging
import os

logger = logging.getLogger(__name__)

DASHSCOPE_MODEL_VERSIONS = frozenset({"qwen3-max", "qwen-plus", "Fine_Model"})


class VLLMRequestModel(BaseModel):
    """vLLM代理模型请求模型"""
    messages: List[dict]
    # 模型
    model: str
    # 模型版本
    version: str
    # 创造性比例（0 - 1 值越低生成数据越可靠，值越高生成数据越富有创造力）
    temperature: float
    # 最大token数量
    num_predict: int
    # 是否流式生成
    stream: bool
    # 是否思考模型
    think_through: bool = False
    # Qwen3.8 思考深度：仅 think_through=True 且 version=qwen38-27b-fp8 时生效；未传默认 low
    reasoning_effort: Optional[str] = None
    # Qwen3.8 是否保留思考；开思考时未传默认 True；关思考时不发给上游
    preserve_thinking: Optional[bool] = None
    # 额外参数（如lora_module等）
    extra_params: Optional[dict] = None


def _get_dashscope_api_key() -> str:
    """获取百炼API Key，优先从环境变量读取"""
    # 首先尝试直接读取环境变量
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if api_key:
        return api_key

    # 如果环境变量没有，尝试从 common_config 读取
    try:
        from common.app.config.config import common_config
        # 尝试多个可能的环境变量名
        api_key = os.getenv("TONGYI_WANXIANG_API_KEY", "")
        if api_key:
            return api_key
    except Exception:
        pass

    return ""


# local 环境直连公网 GPU 机器，其他环境（sit/uat/dev/prod）走内网 192.168.22.9
# 通过 .env.* 中的 VLLM_BASE_HOST 控制，local 不设则使用默认公网地址
_VLLM_BASE_HOST: str = os.getenv("VLLM_BASE_HOST", "183.252.196.135")
_VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "")


def _vllm_url(port: int) -> str:
    return f"http://{_VLLM_BASE_HOST}:{port}/v1"


# 开启 VLLM_FORCE_BAILIAN 后，这些自建 version 的出站客户端改打 debug_Model
_FORCE_BAILIAN_VERSIONS = frozenset(
    {
        "qwen35-35b-GPTQ-Int4",
        "qwen35-35b-fp8",
        "qwen35-35b",
        "Ubao-Model",
        "UbaoModel",
    }
)
_FORCE_BAILIAN_TARGET = "debug_Model"


def _vllm_force_bailian_enabled() -> bool:
    """是否强制把自建 35B/Ubao 流量切到百炼 MaaS debug_Model。"""
    return os.getenv("VLLM_FORCE_BAILIAN", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def resolve_vllm_runtime_version(model_version: str) -> str:
    """业务 version 保持不变；出站时按开关解析真实配置 key。"""
    if _vllm_force_bailian_enabled() and model_version in _FORCE_BAILIAN_VERSIONS:
        return _FORCE_BAILIAN_TARGET
    return model_version


# 模型配置 - 端口号不变，host 由 VLLM_BASE_HOST 环境变量控制
VLLM_MODELS_CONFIG = {
    "qwen35-35b-GPTQ-Int4": {
        "base_url": _vllm_url(7871),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3.5-35B-int4"
    },
    "qwen35-35b-fp8": {
        "base_url": _vllm_url(7874),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3.5-35B-int4"
    },
    # Qwen3.5-35b
    "qwen35-35b": {
        "base_url": _vllm_url(7861),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3.5-35B",
    },
    # 思考模式：非 think_through 调用由 vllm_proxy_service.THINKING_CAPABLE_VERSIONS 注入 extra_body 关闭
    "Ubao-Model": {
        "base_url": _vllm_url(7880),
        "api_key": _VLLM_API_KEY,
        "model_name": "UbaoModel",
    },
    # Qwen3.8-27B-FP8（端口 7880，served-model-name: Qwen3.8-27B-fp8；默认关思考）
    "qwen38-27b-fp8": {
        "base_url": _vllm_url(7880),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3.8-27B-fp8",
    },
    "UbaoModel": {
        "base_url": _vllm_url(7879),
        "api_key": _VLLM_API_KEY,
        "model_name": "UbaoModel"
    },
    # 模型下线
    # "qwen4b": {
    #     "base_url": _vllm_url(7861),
    #     "api_key": _VLLM_API_KEY,
    #     "model_name": "Qwen3-4B"
    # },
    "qwen-vl": {
        "base_url": _vllm_url(7872),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3-VL-8B-Thinking"
    },
    # MiniCPM-V-4.6 SGLang 部署（端口 7880；调用时需带 top_k=-1 与 stop_token_ids，见 vllm_minicpm_v_46）
    "minicpm-v-4.6": {
        "base_url": _vllm_url(7880),
        "api_key": _VLLM_API_KEY,
        "model_name": "MiniCPM-V-4.6",
    },
    "qwen3-max": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": _get_dashscope_api_key(),
        "model_name": "qwen3.7-max"
    },
    "qwen-plus": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": _get_dashscope_api_key(),
        "model_name": "qwen-plus"
    },
    "ds-ocr": {
        "base_url": _vllm_url(7865),
        "api_key": _VLLM_API_KEY,
        "model_name": "deepseek-ai/DeepSeek-OCR"
    },
    "embedding": {
        "base_url": _vllm_url(7863),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3-Embedding"
    },
    "Fine_Model": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": _get_dashscope_api_key(),
        "model_name": "qwen3.6-plus"
    },
    # 百炼 MaaS 调试入口；VLLM_FORCE_BAILIAN=1 时，自建 35B/Ubao 强制改打此配置
    "debug_Model": {
        "base_url": "https://llm-ncoi8jnlo55zdfof.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "api_key": os.getenv("DEBUG_MODEL_API_KEY", ""),
        "model_name": "qwen3.8-27b",
    },
    # Qwen3-VL-Embedding（端口 7873，served-model-name: Qwen3-VL-Embedding）
    "qwen3-vl-embedding": {
        "base_url": _vllm_url(7873),
        "api_key": _VLLM_API_KEY,
        "model_name": "Qwen3-VL-Embedding",
    },
    # "rerank": {
    #     "base_url": _vllm_url(7867),
    #     "api_key": _VLLM_API_KEY,
    #     "model_name": "Qwen3-Reranker-8B"
    # }
}


class VLLMModelClient:
    """vLLM模型客户端类 - 直接连接各个模型服务器"""

    def __init__(self):
        """初始化vLLM模型客户端"""
        self.clients_cache: Dict[str, OpenAI] = {}

    def _get_api_key(self, model_version: str) -> str:
        """
        获取指定模型的API Key
        对于百炼模型，支持动态从环境变量读取
        """
        if model_version in DASHSCOPE_MODEL_VERSIONS:
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            if api_key:
                return api_key
            api_key = os.getenv("TONGYI_WANXIANG_API_KEY", "")
            if api_key:
                return api_key
            return VLLM_MODELS_CONFIG[model_version]["api_key"]
        return VLLM_MODELS_CONFIG[model_version]["api_key"]

    def get_client(self, model_version: str) -> OpenAI:
        """
        获取指定模型版本的OpenAI客户端

        Args:
            model_version: 模型版本（如 "qwen32b", "qwen35b", "qwen-vl", "ds-ocr", "embedding", "rerank", "qwen3-max"）

        Returns:
            OpenAI: 配置好的OpenAI客户端

        Raises:
            ValueError: 当模型版本不支持时
        """
        if model_version not in VLLM_MODELS_CONFIG:
            raise ValueError(f"不支持的模型版本: {model_version}")

        model_version = resolve_vllm_runtime_version(model_version)

        # 对于百炼模型，每次都重新获取 API Key（支持动态配置）
        if model_version in DASHSCOPE_MODEL_VERSIONS:
            api_key = self._get_api_key(model_version)
            if not api_key:
                raise ValueError(
                    f"百炼模型 {model_version} 需要提供 API Key，请设置 DASHSCOPE_API_KEY 或 TONGYI_WANXIANG_API_KEY 环境变量")
            config = VLLM_MODELS_CONFIG[model_version]
            try:
                client = OpenAI(base_url=config["base_url"], api_key=api_key)
                logger.info(f"初始化百炼模型客户端: {model_version}, base_url: {config['base_url']}")
                return client
            except Exception as e:
                logger.error(f"初始化百炼模型客户端失败: {str(e)}")
                raise

        # 本地 vLLM 模型使用缓存
        if model_version in self.clients_cache:
            return self.clients_cache[model_version]

        config = VLLM_MODELS_CONFIG[model_version]

        try:
            client = OpenAI(
                base_url=config["base_url"],
                api_key=config["api_key"]
            )

            self.clients_cache[model_version] = client
            logger.info(f"初始化vLLM模型客户端: {model_version}, base_url: {config['base_url']}")
            return client
        except Exception as e:
            logger.error(f"初始化vLLM模型客户端失败: {str(e)}")
            raise

    def get_model_name(self, model_version: str) -> str:
        """
        获取指定模型版本的模型名称

        Args:
            model_version: 模型版本

        Returns:
            str: 模型名称

        Raises:
            ValueError: 当模型版本不支持时
        """
        if model_version not in VLLM_MODELS_CONFIG:
            raise ValueError(f"不支持的模型版本: {model_version}")

        model_version = resolve_vllm_runtime_version(model_version)
        return VLLM_MODELS_CONFIG[model_version]["model_name"]

    def get_lora_adapters(self, model_version: str) -> Optional[List[str]]:
        """
        获取指定模型版本可用的 Lora 适配器列表（若有配置）

        Args:
            model_version: 模型版本

        Returns:
            适配器名称列表，未配置则返回 None
        """
        if model_version not in VLLM_MODELS_CONFIG:
            raise ValueError(f"不支持的模型版本: {model_version}")
        model_version = resolve_vllm_runtime_version(model_version)
        return VLLM_MODELS_CONFIG[model_version].get("lora_adapters")


# 全局模型客户端实例
vllm_model_client = VLLMModelClient()

# 预配置的模型实例

# Qwen3-32B（不思考，温度 0.3）
vllm_qwen32b = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen32b",
    temperature=0.3,
    num_predict=2000,
    stream=False,
    think_through=False
)

# Qwen3.5-35B 本地 vLLM（端口 7867，流式时可传 extra_params={"chat_template_kwargs": {"enable_thinking": False}}）
vllm_qwen35b = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen35b",
    temperature=0.7,
    num_predict=2048,
    stream=False,
    think_through=False
)

# Qwen3.5-35B 本地 vLLM（端口 7861，model_name: Qwen3.5-35B）
vllm_qwen35_35b = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen35-35b",
    temperature=0.7,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# Qwen3.5-35B-GPTQ-Int4 本地 vLLM（端口 7871，model_name: Qwen3.5-35B-int4）
vllm_qwen35_35b_gptq_int4 = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen35-35b-GPTQ-Int4",
    temperature=0.1,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# Qwen3.5-35B-FP8 SGLang 部署（端口 7874，served-model-name: Qwen3.5-35B-int4）
vllm_qwen35_35b_fp8 = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen35-35b-fp8",
    temperature=0.1,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# Qwen3.5-35B-FP8 HR 面试官专用（温度 0.6，对话更自然；num_predict 2048）
vllm_qwen35_35b_fp8_hr_interviewer = vllm_qwen35_35b_fp8.model_copy(
    update={"temperature": 0.6, "num_predict": 2048}
)

# Qwen3.5-35B-FP8 胜任力卡片/结论生成专用（温度 0.2，结构化输出更稳定）
vllm_qwen35_35b_fp8_hr_structured = vllm_qwen35_35b_fp8.model_copy(
    update={"temperature": 0.2, "num_predict": 2048}
)

# UbaoModel 本地 vLLM（端口 7879，与 VLLM_MODELS_CONFIG["UbaoModel"] 一致）
vllm_ubaomodel = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="UbaoModel",
    temperature=0.1,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# life_manager WebSocket `/ws/question_classification` 推荐编排（0–3 多轮追问/检索说明/推荐正文）专用
vllm_ubaomodel_question_classify_recommend = vllm_ubaomodel.model_copy(
    update={"temperature": 0.6}
)

# Qwen3.8-27B-FP8（端口 7880；默认关思考。开思考：think_through=True，reasoning_effort=low|xhigh）
vllm_qwen38_27b_fp8 = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen38-27b-fp8",
    temperature=0.1,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# Ubao-Model 本地 vLLM（端口 7880，与 VLLM_MODELS_CONFIG["Ubao-Model"] 一致）
vllm_ubao_model = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="Ubao-Model",
    temperature=0.1,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# Qwen3.5-4B 本地 vLLM（端口 7681，4 个 Lora: lawyer-8, lawyer-16, lawyer-32, lawyer-64）
vllm_qwen35_4b = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen35-4b",
    temperature=0.7,
    num_predict=2048,
    stream=False,
    think_through=False,
)

# Qwen3-VL
vllm_qwen_vl = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen-vl",
    temperature=0.7,
    num_predict=2000,
    stream=False,
    think_through=False
)

# MiniCPM-V-4.6 SGLang（端口 7880；官方要求 extra_body top_k / stop_token_ids，见 MiniCPM-V CookBook）
vllm_minicpm_v_46 = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="minicpm-v-4.6",
    temperature=0.7,
    num_predict=2000,
    stream=False,
    think_through=False,
    extra_params={
        "extra_body": {
            "top_k": -1,
            "stop_token_ids": [248044, 248046],
        },
    },
)

# Qwen3-Max (阿里百炼)
vllm_qwen3_max = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen3-max",
    temperature=0.7,
    num_predict=10000,
    stream=False,
    think_through=False
)

# Qwen3.6-Plus (阿里百炼 Fine_Model)
vllm_fine_model = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="Fine_Model",
    temperature=0.7,
    num_predict=10000,
    stream=False,
    think_through=False
)

# DeepSeek-OCR
vllm_ds_ocr = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="ds-ocr",
    temperature=0.1,
    num_predict=1024,
    stream=False,
    think_through=False
)

# Reranker
vllm_rerank = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="rerank",
    temperature=0.0,
    num_predict=100,
    stream=False,
    think_through=False
)

# Embedding
vllm_embedding = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="embedding",
    temperature=0.0,
    num_predict=1024,
    stream=False,
    think_through=False
)

# Qwen3-VL-Embedding
vllm_qwen3_vl_embedding = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen3-vl-embedding",
    temperature=0.0,
    num_predict=2048,
    stream=False,
    think_through=False
)

# Qwen3-4b
vllm_qwen3_4b = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen3-4b",
    temperature=0.2,
    num_predict=2000,
    stream=False,
    think_through=False
)

# Qwen2.5-1.5B-Instruct
vllm_qwen2_5_1_5b_instruct = VLLMRequestModel(
    messages=[],
    model="vllm",
    version="qwen2.5",
    temperature=0.6,
    num_predict=2000,
    stream=False,
    think_through=False
)

if __name__ == '__main__':
    print(vllm_model_client.get_model_name("qwen-vl"))
