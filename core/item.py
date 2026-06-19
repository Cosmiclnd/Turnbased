class Item:
    def __init__(self, nameid, name, master=None):
        self.nameid = nameid
        self.name = name
        self.master = master
    
    def dead(self):
        return self.master.dead() if self.master else False
    
    def get_info(self):
        return {"nameid": self.nameid, "name": self.name}

class DeadToggle(Item):
    def __init__(self, master=None):
        super().__init__("dead_toggle", "Dead Toggle", master)
        self.dead_toggle = False
    
    def dead(self):
        if super().dead():
            return True
        return self.dead_toggle

class ItemList(list[Item]):
    def refresh(self):
        self[:] = [item for item in self if not item.dead()]
