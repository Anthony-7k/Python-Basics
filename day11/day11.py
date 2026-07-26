"""
try:
    f = open("D:/abc.txt","r",encoding="UTF-8")
except:
    print("出现异常了，因为文件不存在，将r改为w")
    f = open("D:/abc.txt","w",encoding="UTF-8")
try:
    print(name)
except NameError as e:
    print("出现了变量未定义的异常")
    print(e)

try:
    1/0
except (NameError, ZeroDivisionError) as e:
    print("出现变量未定义，除以0的错误")

try:
    f = open("D:/12c.txt","r",encoding="UTF-8")
except Exception as e:
    print("出现异常了")
    f = open("D:/12c.txt", "w", encoding="UTF-8")
else:
    print("没有异常")
finally:
    print("有没有异常都关闭")
    f.close()

def func1():
    print("func1,开始执行")
    num = 1/0
    print("func1,结束执行")
def func2():
    print("func2,开始执行")
    func1()
    print("func2,结束执行")
def main():
    try:
        func2()
    except Exception as e:
        print(f"出现异常，异常是：{e}")
main()


# 模块
# 模块的导入
import time
print("你好")
time.sleep(5)     # 通过.就可以使用模块内的功能
print("我好")

# form ..... import.....针对某一个功能使用
from time import sleep
import time
print("你好")
sleep(5)
print("我好")


# 通过*导入所有功能
from time import*
print("你好")
sleep(5)     # 通过.就可以使用模块内的功能
print("我好")

# import 加别名
import time as t
print("你好")
t.sleep(5)     # 通过.就可以使用模块内的功能
print("我好")

from time import sleep as t
print("你好")
t(5)     # 通过.就可以使用模块内的功能
print("我好")

# 自定义模块
import my_moldue1
my_moldue1.test(1,2)
import my_moldue2
my_moldue2.test(1,2)

from my_moldue1 import*
test_a(1,2)
test_b(1,2)

import my_moldue1
import my_package.my_module1
import my_package.my_module2
my_package.my_module1.info_print()
my_package.my_module2.info_print()


from my_package import my_module1
from my_package import my_module2
my_module1.info_print()
my_module2.info_print()

from my_package.my_module1 import info_print1
from my_package.my_module2 import info_print2
info_print1()
info_print2()
"""
import my_utils.str_util
from my_utils import file_util
print(my_utils.str_util.str_reverse("hello"))

print(my_utils.str_util.substr("hello",0,4))

file_util.append_to_file("D://t5.txt","hello")
file_util.print_file_info("D://t5.txt")