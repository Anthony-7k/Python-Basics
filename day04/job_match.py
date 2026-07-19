print("岗位匹配测试")
python_score = int(input("请输入python的分数"))
database_score = int(input("请输入database的分数"))
project_score = int(input("请输入project的分数"))
# 先判断输入是否合法
if python_score < 0 or python_score > 100:
    print("格式有误")
elif database_score < 0 or database_score > 100:
    print("格式有误")
elif project_score < 0 or project_score > 100:
    print("格式有误")
# 分数分80、60
if python_score > 80 and  database_score >80 and python_score > 80:
    print("等级为A，高度匹配")
elif python_score > 60 and  database_score >60 and python_score > 60:
    print("等级为B，基本匹配")
elif python_score > 60 or  database_score >60 or python_score > 60:
    print("等级为C，匹配低")
else :
    print("等级为D，不予匹配")