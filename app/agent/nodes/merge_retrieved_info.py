import asyncio
from os import name
from langgraph.runtime import Runtime
from typing_extensions import runtime

from app.agent.context import DataAgentContext
from app.agent.nodes.state import TableInfoStata, MetricInfoStata
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant

from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, ColumnInfoState, MetricInfoState, TableInfoState
from app.core.log import logger


# 负责定义合并召回信息的节点

def convert_column_info_from_mysql_to_qdrant(column_info_mysql: ColumnInfoMySQL):
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        type=column_info_mysql.type,
        role=column_info_mysql.role,
        examples=column_info_mysql.examples,
        description=column_info_mysql.description,
        alias=column_info_mysql.alias,
        table_id=column_info_mysql.table_id,
    )


def convert_column_info_from_qdrant_to_state(column: ColumnInfoQdrant) -> ColumnInfoState:
    return ColumnInfoState(
        name=column["name"],
        type=column["type"],
        role=column["role"],
        examples=column["examples"],
        description=column["description"],
        alias=column["alias"]
    )


def convert_metric_info_from_qdrant_to_state(retrieved_metric: MetricInfoQdrant) -> MetricInfoState:
    return MetricInfoState(
        name=retrieved_metric["name"],
        description=retrieved_metric["description"],
        relevant_columns=retrieved_metric["relevant_columns"],
        alias=retrieved_metric["alias"]
    )


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"state": "合并召回信息: 将三路搜索得到的结果进行合并 "})
    try:
        # 封装表信息列表
        table_infos: list[TableInfoStata] = []
        # 封装指标信息列表
        metric_infos: list[MetricInfoStata] = []
        # 获取召回的字段列表
        retrieved_columns: list[ColumnInfoQdrant] = state["retrieved_columns"]
        # 获取召回的值列表
        retrieved_values: list[ValueInfoEs] = state["retrieved_values"]
        # 获取召回的指标信息
        retrieved_metrics: list[MetricInfoQdrant] = state["retrieved_metrics"]
        # 获取查询字段信息的mysql客户端对象
        meta_mysql_repository = runtime.context["meta_mysql_repository"]

        retrieved_columns_map: dict[str, ColumnInfoQdrant] = {retrieved_column["id"]: retrieved_column for
                                                              retrieved_column in retrieved_columns}

        for metric in retrieved_metrics:
            relevant_columns: list[str] = metric["relevant_columns"]

            for relevant_column in relevant_columns:
                # 判断是否已经被召回
                if relevant_column not in retrieved_columns_map:
                    # 根据字段id查询字段信息
                    column_info_mysql: ColumnInfoMySQL = await  meta_mysql_repository.get_column_info_by_id(
                        relevant_column)
                    # 转换类型
                    column_info_qdrant: ColumnInfoQdrant = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
                    # 存储
                    retrieved_columns_map[relevant_column] = column_info_qdrant

        for retrieved_value in retrieved_values:
            column_id = retrieved_value["column_id"]

            column_value = retrieved_value["value"]

            if column_id not in retrieved_columns_map:
                # 根据字段id查询字段信息
                column_info_mysql: ColumnInfoMySQL = await  meta_mysql_repository.get_column_info_by_id(column_id)
                # 转换类型
                column_info_qdrant: ColumnInfoQdrant = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
                # 存储
                retrieved_columns_map[column_id] = column_info_qdrant

            if column_value not in retrieved_columns_map[column_id]['examples']:
                retrieved_columns_map[column_id]['examples'].append(column_value)

        table_to_column_map: dict[str, list[ColumnInfoQdrant]] = {}

        for column in retrieved_columns_map.values():

            table_id = column["table_id"]
            if not table_id in table_to_column_map:
                table_to_column_map[table_id] = []

            table_to_column_map[table_id].append(column)

        for table_id in table_to_column_map.keys():
            key_columns: list[ColumnInfoMySQL] = await meta_mysql_repository.get_column_info_by_id(table_id)
            if key_columns:
                ids = [column['id'] for column in table_to_column_map[table_id]]

                for key_column in key_columns:
                    # 获取id
                    column_id = key_column.id
                    # 判断是否已经存在
                    if column_id not in ids:
                        table_to_column_map[table_id].append(convert_column_info_from_mysql_to_qdrant(key_column))

        # 转换表结构封装
        for table_id, column_list in table_to_column_map.items():
            # 根据表id查询表信息
            table_info_mysql: TableInfoMySQL = await meta_mysql_repository.get_table_info_by_id(table_id)

            # 获取当前表的所有字段信息
            columns = [convert_column_info_from_qdrant_to_state(column) for column in column_list]

            #  转换类型
            table_info = TableInfoState(
                name=table_info_mysql.name,
                role=table_info_mysql.role,
                description=table_info_mysql.description,
                columns=columns
            )
            table_infos.append(table_info)

        logger.info(f'合并后的表信息数据{[table_info["name"] for table_info in table_infos]}')
        # 指标转换结构
        metric_infos: list[MetricInfoState] = [convert_metric_info_from_qdrant_to_state(retrieved_metric) for
                                               retrieved_metric in retrieved_metrics]

        logger.info(f'合并后的指标信息{[metric_info["name"] for metric_info in metric_infos]}')
        return {"table_infos": table_infos, "metric_infos": metric_infos}


    except Exception as e:
        logger.error(f"合并召回信息异常{str(e)}")
        raise
