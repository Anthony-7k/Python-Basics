from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

# 注册功能：用户名和密码 -> str
class User(BaseModel):
    username: str
    password: str

@app.post("/register")
async def register(user: User):
    return user

class Book(BaseModel):
    name: str = Field(min_length=1, description="书名")
    author: str = Field(min_length=1, description="作者")
    publisher: str = Field(min_length=1, description="出版社",default="黑马出版社")
    price: float = Field(gt=0, description="售价")


@app.post("/books", status_code=201)
async def create_book(book: Book):
    return {
        "message": "图书新增成功",
        "data": book,
    }
