from pathlib import Path

import uuid
from omegaconf import OmegaConf

from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.column_info_mysql import ColumnInfoMySQL
from app.models.table_info_mysql import TableInfoMySQL
from app.repossitories.dw_mysql_repository import DwMysqlRepository
from app.repossitories.meta_mysql_repository import MetaMysqlRepository


class MetaKnowledgeService:
    def __init__(self,meta_mysql_repository:MetaMysqlRepository,
                 dw_mysql_repository:DwMysqlRepository):
        self.meta_mysql_repository=meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository


    async def build(self,file_path:Path):
        #加载配置文件读取数据

        context=OmegaConf.load(file_path)

        schema=OmegaConf.structured(context)

        meta_config:MetaConfig=OmegaConf.to_object(OmegaConf.merge(schema,context))

        logger.info("配置加载已经完成")

        # print(meta_config)
        if meta_config['tables'] :
            table_infos: list[TableInfoMySQL] = []
            column_infos: list[ColumnInfoMySQL] = []
            for table in meta_config['tables']:

                table_info_mysql = TableInfoMySQL(
                    id=table['name'] ,
                    name=table['name'],
                    role=table['role'],
                    description=table['description'],
                )
                table_infos.append(table_info_mysql)

                column_types:dict[str,str]=await self.dw_mysql_repository.get_cloumn_types(table['name'])

                # 构建该表下的字段元数据
                if table.get('columns'):
                    for col in table['columns']:
                        examples=await self.dw_mysql_repository.get_column_values(table['name'], col['name'])
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

            logger.info("保存表信息和字段信息在meta数据库")





    def get_meta_config(self):
        return self.meta_config