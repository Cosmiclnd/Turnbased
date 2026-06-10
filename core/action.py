import item

class ActionUnit(item.Item):
    order = 0

    def __init__(self, nameid, name, priority, master=None):
        super().__init__(nameid, name, master)
        self.priority = priority
        self.order = ActionUnit.next_order()
    
    def action_value(self):
        return 0
    
    def sort_key(self):
        return (self.action_value(), -self.priority, self.order)
    
    @classmethod
    def next_order(cls):
        cls.order += 1
        return cls.order

class ActionPriority:
    NORMAL_TURN = 0
    EXTRA_TURN = 1
    FOLLOW_UP = 2
