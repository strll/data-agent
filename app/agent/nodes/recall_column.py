from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langgraph.runtime import Runtime
from sqlalchemy.ext.asyncio import result

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.agent.llm import llm
from app.repossitories.qdrant.column_qdrant_repository import ColumnQdrantRepository


# 负责定义召回字段信息的节点
async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):

	embedding_client:HuggingFaceEndpointEmbeddings=runtime.context["embedding_client"]
	column_qdrant_repository :ColumnQdrantRepository= runtime.context["column_qdrant_repository"]
	writer=runtime.stream_writer
	writer({"state":"召回字段信息"})

	keywords:list[str]=state.get("keywords", [])

	query:str=state.get("query","")
	try:
		#扩展提示词
		prompt=PromptTemplate(template=load_prompt("extend_keywords_for_column_recall"),
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

			payloads: list[ColumnInfoQdrant] = await column_qdrant_repository.search(embedding)
			retrieved_column_map: dict[str, ColumnInfoQdrant] = {}
			# 遍历查询负载结果
			for payload in payloads:
				# 获取字段id
				column_id = payload["id"]
				# 判断召回map列表中是否存在
				if not column_id in retrieved_column_map:
					retrieved_column_map[column_id] = payload

			retrieved_columns = list(retrieved_column_map.values())
			logger.info(f"召回字段成功{[retrieved_column_map.keys()]}")


			return {"retrieved_columns": retrieved_columns}

	except Exception as e:
		logger.error(f"召回字段异常：{str(e)}")
		raise