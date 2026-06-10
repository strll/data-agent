from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select, text

from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL


class MetaMysqlRepository:
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session

    async def save_table_infos(self, table_infos: list[TableInfoMySQL]):
        """保存表元数据：主键冲突则更新，否则新增"""
        for info in table_infos:
            await self.session.merge(info)

    async def save_column_infos(self, column_infos: list[ColumnInfoMySQL]):
        """保存列元数据：主键冲突则更新，否则新增"""
        for info in column_infos:
            await self.session.merge(info)

    async def save_metric_infos(self, meta_infos:list[MetricInfoMySQL]):
        for meta_info in meta_infos:

         await   self.session.merge(meta_info)

    async def save_column_metrics(self, column_metrics:list[ColumnMetricMySQL]):
        for column_metric in column_metrics:
            await self.session.merge(column_metric)

    async def get_key_columns_by_table_id(self, table_id:str)->list[ColumnInfoMySQL]:
        # 定义sql
        sql= """
            select *
            from column_info
            where table_id = :table_id
              and role in ('primary_key', 'foreign_key') 
        """

        # 执行sql
        result=await self.session.execute(select(ColumnInfoMySQL).from_statement(text(sql)),{"table_id":table_id})

        return result.scalars().fetchall()

    async def get_column_info_by_id(self, column_id:str):

        return await self.session.get(ColumnInfoMySQL,column_id)

    async def get_table_info_by_id(self, table_id):
        return await self.session.get(TableInfoMySQL,table_id)