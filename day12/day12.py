""""# 设计一个类
class student:
    name = None
    gender = None
    nationality = None
    native_place = None
    age = None
# 创建一个对象
stu_1 = student()
# 对象属性进行赋值
stu_1.name = "林俊杰"
stu_1.gender = "男"
stu_1.nationality = "中国"
stu_1.native_place = "山东"
stu_1.age = 31
print(stu_1.name)
print(stu_1.gender)
print(stu_1.nationality)
print(stu_1.native_place)
print(stu_1.age)

# 定义一个带有成员方法的类
class student:
    name = None
    def say_hi(self):
        print(f"大家好呀，我是{self.name}，欢迎大家多多关照")

    def say_hi2(self,msg):
        print(f"大家好，我是{self.name},{msg}")

stu = student()
stu.name = "jaychou"
stu.say_hi2("哎哟不错哦")

stu2 = student()
stu2.name = "jjlin"
stu2.say_hi2("小伙子我看好你")


# 设计一个闹钟类
class clock:
    id = None
    price = None

    def ring(self):
        import winsound
        winsound.Beep(2000,3000)

clock1 = clock()
clock1.id = "77"
clock1.price = 10
print(f"闹钟编号{clock1.id},价钱{clock1.price}")
clock1.ring()

clock2 = clock()
clock1.id = "33"
clock1.price = 15
print(f"闹钟编号{clock1.id},价钱{clock1.price}")
clock1.ring()


class student:

    def __init__(self, name, age, tel):
        self.name = name
        self.age = age
        self.tel = tel
        print("student类创建了一个类对象")
stu = student("周杰伦",31,"15015115439")
print(stu.name)
print(stu.age)
print(stu.tel)

# 字符串方法
class student:

    def __init__(self, name, age):
        self.name = name
        self.age = age
    # __str__魔术方法
    def __str__(self):
        return f"student类对象：name={self.name},age={self.age}"
    # __lt__魔术方法（只能用于小于或者大于）
    def  __lt__(self, other):
        return self.age < other.age
    # __le__魔术方法（可用于小于等于或者大于等于）
    def __le__(self, other):
        return self.age <= other.age
    # __eq__魔术方法（判断相等不相等）
    def __eq__(self, other):
        return self.age == other.age


stu1 = student("jaychou",41)
stu2 = student("jjlin",41)
print(stu1 == stu2)


# 定义一个类，内部含有私有成员变量和私有成员方法
class phone:
    __current_voltage = 0.8  #手机运行电压
    def __keep_single_core(self):
        print("让cpu以单核模式运行")
    def call_by_5g(self):
        if self.__current_voltage >= 1:
            print("5g通话已开启")
        else:
            self.__keep_single_core()
            print("电量不足，单核模式启动")
phone = phone()
phone.call_by_5g()

# 单继承
class phone:
    IMEI = None
    producer = "kk"
    def call_by_4g(self):
        print("4g通话")
class phone2022(phone):
    face_id = "10001" # 面部识别id
    def call_by_5g(self):
        print("2022年5g通话")

phone = phone2022()
print(phone.producer)
phone.call_by_4g()
phone.call_by_5g()

# 多继承
class phone:
    IMEI = None
    producer = "kk"
    def call_by_4g(self):
        print("4g通话")
class NFCreader:
    nfc_type = "第五代"
    producer = "77"
    def read_card(self):
        print("读卡")
    def write_card(self):
        print("写卡")
class RemoteControl:
    rc_type = "红外遥控"
    def control(self):
        print("红外遥控器")
class myphone(phone,NFCreader,RemoteControl):
    pass
phone = myphone()
phone.call_by_4g()
phone.read_card()
phone.write_card()
phone.control()

class phone:
    IMEI = None
    producer = "kk"

    def call_by_5g(self):
        print("使用5g进行通话")

class myphone(phone):
    producer = "77" # 复写成员属性
    def call_by_5g(self):
        print("开启单核模式")
        # 方式一
        # print(f"父类的厂商是{phone.producer}")
        # phone.call_by_5g(self)
        # 方式二
        print(f"父类的厂商是{super().producer}")
        super().call_by_5g()
        print("关闭单核模式")

Phone = myphone()
Phone.call_by_5g()
print(Phone.producer)

import random

import json
from os import name

# 基础数据类型注解
var_1: int = 10
var_2: str = "itheima"
var_3: bool = True
# 类对象注解
class student:
    pass
stu: student = student()
# 基础容器类型注解
my_list: list[int] = [1,2,3]
mt_tuple: tuple[int,str,bool] = (1,"itheima",True)
my_dict: dict[str,int] = {"itheima":666}

var_1 = random.randint(1,10)  # type:int
var_2 = json.loads('{"name":"zhangsan"}')  # type:dict[str,str]
def func():
    pass
var_3 = func() # type:int
"""
# 函数方法类型注解
def add(x:int,y:int):
    return x + y

def func(data:list) ->list:
    return data