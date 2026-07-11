class Item:
    def __init__(self, nameid, name, master=None):
        self.nameid = nameid
        self.name = name
        self.master = master
    
    def dead(self):
        return self.master.dead() if self.master else False
    
    def on_removed(self, list):
        pass

class DeadToggle(Item):
    def __init__(self, master=None):
        if master is None:
            super().__init__("dead_toggle", "Dead Toggle")
        else:
            super().__init__(master.nameid, master.name, master)
        self.dead_toggle = False
    
    def dead(self):
        if super().dead():
            return True
        return self.dead_toggle

class ItemList(list):
    def refresh(self):
        dead = [item for item in self if item.dead()]
        self[:] = [item for item in self if not item.dead()]
        for item in dead:
            item.on_removed(self)
