import item
import config

class DecisionProvider:
    def start(self):
        pass

    def stop(self):
        pass

    def on_battle_start(self):
        pass

    def notify(self, message):
        pass
    
    def provide_ultimate(self):
        pass
    
    def provide_ultimate_target(self, character):
        pass

    def provide_character_skill_option(self, character):
        pass
    
    def provide_random_rate(self):
        pass

    def provide_random_character_target(self):
        pass

    def provide_random_monster_target(self):
        pass

provider = None

def start_provider(name):
    global provider
    provider = config.load_class("decision", name)()
    provider.start()
