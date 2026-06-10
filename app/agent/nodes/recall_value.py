
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate

from langgraph.runtime import Runtime


from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs

from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.agent.llm import llm
from app.repossitories.es.ValueEsRepository import ValueEsRepository


# 负责定义召回取值信息的节点
async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"state": "正在召回取值信息"})

    keywords: list[str] = state.get("keywords", [])

    query: str = state.get("query", "")
    try:
        # 扩展提示词
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"),
                                input_variables=["query"]
                                )
        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        value_es_repository:ValueEsRepository = runtime.context["value_es_repository"]

        keywords = set(keywords + result)
        logger.info(f"扩展后的关键词列表{keywords}")

        retrieved_value_map: dict[str, ValueInfoEs] = {}
        for keyword in keywords:
            # 查询es
            es_values: list[ValueInfoEs] = await value_es_repository.search(keyword)
            # 遍历查询负载结果
            for value in es_values:
                # 获取指标id
                value_id = value["id"]
                # 判断召回map列表中是否存在
                if not value_id in retrieved_value_map:
                    retrieved_value_map[value_id] = value

        # 获取召回字段对象列表
        retrieved_values = list(retrieved_value_map.values())
        logger.info(f"es搜索召回字段取值成功{[retrieved_value_map.keys()]}")
        return {"retrieved_values": retrieved_values}
    except Exception as e:
        logger.error(f"召回字段取值失败：{str(e)}")
        raise