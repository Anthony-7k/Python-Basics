from urllib import request

from fastapi import FastAPI,HTTPException
from pydantic import BaseModel

app = FastAPI()


@app.middleware("http")
async def middleware1(Request, call_next):
    print("中间件1：start")
    response = await call_next(request)
    print("中间件1：end")
    return response

@app.middleware("http")
async def middleware2(Request, call_next):
    print("中间件2：start")
    response = await call_next(request)
    print("中间件2：end")
    return response

@app.get("/")
async def root():
    return {"message": "Hello World"}

"""
@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

# 需求：新闻接口——>响应数据格式
class News(BaseModel):
    id: int
    title: str
    content: str

@app.get("/news/{id}", response_model=News)
async def get_news(id: int):
    return {
        "id": id,
        "title": f"这是第{id}本书",
        "content":"这是一本好书"
    }

# 需求 ： 按id查询，id：1-6
@app.get("/news/{id}")
async def get_news(id: int):
    id_list = [1,2,3,4,5,6]
    if id not in id_list:
        raise HTTPException(status_code=404, detail="Not Found")
    return {
        "id": id,
    }
    
"""

