"""
===============================================================================
合并召回信息节点 (Merge Retrieved Info Node)
===============================================================================

【业务定位】
  本文件是 LangGraph 数据代理工作流中的一个节点函数，负责将来自三条不同检索路径的
  召回结果进行合并、补全、去重、归组，最终输出统一的结构化表/指标信息给下游 LLM
  推理节点使用。

【三条检索路径说明】
  1. retrieved_columns — Qdrant 向量检索：用用户查询的语义向量与字段元数据做相似度匹配
  2. retrieved_values  — Elasticsearch 全文检索：用查询关键词在数据值中做文本匹配
  3. retrieved_metrics — Qdrant 向量检索：用用户查询的语义向量与指标元数据做相似度匹配

【为什么需要合并节点？】
  三路检索相互独立，结果存在以下问题：
  - 指标关联的字段可能未被向量检索召回（确定性补全需求）
  - ES值命中的字段可能未被向量检索召回（反查补全需求）
  - 字段散落在不同路径中，需要按表维度归并
  - 主键字段可能未被任何一路检索命中，但下游生成SQL必须用到
  - 字段的examples样本池需要融合多路来源的真实值
  因此需要一个合并节点将碎片化的召回结果整理成完整的结构化数据。

【数据流概要】
  State输入:
    ├── retrieved_columns (Qdrant向量检索) → [ColumnInfoQdrant]
    ├── retrieved_values  (ES全文检索)     → [ValueInfoEs]
    └── retrieved_metrics (Qdrant向量检索) → [MetricInfoQdrant]

  State输出:
    ├── table_infos  → [TableInfoState]  (表名 + 角色 + 描述 + 完整字段列表)
    └── metric_infos → [MetricInfoState] (指标名 + 描述 + 关联字段 + 别名)
"""

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
    """
    【字段转换】MySQL模型 → Qdrant模型

    业务含义：将 MySQL 中存储的字段元数据（结构化查询结果）转换为 Qdrant 的字段模型格式，
             以便统一放入 retrieved_columns_map 中与其他向量检索结果一起处理。

    设计原因：MySQL 查询返回的是 ORM 模型 ColumnInfoMySQL，但后续处理链路
             （分组、去重、值注入examples）统一使用 ColumnInfoQdrant 作为中间格式。
             这样做避免了后续代码对两种字段模型的分支判断，保持数据流单一化。

    参数:
        column_info_mysql: MySQL中查询出的字段ORM对象

    返回:
        ColumnInfoQdrant: 统一字段模型，包含 id/name/type/role/examples/description/alias/table_id
    """
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
    """
    【字段转换】Qdrant中间模型 → LangGraph State 最终格式

    业务含义：将合并完成后的字段信息（ColumnInfoQdrant）转换为 LangGraph 状态机上
             统一使用的 ColumnInfoState 格式，供下游节点（如SQL生成节点）消费。

    设计原因：table_id 是中间处理阶段需要的字段（用于 table 分组），但在最终 State 中
             不需要暴露，因为字段已经挂载在所属表下了。所以这里只选择字段自身的元信息。

    参数:
        column: 合并后的字段信息（Qdrant中间模型）

    返回:
        ColumnInfoState: 最终态字段信息，包含 name/type/role/examples/description/alias
    """
    return ColumnInfoState(
        name=column["name"],
        type=column["type"],
        role=column["role"],
        examples=column["examples"],
        description=column["description"],
        alias=column["alias"]
    )


