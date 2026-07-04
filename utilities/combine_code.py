import os

print(os.getcwd())

def combine(dir, output_filename, ext):
    output = ""
    paths = []

    for dirpath, dirnames, filenames in os.walk(dir):
        for filename in filenames:
            if filename.endswith(ext):
                paths.append(os.path.join(dirpath, filename))
    paths.sort()

    for filename in paths:
        output += "#" * 20 + "\n"
        output += "# " + filename + "\n"
        output += "#" * 20 + "\n\n"
        with open(filename, "r", encoding="utf-8") as f:
            output += f.read()
        output += "\n"

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(output)

combine("core", "utilities\\output\\combined_code.py", ".py")
combine("config", "utilities\\output\\combined_config.txt", ".json")
