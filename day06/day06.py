"""str1 = input("请输入")
#str2 = "itcat"
#str3 = "python"
def my_len(data):
    count = 0
    for i in data:
        count += 1
    print(f"长度为{count}")

my_len(str1)
#my_len(str2)
#my_len(str3)

x = int(input("输入x"))
y = int(input("输入y"))
def add(x,y):
    result = x + y
    print(f"{x} + {y} = {result}")
def sub(x,y):
    result = x - y
    print(f"{x} - {y} = {result}")
def mul(x,y):
    result = x * y
    print(f"{x} * {y} = {result}")
def div(x,y):
    result = x / y
    print(f"{x} / {y} = {result}")
add(x,y)
sub(x,y)
mul(x,y)
div(x,y)


def add(a,b):

    reult = a+b
    return reult
r = add(3,4)
print(r)
"""

# atm案例
money = 5000000
name =  None
name = input("请输入你的姓名")
def query(show_header):
    if show_header:
        print("--------查询余额-------")
    print(f"{name},您好，您的余额剩余{money}元")
def saving(num):
    global money
    money += num
    print("--------存款-------")
    print(f"{name},您好，您存款{num}元成功")
    query(False)
def get_money(num):
    global money
    money -= num
    print("--------取款-------")
    print(f"{name},您好，您取款{num}元成功")
    query(False)
def main():
    print("--------主菜单-------")
    print(f"{name},您好，欢迎来到atm")
    print("查询余额\t[输入1]")
    print("存款\t\t[输入2]")
    print("取款\t\t[输入3]")
    print("退出\t\t[输入4]")
    return input("请输入你的选择")
while True:
    keyboard_input = main()
    if keyboard_input == "1":
        query(True)
        continue #通过continue进行下一次循环，回到主菜单
    elif keyboard_input == "2":
        num = int(input("您要存多少钱"))
        saving(num)
        continue
    elif keyboard_input == "3":
        num = int(input("您要取多少钱"))
        get_money(num)
        continue
    else:
        print("程序退出")
        break



