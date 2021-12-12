f1 = open("README", "rb")
f2 = open("127.0.0.1.33123", "rb")
lines1 = f1.readlines()
lines2 = f2.readlines()
len1 = len(lines1)
len2 = len(lines2)
for i in range(0, len1):
    if lines1[i] != lines2[i]:
        print("compare")
        print(lines1[i])
        print(lines2[i])
