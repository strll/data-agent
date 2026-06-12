from unittest import result

import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import text

from app.core.log import logger


class DwMysqlRepository:
    def __init__(self, session: AsyncSession,
                 ):

        self.session: AsyncSession = session

    async def get_cloumn_types(self, table_name: str) -> dict[str, str]:
        sql = f"show columns from  {table_name}"

        result = await self.session.execute(text(sql))
        return {row[0]: row[1] for row in result.fetchall()}

    async def get_column_values(self, table_name: str, column_name: str, limit: int = 10) -> list[str]:
        sql = text(f"select distinct {column_name} from {table_name} limit {limit} ")
        result = await self.session.execute(sql)
        res = [row[0] for row in result.fetchall()]

        return res

    async def get_db_info(self):
        # 获取版本
        result = await self.session.execute(text("select version()"))
        # 获取版本信息
        version = result.scalar()

        # 获取方言
        dialect = self.session.get_bind().dialect.name

        return {"version": version, "dialect": dialect}

    async def validate_sql(self, sql):

        try:
            result = await self.session.execute(text(f"explain {sql}"))
        except Exception as e:
            logger.error(f"校验sql错误{str(e)}")
            raise

    async def execute_sql(self, sql:str):

        try:
            result =await  self.session.execute(text(sql))

            fetchall= result.mappings().fetchall()
        except Exception as e:
            logger.error(f"执行sql错误 {str(e)}")
            raise
        return fetchall

