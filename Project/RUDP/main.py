# 用来检查两个文本是否一致的小工具
f1 = open("alice.txt", "rb")
f2 = open("127.0.0.1.33123", "rb")
f3 = open("README", "rb")

lines1 = f1.readlines()
lines2 = f2.readlines()
len1 = len(lines1)
len2 = len(lines2)
for i in range(0, len1):

    if lines1[i] != lines2[i]:
        print("compare")
        print(lines1[i])
        print(lines2[i])
