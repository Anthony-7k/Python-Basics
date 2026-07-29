from datetime import datetime
from sqlalchemy import DateTime, func, String
from sqlalchemy import Float
from fastapi import FastAPI,Query,Depends # 2.导入depends
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from collections.abc import AsyncGenerator
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

app = FastAPI()

#创建异步引擎
ASYNC_DATABASE_URL = "mysql+aiomysql://root:123456@localhost:3306/day17?charset=utf8"
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True, # 输出日志用的
    pool_size=10, # 设置连接池活跃的连接数
    max_overflow=20, # 允许的额外连接数
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False
)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# 2、定义模型类： 先有基类再有表对应的模型类
# 基类：创建时间、更新时间；

class Base(DeclarativeBase):
    create_time: Mapped[datetime] = mapped_column(DateTime,insert_default=func.now(),default=func.now(),comment = "创建时间")
    update_time: Mapped[datetime] = mapped_column(DateTime,insert_default=func.now(),default=func.now(),onupdate=func.now(),comment="修改时间")


class Book(Base):
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(primary_key=True,comment="书籍id")
    bookname:Mapped[str] = mapped_column(String(255),comment="书名")
    author: Mapped[str] = mapped_column(String(255), comment="作者")
    price: Mapped[float] = mapped_column(Float, comment="价格")
    publisher: Mapped[str] = mapped_column(String(255), comment="出版社")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, comment="用户ID")
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        comment="用户名",
    )
    password: Mapped[str] = mapped_column(String(255), comment="密码")


class BookCreate(BaseModel):
    bookname: str
    author: str
    price: float
    publisher: str


class BookResponse(BookCreate):
    id: int
    create_time: datetime
    update_time: datetime

    model_config = ConfigDict(from_attributes=True)


# 3.建表：定义函数建表->FastApi启动的时候调用建表函数
async def create_tables():
    # 获取数据库的异步引擎，创建事务-建表
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    await create_tables()

@app.post("/books", response_model=BookResponse, status_code=201)
async def create_book(
    book_data: BookCreate,
    db: AsyncSession = Depends(get_db),
):
    book = Book(**book_data.model_dump())

    db.add(book)
    await db.commit()
    await db.refresh(book)

    return book



@app.get("/")
async def root():
    return {"message": "Hello World"}




"""
# 分页参数逻辑共用：新闻列表和用户列表
# 依赖项
async def common_params(
        skip: int = Query(0,ge=0),
        limit: int = Query(10,le=60)
):
        return {"skip": skip, "limit": limit}


@app.get("/news/news_list")
async def get_news_list(commons = Depends(common_params)):
    return commons

@app.get("/user/user_list")
async def get_user_list(commons = Depends(common_params)):
    return commons
"""
