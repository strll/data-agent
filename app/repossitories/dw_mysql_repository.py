from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import text

from app.repossitories.meta_mysql_repository import MetaMysqlRepository


class DwMysqlRepository:
    def __init__(self, session: AsyncSession,
                 ):

        self.session: AsyncSession = session

    async def get_cloumn_types(self, table_name: str)->dict[str,str]:
        sql = f"show columns from  {table_name}"

        result=await self.session.execute(text(sql))
        return {row[0]:row[1] for row in result.fetchall()}

    async def get_column_values(self, table_name:str, column_name:str,limit:int=10)->list[str]:
        sql=text(f"select distinct {column_name} from {table_name} limit {limit} ")
        result=await self.session.execute(sql)
        res= [row[0] for row in result.fetchall()]

        return res
