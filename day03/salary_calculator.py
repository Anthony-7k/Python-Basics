base_salary = float(input("请输入你的底薪："))
bonus = float(input("请输入你的奖金："))
deduction = float(input("请输入你的扣款： "))

salary = base_salary + bonus - deduction
print("薪资明细")
print(f"底薪:{base_salary:.2f}")
print(f"奖金:{bonus:.2f}")
print(f"扣款:{deduction:.2f}")
print(f"工资：{salary:.2f}")