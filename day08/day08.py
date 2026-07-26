"""
my_str = "itheima"
print(my_str[0])
print(my_str[1])
print(my_str[3])
value = my_str.index("h")
print(f"h在:{value}")

my_str = "itheima and itcat"
new_my_str = my_str.replace("it", "程序")
print(new_my_str)

my_str = "hello itheima itcat"
my_str_list = my_str.split(" ")
print(f"将字符串分割后得到：{my_str_list}，类型是：{type(my_str_list)}")

my_str = "   itheima and itcat "
new_my_str = my_str.strip()
print(f"字符串{new_my_str}")

my_str = "12itheima and itcat21"
new_my_str = my_str.strip("12")
print(f"字符串{new_my_str}")


my_str = "itheima and itcat"
count = my_str.count("it")
print(f"it出现的次数是{count}")

my_str = "itheima and itcat"
length = len(my_str)
print(f"长度是{length}")

my_str = "itheima itcat boxuegu"
count = my_str.count("it")
new_str = my_str.replace(" ","|")
new_str2 = new_str.split("|")
print(count)
print(new_str)
print(new_str2)

# 序列
# 对list进行切片
my_list = [0,1,2,3,4,5,6]
resuly1 = my_list[1:4]
print(resuly1)
#
my_tuple = (0,1,2,3,4,5,6)
resuly2 = my_tuple[1:4]
print(resuly2)
# 对字符串进行切片
my_str = [0,1,2,3,4,5,6,7]
resuly3 = my_str[::2]
print(resuly3)
# 对str进行切片，从头开始，到最后结束，步长-1
my_str = "01234567"
resuly4 = my_str[::-1]
print(resuly4)

# 对列表进行切片
my_list = [0,1,2,3,4,5,6]
resuly5 = my_list[3:1:-1]
print(resuly5)

# 对元组进行切片
my_tuple = (0,1,2,3,4,5,6)
resuly6 = my_tuple[::-2]
print(resuly6)


# 集合
my_set = {"itheima", "itcat", "boxuegu"}
my_set.add("77")
print(my_set)
my_set = {"itheima", "itcat", "boxuegu"}
my_set.remove("itheima")
print(my_set)
my_set = {"itheima", "itcat", "boxuegu"}
element = my_set.pop()
print(f"取出之后是{my_set}，出去的是{element}")
my_set = {"itheima", "itcat", "boxuegu"}
my_set.clear()
print(my_set)


# 取两个集合的差值
set1 = {1,2,3}
set2 = {1,5,6}
set3 = set1.difference(set2)
print(set3)
# 消除两个集合的差值
set1 = {1,2,3}
set2 = {1,5,6}
set1.difference_update(set2)
print(set1)# set1当中会删除和set2相同的元素
print(set2)
# 合并为一个集合
set1 = {1,2,3}
set2 = {1,5,6}
set3 = set1.union(set2)
print(set3)
# 统计集合数量（统计也会去重）
set1 = {1,2,3,1,2,3}
set2 = {1,5,6}
num = len(set1)
print(num)
# 集合的遍历(集合不支持下标索引，不能用while循环)
set1 = {1,2,3,4,5}
for num in set1:
    print(num)

# 字典
my_dict =  {"王力宏":88,"林俊杰":77,"周杰伦":66}
score =  my_dict["林俊杰"]
print(score)

# 定义嵌套字典
stu_score_dict = {
    "王力宏":{
        "语文":77,
        "数学":66,
        "英语":33

    },"周杰伦":{
        "语文":88,
        "数学":86,
        "英语":55
    },"林俊杰":{
        "语文":99,
        "数学":96,
        "英语":66
    }
}
score = stu_score_dict["周杰伦"]["语文"]
print(score)
"""
my_dict = {"周杰伦":99,"林俊杰":88,"张学友":77}
my_dict["张信哲"]=66
print(my_dict)
my_dict["周杰伦"]=33
print(my_dict)
score= my_dict.pop("周杰伦")
print(f"删除之后{my_dict},删除的是{score}")
my_dict.clear()
print(my_dict)

my_dict = {"周杰伦":99,"林俊杰":88,"张学友":77}
keys = my_dict.keys()
print(keys)
# 遍历字典
# 方式1 通过key
for key in keys:
    print(f"字典的key是{key}")
    print(f"字典的value是{my_dict[key]}")

# 方式2 for循环
for key in my_dict:
    print(f"字典的key是{key}")
    print(f"字典的value是{my_dict[key]}")

# 统计字典数量
num = len(my_dict)
print(num)