import item

class LightCone(item.Item):
    def __init__(self, nameid, name, path):
        super().__init__(nameid, name)
        self.path = path
        self.target = None
        self.level = None
        self.stacks = None
    
    def apply(self, t):
        self.target = t
    
    def get_record(self):
        return {
            "name": self.nameid,
            "level": self.level,
            "stacks": self.stacks
        }
    
    def set_record(self, record):
        # `name`在target中被处理
        self.level = record["level"]
        self.stacks = record["stacks"]
