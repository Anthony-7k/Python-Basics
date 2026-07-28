from fastapi import FastAPI,Path,Query

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/user/{id}")
async def get_user(id: int = Path(..., gt=0,lt=101)):
    return {"userid": id,"title":f"这是第{id}个user"}


# 查找书籍的作者，路径参数：name，长度范围2-10
@app.get("/author/{name}")
async def get_name(name: str = Path(..., min_length=2,max_length=10)):
    return{"msg":f"这是{name}的信息"}


# 根据新闻分类 ID 查询
@app.get("/news/category/id/{category_id}")
async def get_category_by_id(
    category_id: int = Path(..., ge=1, le=100)
):
    return {
        "category_id": category_id,
        "message": f"查询 ID 为 {category_id} 的新闻分类"
    }


# 根据新闻分类名称查询
@app.get("/news/category/name/{category_name}")
async def get_category_by_name(
    category_name: str = Path(..., min_length=2, max_length=10)
):
    return {
        "category_name": category_name,
        "message": f"查询名称为 {category_name} 的新闻分类"
    }

# 需求 查询新闻-》分页 skip：跳过的记录 limit：返回的记录数：10
@app.get("/news/news_list")
async def get_news_list(
        skip:int = Query(0,description="跳过的记录",lt=100),
        limit:int = Query(10,description="返回的记录数")
    ):
    return {"skip":skip,"limit":limit}

# 根据图书分类和价格查询图书
@app.get("/books")
async def get_books(
    category: str = Query(
        default="Python开发",
        min_length=5,
        max_length=255,
        description="图书分类",
    ),
    price: float = Query(
        ...,
        ge=50,
        le=100,
        description="图书价格",
    ),
):
    return {
        "category": category,
        "price": price,
        "message": f"正在查询分类为 {category}、价格为 {price} 的图书",
    }
