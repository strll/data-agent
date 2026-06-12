from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


# 负责定义过滤指标信息的节点
async def filter_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
	try:
		writer=runtime.stream_writer
		writer({"state":"过滤指标信息"})

		#获取需要的信息 获取用户问题

		query=state["query"]
		metric_infos=state["metric_infos"]


		prompt=PromptTemplate(template=load_prompt("filter_metric_info"),
							  input_variables=["query","metric_infos"])

		output_parser = JsonOutputParser()

		chain = prompt | llm | output_parser

		formatted_prompt = prompt.format(query=query, metric_infos=metric_infos)
		logger.info(
			f"========== 发送给大模型的完整提示词 ==========\n{formatted_prompt}\n============================================")

		result = await chain.ainvoke({"query": query, "metric_infos": metric_infos})

		logger.info(f"大模型筛选之后的指标的信息\n{result}\n")

		for metric_info in metric_infos[:]:
			if metric_info["name"] not in result:
				metric_infos.remove(metric_info)

		logger.info(f"过滤后的指标信息{[metric_info["name"] for metric_info in metric_infos]}")
	except Exception as e:
		logger.error(f"过滤指标信息异常：{str(e)}")
		raise
