# my_list = [[1, 2, 3, 4, 5, 6, 7, 8, 9],[1,3,5,6,7,]]
# print(my_list[1][-2])
"""
mylist = ["itheima","itcat","python"]
index = mylist.index("itheima")
print(f"itheima在列表中的索引是:{index}")
mylist[0] = "chuanzhi"
print(mylist)
mylist.insert(2,"kk")
print(mylist)
mylist.append("77")
print(mylist)
mylist2 = [1,2,3,"love"]
mylist.extend(mylist2)
print(mylist)

# 删除
mylist = ["itheima","itcat","python"]
del mylist[2]
print(mylist)
mylist = ["itheima","itcat","python"]
element = mylist.pop(2)
print(f"删除之后的内容为:{mylist}，去除的内容是:{element}")

# 删除第一个搜索到的指定元素
mylist = ["itheima","itcat","python","itcat","itheima"]
mylist.remove("itheima")
print(f"删除之后为:{mylist}")

# 清空列表内容
mylist = ["itheima","itcat","python","itcat","itheima"]
mylist.clear()
print(mylist)

mylist = ["itheima","itcat","python","itcat","itheima"]
count = mylist.count("itheima")
print(f"itheima的个数是:{count}")

mylist = ["itheima","itcat","python","itcat","itheima"]
count = len(mylist)
print(f"有:{count}个元素")

# while和for遍历列表
def list_while_func():
    my_list = ["kk","77","python"]
    index = 0
    while index < len(my_list):
        element = my_list[index]
        print(f"列表的元素:{element}")
        index += 1
list_while_func()


def list_for_func():
    my_list = ["kk","77","python"]
    for element in my_list:
        print(element)
list_for_func()
"""

# 元组:一旦定义完成就不可以修改
t5 = ((1,2,3),(4,5,6))
num = t5[1][2]
print(num)

t6 = ("kk","77","python")
index = t6.index("77")
print(index)

t7 = ("kk","77","python","kk","77","python")
num = t7.count("kk")
print(num)

t8 = ("kk","77","python","kk","77","python")
num = len(t8)
print(num)

index = 0
while index < len(t8):
    print(f"{t8[index]}")
    index += 1

for element in t8:
    print(f"2;{element}")