def convert_metric_info_from_qdrant_to_state(retrieved_metric: MetricInfoQdrant) -> MetricInfoState:
    """
    【指标转换】Qdrant中间模型 → LangGraph State 最终格式

    业务含义：将检索到的指标信息转换为 State 统一格式。

    字段说明：
        - name:             指标名称（如 "销售额"、"日活用户数"）
        - description:      指标的业务定义与计算口径
        - relevant_columns: 该指标关联的字段列表（如销售额关联 order_amount、order_date）
        - alias:            指标的别名/同义词，提升用户查询的命中率

    参数:
        retrieved_metric: 检索出的指标信息

    返回:
        MetricInfoState: 最终态指标信息
    """
    return MetricInfoState(
        name=retrieved_metric["name"],
        description=retrieved_metric["description"],
        relevant_columns=retrieved_metric["relevant_columns"],
        alias=retrieved_metric["alias"]
    )


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    ===========================================================================
    三路检索结果合并核心函数
    ===========================================================================

    【合并流程六阶段】

    阶段一 ─ 数据汇集：从State中取出三路检索结果，构建字段去重字典
    阶段二 ─ 指标关联字段补全：遍历指标的relevant_columns，缺失字段从MySQL精确查询
    阶段三 ─ ES值反查字段补全 + examples注入：从ES命中的值反查所属字段，并注入值示例
    阶段四 ─ 表维度归并：将所有字段按table_id分组，并补充主键字段
    阶段五 ─ 格式转换：将分组后的数据转为TableInfoState/MetricInfoState
    阶段六 ─ 返回合并结果

    数据合并策略说明：
        【去重机制】:
          通过 dict 以 id 为 key 存储所有字段，天然完成去重。
          三路来源的字段如果 id 相同，后者会覆盖前者（这里后者是MySQL补充的字段，
          数据更完整，覆盖向量检索的简版字段是有益的）。

        【补全策略】:
          采用"精确ID补全"而非"再检索补全"，原因：
          - 指标定义中的 relevant_columns 存储的是字段ID，精确查询比再次向量检索
            更快、更准确，不会受嵌入质量波动影响
          - ES检索结果中的 column_id 也是精确ID，同理

        【归并策略】:
          按 table_id 归组后补全该表的主键。主键补全的必要性：
          - 下游 SQL 生成需要 JOIN/WHERE 条件必须用到主键
          - 检索阶段不保证召回主键字段（主键名通常与业务查询无语义关联）

    ===========================================================================
    """

    # LangGraph Runtime 的流式输出对象，用于向调用方实时推送处理进度
    writer = runtime.stream_writer
    writer({"state": "合并召回信息: 将三路搜索得到的结果进行合并 "})

    try:
        # ==================== 阶段一：数据汇集 ====================
        # 封装表信息列表
        """
        将三路检索的结果从 state 中取出并建立以 id 为 key 的字典，
        用于后续的去重和快速查找。
        """

        # 封装表信息列表
        table_infos: list[TableInfoStata] = []
        # 封装指标信息列表
        metric_infos: list[MetricInfoStata] = []
        # 获取召回的字段列表 — Qdrant向量检索的结果
        retrieved_columns: list[ColumnInfoQdrant] = state["retrieved_columns"]
        # 获取召回的值列表 — ES全文检索的结果
        retrieved_values: list[ValueInfoEs] = state["retrieved_values"]
        # 获取召回的指标信息 — Qdrant向量检索的结果
        retrieved_metrics: list[MetricInfoQdrant] = state["retrieved_metrics"]
        # 获取查询字段信息的mysql客户端对象 — 用于精确ID补全查询
        meta_mysql_repository = runtime.context["meta_mysql_repository"]

        # 【关键数据结构】字段去重字典
        # 以字段ID为key，确保同一个字段无论从哪条路径来，在最终结果中只出现一次
        retrieved_columns_map: dict[str, ColumnInfoQdrant] = {retrieved_column["id"]: retrieved_column for
                                                              retrieved_column in retrieved_columns}

        # ==================== 阶段二：指标关联字段补全 ====================
        """
        策略：遍历每个检索到的指标，检查其声明的关联字段（relevant_columns）。
             如果某个关联字段不存在于已召回字段中，则通过MySQL进行精确ID查询补全。

        为什么需要这样做？
        - 向量检索基于语义相似度，如果用户query与某个字段的描述不相似，该字段
          就不会被召回。但该字段可能是指标计算必须的字段。
        - 例如：用户问"上月毛利率"，向量检索可能召回 profit、gross_sales，
          但指标定义中还关联了 cost_of_goods，这个字段的description可能与
          "毛利率"这个词的向量距离较远，未被召回。
        - 通过这种方式，用指标定义中的确定性关联弥补向量检索的不确定性。
        """
        for metric in retrieved_metrics:
            relevant_columns: list[str] = metric["relevant_columns"]

            for relevant_column in relevant_columns:
                # 判断是否已经被召回
                if relevant_column not in retrieved_columns_map:
                    # 根据字段id查询字段信息 — 精确查询，一次命中
                    column_info_mysql: ColumnInfoMySQL = await  meta_mysql_repository.get_column_info_by_id(
                        relevant_column)
                    # 转换类型 — MySQL模型 → Qdrant中间格式（与向量检索结果统一）
                    column_info_qdrant: ColumnInfoQdrant = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
                    # 存储 — 加入字段字典，后续与其他来源的字段统一处理
                    retrieved_columns_map[relevant_column] = column_info_qdrant

        # ==================== 阶段三：ES值反查字段补全 + examples注入 ====================
        """
        策略：遍历ES检索命中的值，做两件事：
              1) 如果值所属的字段不在字段字典中，通过MySQL精确查询补全
              2) 将值本身追加到该字段的 examples 列表中（去重追加）

        为什么需要"值反查字段"？
        - ES全文检索在数据值上做匹配，可能命中某个字段的具体值，
          但该字段名/描述与用户query语义不相似，因此未被向量检索召回。
        - 典型场景：用户问"包含'黄金会员'的数据"，ES在 customer_level 字段的
          值中命中"黄金会员"，但 customer_level 的向量嵌入可能与"黄金会员"
          这一具体值的语义距离较远，未被Qdrant召回。
        - 通过值→字段的反向关联（ValueInfoEs 中存储了 column_id），
          把"漏网字段"补回来。

        为什么需要注入examples？
        - examples（字段值示例）在最终 Prompt 中用来帮助 LLM 理解字段内容。
        - ES命中的值是该字段的真实数据，作为example注入可以让 LLM 看到
          更丰富的样本，提升 SQL 生成质量（比如知道枚举值有哪些、数值范围）。
        - 去重逻辑：同一个值可能在ES中多次命中（不同文档），但examples中只保留一份。
        """
        for retrieved_value in retrieved_values:
            # column_id: ES中每个命中值都关联了其所属字段的ID
            column_id = retrieved_value["column_id"]
            # value: ES命中的具体字段值（如"黄金会员"）
            column_value = retrieved_value["value"]

            # 反查：如果该字段尚未在字段字典中，从MySQL精确查询补全
            if column_id not in retrieved_columns_map:
                # 根据字段id查询字段信息
                column_info_mysql: ColumnInfoMySQL = await  meta_mysql_repository.get_column_info_by_id(column_id)
                # 转换类型
                column_info_qdrant: ColumnInfoQdrant = convert_column_info_from_mysql_to_qdrant(column_info_mysql)
                # 存储
                retrieved_columns_map[column_id] = column_info_qdrant

            # 值注入：将ES命中的真实值追加到字段的examples列表
            # 去重判断：避免同一个值在examples中重复出现
            if column_value not in retrieved_columns_map[column_id]['examples']:
                retrieved_columns_map[column_id]['examples'].append(column_value)

        # ==================== 阶段四：表维度归并 ====================
        """
        策略：将全局字段字典按 table_id 分组，建立 "表→字段列表" 的映射，
             然后对每张表补充其主键字段。

        为什么需要按表归并？
        - 下游 LLM 需要理解数据按表组织的结构来生成正确的 SQL
        - 字段散落在三个检索来源中，需要按表维度重新组织
        - 一张表下的字段集合决定了可以查询哪些列、做哪些 JOIN

        为什么需要补充主键？
        - 主键字段名（如 id, user_id, order_no）通常与业务查询关键词无语义关联，
          在向量检索阶段大概率不会被召回
        - 但生成 SQL 的 JOIN、WHERE、GROUP BY 必须用到主键
        - key_columns 是表结构中标记的主键字段，补全它保证 SQL 完整性
        - 去重判断（column_id not in ids）：如果主键恰好已被召回，不重复添加
        """

        # table_id → [ColumnInfoQdrant, ...] 的映射
        # 将散列字段按所属表归组
        table_to_column_map: dict[str, list[ColumnInfoQdrant]] = {}

        for column in retrieved_columns_map.values():
            table_id = column["table_id"]
            # 首次遇到该table_id，初始化空列表
            if not table_id in table_to_column_map:
                table_to_column_map[table_id] = []

            table_to_column_map[table_id].append(column)

        # 对每张表，从MySQL获取其主键字段并补充
        for table_id in table_to_column_map.keys():
            # key_columns: MySQL中标记为主键的字段列表
            key_columns: list[ColumnInfoMySQL] = await meta_mysql_repository.get_column_info_by_id(table_id)
            if key_columns:
                # 收集当前表中已有字段的id列表，用于去重
                ids = [column['id'] for column in table_to_column_map[table_id]]

                for key_column in key_columns:
                    # 获取id
                    column_id = key_column.id
                    # 判断是否已经存在 — 去重，不重复添加已存在的字段
                    if column_id not in ids:
                        table_to_column_map[table_id].append(convert_column_info_from_mysql_to_qdrant(key_column))

        # ==================== 阶段五：格式转换 ====================

        """
        将阶段四归组好的数据转换为 LangGraph State 的最终格式。
        包括两个转换：
        A. 表信息转换：table_id分组数据 → TableInfoState
        B. 指标信息转换：MetricInfoQdrant → MetricInfoState
        """

        # --- A. 表信息转换 ---
        # 遍历每个表分组，查询表的元信息并构建完整 TableInfoState
        for table_id, column_list in table_to_column_map.items():
            # 根据表id查询表信息（name, role, description）
            # role 字段标记了这张表是事实表还是维度表，对 JOIN 策略有影响
            table_info_mysql: TableInfoMySQL = await meta_mysql_repository.get_table_info_by_id(table_id)

            # 获取当前表的所有字段信息 — ColumnInfoQdrant → ColumnInfoState
            # 每个字段转成最终 State 格式（丢弃 table_id，因为已挂载到表下）
            columns = [convert_column_info_from_qdrant_to_state(column) for column in column_list]

            #  转换类型 — 构建最终的表信息对象
            table_info = TableInfoState(
                name=table_info_mysql.name,            # 表名
                role=table_info_mysql.role,            # 表角色（事实表/维度表）
                description=table_info_mysql.description,  # 表的业务描述
                columns=columns                         # 该表下的完整字段列表
            )
            table_infos.append(table_info)

        # 日志输出：打印所有合并后的表名，便于调试
        logger.info(f'合并后的表信息数据{[table_info["name"] for table_info in table_infos]}')

        # --- B. 指标转换 ---
        # 指标信息直接转换，不需要像字段那样分组
        metric_infos: list[MetricInfoState] = [convert_metric_info_from_qdrant_to_state(retrieved_metric) for
                                               retrieved_metric in retrieved_metrics]

        logger.info(f'合并后的指标信息{[metric_info["name"] for metric_info in metric_infos]}')

        # ==================== 阶段六：返回合并结果 ====================
        """
        返回值直接更新 LangGraph State，下游节点可以通过
        state["table_infos"] 和 state["metric_infos"] 访问合并后的数据。
        """
        return {"table_infos": table_infos, "metric_infos": metric_infos}


    except Exception as e:
        logger.error(f"合并召回信息异常{str(e)}")
        raise