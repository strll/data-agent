from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.agent.llm import llm
from app.repossitories.qdrant.metric_qdrant_repository import MetricQdrantRepository


# 负责定义召回取值信息的节点
async def recall_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
	writer=runtime.stream_writer
	writer({"state":"召回指标信息"})


	embedding_client:HuggingFaceEndpointEmbeddings=runtime.context["embedding_client"]

	metric_qdrant_repository :MetricQdrantRepository= runtime.context["metric_qdrant_repository"]

	writer=runtime.stream_writer
	writer({"state":"召回字段信息"})

	keywords:list[str]=state.get("keywords", [])

	query:str=state.get("query","")
	try:
		#扩展提示词
		prompt=PromptTemplate(template=load_prompt("extend_keywords_for_metric_recall"),
							  input_variables=["query"]
							  )
		output_parser=JsonOutputParser()

		chain=prompt|llm|output_parser

		result=await chain.ainvoke({"query":query})

		keywords=set(keywords+result)
		logger.info(f"扩展后的关键词列表{keywords}")

		for keyword in keywords:
			# 转换向量
			embedding=await embedding_client.aembed_query(keyword)

			payloads: list[MetricInfoQdrant] = await metric_qdrant_repository.search(embedding)
			retrieved_metric_map: dict[str, MetricInfoQdrant] = {}
			# 遍历查询负载结果
			for payload in payloads:
				# 获取字段id
				metric_id = payload["id"]
				# 判断召回map列表中是否存在
				if not metric_id in retrieved_metric_map:
					retrieved_metric_map[metric_id] = payload

			retrieved_columns = list(retrieved_metric_map.values())
			logger.info(f"召回指标成功{[retrieved_metric_map.keys()]}")


			return {"retrieved_metrics": retrieved_columns}

	except Exception as e:
		logger.error(f"召回指标异常：{str(e)}")
		raise