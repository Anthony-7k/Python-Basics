# 直接输出
print(type("Hello World"));
print(type(11.456));
print(type(777));

# 方法2
string_type=type("Hello World");
int_type=type(11);
float_type=type(11.456);
print(string_type);
print(int_type);
print(float_type);

# 将数字类型转化为字符串
num_str = str(11);
print(type(num_str),num_str);

float_str = str(11.456);
print(type(float_str),float_str);

# 将字符串转化为数字
num = int(11);
print(type(num),num);

num2 = int("11.456");
print(type(num2),num2);

# 内容限定，数字不能开头