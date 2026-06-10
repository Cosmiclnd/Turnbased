import os

print(os.getcwd())

output = ""
paths = []

for dirpath, dirnames, filenames in os.walk("core"):
    for filename in filenames:
        if filename.endswith(".py"):
            paths.append(os.path.join(dirpath, filename))
paths.sort()

for filename in paths:
    output += "#" * 20 + "\n"
    output += "# " + filename + "\n"
    output += "#" * 20 + "\n\n"
    with open(filename, "r", encoding="utf-8") as f:
        output += f.read()
    output += "\n"

with open("utilities\\output\\combined_output.py", "w", encoding="utf-8") as f:
    f.write(output)
