"""logs = [
    "INFO User login",
    "ERROR Database failed",
    "",
    "WARNING Disk almost full",
    "ERROR Timeout",
    "INFO Success",
    "abcdefg",
    "WARNING CPU high",
    "",
    "ERROR Network lost"
]
error_count = 0
warning_count = 0
for log in logs:
    if log =="":
        continue
    if "INFO" not in log and "ERROR" not in log and "WARNING" not in log:
        continue
    if "ERROR"  in log:
        error_count += 1
    if "WARNING"  in log:
        warning_count += 1
print(f"ERROR的数量{error_count}")
print(f"WARNING的数量{warning_count}")
"""

"""
项目名称：日志统计器（Log Counter）

功能：
1. 过滤空日志
2. 过滤无效日志
3. 统计 INFO / WARNING / ERROR 数量
4. 统计有效日志数量
5. 当连续出现3条空日志时停止统计（练习break）
6. 输出统计报告
"""

logs = [
    "INFO User login",
    "ERROR Database failed",
    "",
    "WARNING Disk almost full",
    "ERROR Timeout",
    "INFO Success",
    "abcdefg",
    "WARNING CPU high",
    "",
    "ERROR Network lost",
    "",
    "",
    ""
]

info_count = 0
warning_count = 0
error_count = 0
empty_count = 0
valid_count = 0
for log in logs:
    if log == "":
        empty_count += 1
        print(f"发现空日志，连续{empty_count}条")

        if empty_count == 3:
            print("连续出现空日志，停止统计。")
            break
        continue
    empty_count = 0
    # 判断是否为合法日志
    if "INFO" not in log and "ERROR" not in log and "WARNING" not in log:
        print(f"跳过无效日志:{log}")
        continue
    # 有效日志数量
    valid_count +=1
    if "INFO" in log:
        info_count += 1
    if "WARNING" in log:
        warning_count += 1
    if "ERROR" in log:
        error_count += 1
print(f"日志总数：{len(logs)}")
print(f"有效日志：{valid_count}")
print(f"INFO数量：{info_count}")
print(f"WARNING数量：{warning_count}")
print(f"ERROR数量：{error_count}")
