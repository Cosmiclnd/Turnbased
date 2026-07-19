import os

print(os.getcwd())

def combine(dirs, output_filename, exts):
    output = ""
    paths = []

    for dir in dirs:
        for dirpath, dirnames, filenames in os.walk(dir):
            for filename in filenames:
                idx = filename.find(".")
                if idx == -1:
                    continue
                ext = filename[idx:]
                if ext in exts:
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

combine(["core", "client", "mirror_test"], "utilities\\output\\combined_code.py", [".py", ".pyx", ".pxd"])
combine(["config"], "utilities\\output\\combined_config.txt", [".json"])
