import uuid
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.repossitories.es.ValueEsRepository import ValueEsRepository
from app.repossitories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repossitories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repossitories.qdrant.column_qdrant_repository import ColumnQdrantRepository


class MetaKnowledgeService:
    def __init__(self, meta_mysql_repository: MetaMysqlRepository,
                 dw_mysql_repository: DwMysqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client:HuggingFaceEndpointEmbeddings,
                 value_es_repository: ValueEsRepository,
                 ):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_client=embedding_client
        self.value_es_repository = value_es_repository

    async def build(self, file_path: Path):
        # 加载配置文件读取数据

        context = OmegaConf.load(file_path)

        schema = OmegaConf.structured(context)

        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))

        logger.info("配置加载已经完成")

        # print(meta_config)
        if meta_config['tables']:
            column_infos = await self._save_table_info_to_meta_db(meta_config)
            logger.info("保存表信息和字段信息在meta数据库")

            await self._save_table_info_to_qdrant(column_infos)
            logger.info("为字段构建向量索引")
            await self.column_qdrant_repository.ensure_collection()
            logger.info("为字段信息构建向量索引")


            await self._save_value_info_to_es(column_infos,meta_config)
            logger.info("为字段值构建全文索引")




    async def _save_table_info_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfoMySQL]:
        table_infos: list[TableInfoMySQL] = []
        column_infos: list[ColumnInfoMySQL] = []
        for table in meta_config['tables']:

            table_info_mysql = TableInfoMySQL(
                id=table['name'],
                name=table['name'],
                role=table['role'],
                description=table['description'],
            )
            table_infos.append(table_info_mysql)

            column_types: dict[str, str] = await self.dw_mysql_repository.get_cloumn_types(table['name'])

            # 构建该表下的字段元数据
            if table.get('columns'):
                for col in table['columns']:
                    examples = await self.dw_mysql_repository.get_column_values(table['name'], col['name'])
                    column_info = ColumnInfoMySQL(
                        id=f"{table['name']}.{col['name']}",
                        name=col['name'],
                        type=column_types[col['name']],
                        examples=examples,
                        role=col['role'],
                        description=col['description'],
                        alias=col.get('alias', []),
                        table_id=table['name'],
                    )
                    column_infos.append(column_info)

        async with self.meta_mysql_repository.session.begin() as session:

            await self.meta_mysql_repository.save_table_infos(table_infos)

            await self.meta_mysql_repository.save_column_infos(column_infos)




        return column_infos

    def get_meta_config(self):
        return self.meta_config

    def _convert_column_info_from_mysql_to_qdrant(self, column_info:ColumnInfoMySQL):
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            description=column_info.description,
            alias=column_info.alias,
            table_id=column_info.table_id
                                )

    async def _save_table_info_to_qdrant(self, column_infos: list[ColumnInfoMySQL]):

        # 构建向量存储集合
        points: list[dict] = []
        # 遍历字段列表进行封装
        for column_info in column_infos:
            points.append(
                {
                    "id": uuid.uuid4(),
                    "embedding_text": column_info.name,
                    "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
                }
            )

            points.append(
                {
                    "id": uuid.uuid4(),
                    "embedding_text": column_info.name,
                    "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
                }
            )

            points.append(
                {
                    "id": uuid.uuid4(),
                    "embedding_text": column_info.description,
                    "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
                }
            )

            for alias in column_info.alias:
                points.append(
                    {
                        "id": uuid.uuid4(),
                        "embedding_text": alias,
                        "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
                    }
                )

        embedding_text = [point['embedding_text'] for point in points]

        batch_size = 10
        emdeddings: list[list[float]] = []

        for i in range(0, len(embedding_text), batch_size):
            batch_embedding_texts = embedding_text[i:i + batch_size]

            batch_embeddings_texts = await self.embedding_client.aembed_documents(batch_embedding_texts)
            emdeddings.extend(batch_embeddings_texts)

        ids = [point['id'] for point in points]

        paylods = [point['payload'] for point in points]

        await self.column_qdrant_repository.upsert_embeddings(ids, emdeddings, paylods)
        logger.info("保存字段信息到qdrant数据库")

    async def _save_value_info_to_es(self, column_infos:list[ColumnInfoMySQL],meta_config:MetaConfig):
        # 确保存储字段值的索引存在
        await self.value_es_repository.ensure_index()

        # 获取所有字段的值是否进行全文索引的标识
        column2sync: dict[str, bool] = {}
        for table in meta_config['tables']:
            for column in table['columns']:
                column2sync[column['name']] = column['sync']

        # 收集所有字段值数据
        value_infos: list[ValueInfoEs] = []
        # 为字段值信息构建全文索引
        for column_info in column_infos:
            # 获取当前字段的索引标识
            sync = column2sync[column_info.name]
            if sync:
                # 根据列名查询这一列的所有值
                column_values: list[str] = await self.dw_mysql_repository.get_column_values(column_info.table_id,
                                                                                            column_info.name,
                                                                                            limit=10000)

                # 遍历字段值列表
                for column_value in column_values:
                    # 创建对象
                    value_info_es = ValueInfoEs(
                        id=f"{column_info.id}.{column_value}",
                        value=column_value,
                        type=column_info.type,
                        column_id=column_info.id,
                        column_name=column_info.name,
                        table_id=column_info.table_id,
                        table_name=column_info.table_id
                    )
                    value_infos.append(value_info_es)
        # 保存到es
        await self.value_es_repository.save_column_values(value_infos)

