from sqlalchemy.ext.asyncio.session import AsyncSession

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