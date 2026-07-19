# 定义变量存储布尔类型的数据
"""
bool_1 = True
bool_2 = False
print(f"bool_1的内容是是{bool_1}，bool_1的类型是{type(bool_1)}")
print(f"bool_2的内容是是{bool_2}，bool_2的类型是{type(bool_2)}")
"""
# if语句
#age = input("你的年龄是")
"""
age = int(input("你的年龄是"))
if age >= 18:
    print("我已经成年了")
    print("即将步入大学生活")
print("时间过得真快")
"""
# 小练习
"""
print("欢迎来到游乐园")
age = int(input("请输入你的年龄:"))
if age >= 18:
    print("您已成年，需补票")
else:
    print("不需补票")
print("祝您游戏玩愉快")"""


# if elif else
"""height = int(input("请输入你的身高："))
vip_level = int(input("请输入你的VIP等级（1-5）："))

if int(input("请输入你的身高")) < 120:
    print("身高可以免费")
elif int(input("请输入你的VIP等级（1-5）：")) > 3:
    print("等级可以免费")
else:
    print("补票")
"""
"""
print("欢迎来到游乐园")
if int(input("输入你的身高：")) > 120:
    print("身高不可以免费")
    print("vip高，可以免费")
    if int(input("请告诉我你的vip等级：")) >3:
        print("vip等级可以免费")
    else :
        print("需要补票")
else :
    print("玩的开心")
"""


"""
print("领取礼物")
age = int(input("您的年龄是："))
# year = int(input("您的入职时长是："))
# level = int(input("您的级别是："))
if age >= 18:
    print("你是成年人")
    if age < 30:
        print("恭喜你年龄达标")
        if int(input("入职时间")) > 2:
            print("恭喜，年龄和时长都达标，下一步检验")
            if int(input("级别")) >3:
                print("恭喜，年龄,时长和级别都达标，可以领取")
            else :
                print("尽管年龄OK和时长，但是级别未达标，不可领取")
        else :
            print("入职时间不够，不可以领取")
    else :
        print("年龄太大了，不可领取")
else :
    print("年龄太小了，不可以领取")
"""

# 三次猜数字
import random
num = random.randint(1, 10)
guess_num = int(input("输入你要猜的数字"))
if guess_num == num:
    print("恭喜你，第一次就中")
else :
    if(guess_num > num):
        print("大了")
    else :
        print("小了")
    guess_num = int(input("输入第二次你要猜的数字"))
    if guess_num == num:
        print("第二次就中了")
    else :
        if (guess_num > num):
            print("大了")
        else:
            print("小了")
        guess_num = int(input("输入第三次你要猜的数字"))
        if guess_num == num:
            print("第三次就中了")
        else :
            print("三次机会用完了")


