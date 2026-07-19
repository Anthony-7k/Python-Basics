print("1+1=",1+1)
print("1*1=",1*1)
print("4/2=",4/2)
print("9//2=",9//2)

# 复合赋值
num = 11
num *= 2
print("num *= 2",num)
num = 11
num //= 2
print("num //= 2",num)
num **= 2
print("num **= 2",num)
# 单双三引号使用方式
name = '"你好巴拉巴拉"'
print(name)
name = "'你好巴拉巴拉'"
print(name)
name = """你好巴拉巴拉"""

# \转义字符
name = "\" 你好巴拉巴拉 \""
print(name)
name = '\' 你好巴拉巴拉 \''
print(name)

# 字符串拼接
name = "anthony"
address = "LA"
print("我的名字是：" + name + "，我住在：" + address)

# 无法和非字符串进行拼接

# 占位符拼接
nume = 77
print("我好想%s"%nume)

class_num = 57;
avg_salary = 8888;
message = "Python学科：广东%s期 ，平均工资：%s"%(class_num,avg_salary)
print(message)

name = "我想你"
date = 2026
money = 1000000.123456
message = ("公司名为：%s ，成立于%d ，市值约%f")%(name,date,money)
print(message)
print(f"公司名为：{name},成立于{date},市值约{money}")

# 字符串格式化
num1=11
num2=11.345
print("数字11宽度限制5，结果是：%5d"%num1)
print("数字11宽度限制2，结果是：%2d"%num1)
print("数字2的宽度限制为7，精度为3，结果是：%7.3f"%num2)
print("数字2的宽度限制为5，精度为2，结果是：%5.2f"%num2)

# 字符串格式化2
name = "我想你"
date = 2026
money = 1000000.123456
message = ("公司名为：%s ，成立于%d ，市值约%f")%(name,date,money)
print(message)

# 表达式进行字符串格式化
print("1*1的结果是：%d"%(1*1))
print(f"1*1的结果是：{1*1}")
print("字符串在python中的类型是：%s"%type("字符串"))

name = "传智博客"
stock_price = 19.99
stock_code = "003032"
stock_price_growth_factor = 1.2
growth_day = 7
print(f"公司：{name} 股票代码:{stock_code} 当前股价：{stock_price} ")
print("每日增长系数是：%.2f,经过 %d天的增长之后，股价达到了%.2f"%(stock_price_growth_factor,growth_day,stock_price*stock_price_growth_factor**growth_day))


name = input("你是谁")
print(f"我知道了你是{name}")
print("你是：%s"%name)
