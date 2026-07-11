class Features:
    def __init__(self):
        self.features = {}
    
    def get(self, name):
        return self.features.get(name, False)
    
    def use(self, name):
        self.features[name] = True
