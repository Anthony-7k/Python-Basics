"""def test_return():
    return 1,2,"hello"
x,y,z = test_return()
print(x,y,z)

def user_info(name,age,gender):
    print(f"姓名是{name},年龄是{age},性别是{gender}")
user_info("小明",20,"男")
# 关键字传参(可以不按顺序)
user_info(name = "77",age=22 ,gender="女")
# 缺省参数（默认值必须在最后）
def user_info(name,age,gender = "男"):
    print(f"姓名是{name},年龄是{age},性别是{gender}")
user_info("66",12)
user_info("66",12,gender="女")

# 不定长参数
def user_info(*args):
    print(args)
user_info("77","sb",1,2,3)

# 关键字传递(必须键对值)
def user_info(**kwargs):
    print(kwargs)
user_info(name = "kk",age = 12)

# 函数作为参数传入
def test_func(computer):
    result = computer(3,4)
    print(f"computer的类型是{type(computer)}")
    print(result)

def computer(x,y):
    return x+y
test_func(computer)

# lambda匿名函数
test_func(lambda a,b:a*b)
"""
def add(x,y):
    return x+y
test_func(add)
test_func(lambda a,b:a+b)