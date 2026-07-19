# 循环两个要素：条件和操作
"""
i = 0
while i < 100:
    print("xiaomei")
    i += 1
"""
# 求一到一百的和
"""sum = 0
i = 1

while i <= 100:
    sum += i
    i += 1
print(sum)
"""
"""
# 1-100猜数字
import random
num = random.randint(1, 100)
count = 0
# 通过一个布尔类型的变量，做循环是否继续的标记
flag = True
while flag:
    guess_num = int(input("请输入你猜的数字"))
    count += 1
    if guess_num == num:
        print("猜对了")
        flag = False
    else :
        if guess_num > num:
            print("大了")
        else :
            print("小了")
print(f"猜了{count}次")



import random
num = random.randint(1, 100)
count = 0
flag = True
while flag:
    guess_num = int(input("请输入你猜的数字"))
    count += 1
    if guess_num == num:
        print("猜对了")
        flag = False
    else :
        if guess_num > num:
            print("大了")
        else :
            print("小了")
print(f"你猜了{count}次")


i = 1
while i <= 100:
    print(f"今天是第{i}天")

    j = 1
    while j <= 10:
        print(f"送给小妹的第{j}支花")
        j += 1

    print("love you ")
    i += 1
print(f"坚持到第{i-1}")


# 99乘法表
i = 1
while i <= 9:
    j = 1
    while j <= i:
        print(f"{j}*{i}={j*i}\t",end="")
        j += 1
    i += 1
    print()
    

# for循环，遍历语句，看看有多少个字母a
count = 0
name = "itheima is a brand"
for x in name:
    if x == "a":
        count += 1
print(f"{count}个")


# range语句
range(10,20,2)
for i in range(10,20,2):
    print(i, end=" ")



i = 1
for i in range (1,101):
    print(f"今天是{i}")
    for j in range (1,11):
        print(f"送的{j}个")
    print(f"第{i}天")
print(f"{i}天，成功")
"""

# continue & break 语句
# 发工资案例
money = 10000
for i in range(1, 21):
    import random
    score  = random.randint(1,10)
    if score < 5:
        print(f"员工{i}绩效分{score}不满足，下一位")
        continue

    if money >= 1000:
        money -= 1000
        print(f"员工{i}，满足条件发放工资1000，公司账户余额{money}")
    else :
        print(f"余额不足，当前余额：{money}，不足以发工资，不发了，下个月再发")
        break