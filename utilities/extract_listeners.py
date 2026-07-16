import os
from collections import defaultdict

dir = "core"
output = "utilities\\output\\listeners.md"

class ListenerInfo:
    def __init__(self):
        self.namespace = None
        self.name = None
        self.event_name = None
        self.priority = None
        self.priority_number = None

def parse(f, path, type):
    listeners = []
    cur_listener = None
    root = path.replace("\\", ".")[5:-3] + "."  # Windows
    namespace = []
    for line in f.readlines():
        if not line.strip():
            continue
        indents = len(line) - len(line.lstrip())
        assert indents % 4 == 0  # PEP 8
        num_indents = indents // 4
        line = line.strip()
        if line.startswith("@event.member_" + type):
            cur_listener = ListenerInfo()
            content = line[15 + len(type):-1]
            if "," in content:
                priority, name = content.split(", ", 1)
                cur_listener.event_name = name.strip()[1:-1]
            else:
                priority = content
            assert priority.startswith("event.ListenerPriority.")
            cur_listener.priority = priority[23:].strip().lower()
            constants = {"start": 1000, "pre_process": 100, "execute": 0, "post_process": -100, "end": -1000}
            cur_listener.priority_number = eval(cur_listener.priority, constants)
        elif line.startswith("def ") and cur_listener is not None:
            end = line.find("(")
            func_name = line[4:end].strip()
            cur_listener.namespace = root + ".".join(namespace[:num_indents])
            cur_listener.name = func_name
            if cur_listener.event_name is None:
                cur_listener.event_name = func_name
            listeners.append(cur_listener)
            cur_listener = None
        elif line.startswith("class"):
            end = line.find("(")
            class_name = line[6:end].strip()
            namespace = namespace[:num_indents] + [class_name]
    return listeners

def extract(file, type):
    result = defaultdict(list)

    for dirpath, dirnames, filenames in os.walk(dir):
        for filename in filenames:
            if filename.endswith(".py"):
                path = os.path.join(dirpath, filename)
                with open(path, "r", encoding="utf-8") as f:
                    for listener in parse(f, path, type):
                        result[listener.event_name].append(listener)

    result = dict(result)

    file.write(f"# {type.title()}s\n\n")
    for event_name, listeners in sorted(result.items()):
        file.write(f"## {event_name}\n\n")
        for listener in sorted(listeners, key=lambda l: l.priority_number, reverse=True):
            file.write(f"- {listener.name} at {listener.namespace}  <{listener.priority} = {listener.priority_number}>\n")
        file.write("\n")

with open(output, "w", encoding="utf-8") as f:
    extract(f, "listener")
    extract(f, "resolver")
