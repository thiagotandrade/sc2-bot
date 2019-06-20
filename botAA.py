'''
    bot_ai.py:
        Linha 518. O parametro max_distance por padrão é 20 (está 8)
    
    Ideias:
    -> Implementar as estratégias de early e late
    -> Cancelar a construção de estruturas que estejam sendo atacadas.
    -> Definir quais unidades inimigas devem ser atacadas primeiro (priorizar a unidade mais "valiosa" que esteja mais perto)
    -> Sobre Upgrades:
        It usually comes down to preference but most people will tell you to prioritize weapons upgrades against Zerg and fellow Protoss, and to prioritize armor upgrades against Terran.
        Keep in mind this is when working off one Forge, as soon as you get two Forges that you can continuously upgrade out of, this is irrelevant.
        Also, save shields for last ALWAYS
    -> No começo, dar prioridade à construção do gateway > cybernetics core antes do próximo nexus
    
    função main_base_ramp

    Olhar get_available_abilities no bot_ai pra usar as habilidades das unidades quando for batalhar
'''
import random

import sc2
from sc2 import Difficulty, Race, maps, run_game
from sc2.constants import (
    ASSIMILATOR, CYBERNETICSCORE, GATEWAY, NEXUS, 
    PROBE, PYLON, STALKER, EFFECT_CHRONOBOOSTENERGYCOST, 
    CHRONOBOOSTENERGYCOST, WARPGATE, FORGE, TEMPLARARCHIVE,
    PHOTONCANNON, RESEARCH_WARPGATE, MORPH_WARPGATE,
    WARPGATETRAIN_ZEALOT, WARPGATETRAIN_STALKER, WARPGATETRAIN_HIGHTEMPLAR,
    WARPGATETRAIN_DARKTEMPLAR, WARPGATETRAIN_SENTRY)
from sc2.player import Bot, Computer


class BotAA(sc2.BotAI):
    def __init__(self):
        self.actions_list = []
        self.iteration = 0
        self.max_workers = 75
        # Number of times that we used Chronoboost on nexus
        self.cb_on_nexus = 0
        
        self.strategy = "e"
        # Below are the initial values for the early game strategy
        self.gateways_per_nexus = 1
        self.cannons_per_nexus = 1
        # Minimum number of army units to attack
        self.min_army_size = 15
        self.proxy_built = False
        # Probe responsible for scouting
        self.scout = None
        
        

    async def on_step(self, iteration):
        self.iteration = iteration

        if self.strategy == "e":
            await self.early_game_strategy()
        elif self.strategy == "l":
            await self.late_game_strategy()

        # TODO: Define more conditions for the transition to late game:
        # When warpgate is done?
        if self.strategy == "e" and (self.time > 180):
            await self.chat_send("Entering late game strategy. Current time: " + self.time_formatted)
            self.strategy = "l"
            self.gateways_per_nexus = 2.5
            self.min_army_size = 30
            self.cannons_per_nexus = 2

        if self.iteration % 10 == 0:
            await self.distribute_workers()

        await self.build_pylons()
        await self.manage_bases()
        await self.offensive_force_buildings()
        await self.build_offensive_force()
        await self.attack()
        await self.idle_workers()
        #await self.build_defenses()
      
        #Execute all orders
        await self.execute_actions_list()


    async def do(self, action):
        self.actions_list.append(action)


    # TODO: implement early game strategy
    '''
        Basicamente, devemos construir 1 gateway, 1 cibernetics, 1 forge e 1 nexus
        Começar a produzir unidades de ataque
    '''
    async def early_game_strategy(self):
        prefered_base_count = 2

        # Expand up to 2 nexus
        if self.units(NEXUS).amount < prefered_base_count:
            await self.expand()

        # In early game, we only want 1 forge
        if self.units(GATEWAY).ready and self.units(CYBERNETICSCORE).ready and not self.units(FORGE).exists and not self.already_pending(FORGE):
            await self.build_forge()

        # Research Warpgate
        if self.units(CYBERNETICSCORE).ready.exists and self.can_afford(RESEARCH_WARPGATE):
            cybernetics = self.units(CYBERNETICSCORE).first
            if cybernetics.noqueue and await self.has_ability(RESEARCH_WARPGATE, cybernetics):
                await self.do(cybernetics(RESEARCH_WARPGATE))

        # Construir um photo cannon
        # Mandar fazer scout na base inicial


        # Build pylon near enemy base and use the probe who as scout
        # TODO: Choose better condition to place proxy (maybe after warpgate is searched. It will prob need to be on late game)
        if not self.proxy_built and self.units(CYBERNETICSCORE).amount >= 1 and self.can_afford(PYLON):
            worker = self.units(PROBE).closest_to(self.find_target(self.state))
            
            if worker is not None:   
                p = self.game_info.map_center.towards(self.find_target(self.state), 25)
                        
                await self.build(PYLON, near=p, unit=worker)
                self.proxy_built = True
                if not self.scout:
                    self.scout = worker
        '''
            construir algumas defesas
            construir pylon > gateway > cybernetics > pylon
            assim que gateway estiver pronto, construir 1 zealot
            assim que cybernetics core estiver pronto
                * começar a construir stalkers
                * começar a pesquisar warpgate
            construir forge
        '''


    # TODO: implement late game strategy
    async def late_game_strategy(self):
        
        # Make sure to expand in late game (every 2.5 minutes)
        expand_every = 2.5 * 60 # Seconds
        prefered_base_count = 1 + int(self.time / expand_every)
        current_base_count = self.units(NEXUS).ready.filter(lambda unit: unit.ideal_harvesters >= 10).amount # Only count bases as active if they have at least 10 ideal harvesters (will decrease as it's mined out)

        if current_base_count < prefered_base_count:
            await self.expand()

        '''
                        EARLY                               LATE
            (Gateway > Cybernetics Core) -> (Twilight Council > Templar Archives)
                                         -> (Robotics Facility > Robotics Bay)
            Construir robotics bay, twilight consul para construir Colossus e High Templar
        '''


    async def manage_upgrades(self):
        '''
        Early Game:
            Se já existir cybernetics e estiver idle, treinar warpgate
            Se já existir forge e não estiver treinando, treinar arma nv 1
            Se já existir forge e não estiver treinando, treinar armor nv 1
        Late game:
            Pesquisar Upgrades de arma e armor nivel 2 no forge
            Pesquisar thermal lance (Robotics Bay) e psionic storm (templar archives)
        '''
        return

    # Execute all orders in self.actions_list and reset it
    async def execute_actions_list(self):
        await self.do_actions(self.actions_list)
        self.actions_list = [] # Reset actions list
              

    async def build_workers(self, nexus):
        if nexus.is_idle and self.can_afford(PROBE) and nexus.assigned_harvesters <= (nexus.ideal_harvesters + 3) and self.workers.amount < self.max_workers and self.supply_used < 180:
            await self.do(nexus.train(PROBE))

    # Force idle workers near nexus to mine
    async def idle_workers(self):
        if self.workers.idle.exists:
            worker = self.workers.idle.first
            await self.do(worker.gather(self.state.mineral_field.closest_to(self.units(NEXUS).random)))
            

    async def build_pylons(self):
        nexus = self.units(NEXUS).random
        if not nexus:
            return

        # supply_left: Available Population to Produce 
        if self.supply_left <= 5 and not self.already_pending(PYLON) and self.supply_cap < 190:
                if self.can_afford(PYLON):
                    await self.build(PYLON, near=nexus.position.towards(self.game_info.map_center, 10))


    async def build_assimilators(self, nexus):
        # We want to build assimilators only after we start building a gateway
        if self.units(GATEWAY).exists:
            vespenes = self.state.vespene_geyser.closer_than(15.0, nexus)
            for vespene in vespenes:
                if not self.can_afford(ASSIMILATOR):
                    break
                worker = self.select_build_worker(vespene.position)
                if worker is None:
                    break
                if not self.units(ASSIMILATOR).closer_than(1.0, vespene).exists:
                    await self.do(worker.build(ASSIMILATOR, vespene))


    async def build_defenses(self):
        nexus = self.units(NEXUS).closest_to(self.find_target(self.state))
        if self.units(FORGE).ready and self.units(PHOTONCANNON).amount / self.units(NEXUS).amount <= self.cannons_per_nexus and self.can_afford(PHOTONCANNON):
            pylon = self.units(PYLON).closer_than(50, nexus).random
            if pylon is not None:
                await self.build(PHOTONCANNON, near=pylon)
        

    async def expand(self):
        if self.can_afford(NEXUS) and not self.already_pending(NEXUS):
            await self.expand_now()


    async def offensive_force_buildings(self):
        if self.units(PYLON).ready.exists:
            pylon = self.units(PYLON).ready.closest_to(self.units(NEXUS).random)
            position = pylon.position.towards(self.game_info.map_center)
           
            if self.units(GATEWAY).ready.exists and not self.units(CYBERNETICSCORE):
                if self.can_afford(CYBERNETICSCORE) and not self.already_pending(CYBERNETICSCORE):
                    await self.build(CYBERNETICSCORE, near=position)
            
            elif self.units(GATEWAY).amount / self.units(NEXUS).amount <= self.gateways_per_nexus:
                if self.can_afford(GATEWAY) and not self.already_pending(GATEWAY):
                    await self.build(GATEWAY, near=position)


    async def build_offensive_force(self):
        # For each gateway, if we can, morph into warpgate. If not, train stalker
        for gw in self.units(GATEWAY).ready.idle:
            if await self.has_ability(MORPH_WARPGATE, gw) and self.can_afford(MORPH_WARPGATE):
                await self.do(gw(MORPH_WARPGATE))
            else:
                if self.can_afford(STALKER) and self.supply_left > 0:
                    await self.do(gw.train(STALKER))

        for warpgate in self.units(WARPGATE).ready.idle:
            if await self.has_ability(WARPGATETRAIN_ZEALOT, warpgate):
                pos = self.units(PYLON).closest_to(self.find_target(self.state)).position.to2.random_on_distance(4)
                placement = await self.find_placement(WARPGATETRAIN_STALKER, pos, placement_step=1)
                if placement is not None:
                    await self.do(warpgate.warp_in(STALKER, placement))


    def find_target(self, state):
        if len(self.known_enemy_units) > 0:
            return random.choice(self.known_enemy_units)
        elif len(self.known_enemy_structures) > 0:
            return random.choice(self.known_enemy_structures)
        else:
            return self.enemy_start_locations[0]


    async def attack(self):
        if self.units(STALKER).amount > self.min_army_size:
            for s in self.units(STALKER).idle:
                await self.do(s.attack(self.find_target(self.state)))

        elif self.units(STALKER).amount > 3 and len(self.known_enemy_units) > 0:
            for s in self.units(STALKER).idle:
                await self.do(s.attack(random.choice(self.known_enemy_units)))


    async def manage_bases(self):
        # Managing workers, assimilators, chronoboost and nexus defenses
        for nexus in self.units(NEXUS).ready:

            await self.build_workers(nexus)
            await self.handle_chronoboost(nexus)
            await self.build_assimilators(nexus)


    # Check if a unit has an ability available
    async def has_ability(self, ability, unit):
        abilities = await self.get_available_abilities(unit)
        if ability in abilities:
            return True
        else:
            return False

    async def handle_chronoboost(self, nexus):
        '''
            Early (e): Cybernetics Core > gateway/warpgate > Nexus
            Late (l): abilities > upgrades > probes > units
                    Forge > Templar Archives > Cybernetics Core > Robotics Bay > Warpgate
        '''
        if await self.has_ability(EFFECT_CHRONOBOOSTENERGYCOST, nexus) and nexus.energy >= 50:
            if self.strategy == "e":
                # Focus on CBing Warpgate research (we'll only have 1 cyber)
                if self.units(CYBERNETICSCORE).ready.exists:
                    cybernetics = self.units(CYBERNETICSCORE).first
                    if not cybernetics.is_idle and not cybernetics.has_buff(CHRONOBOOSTENERGYCOST):
                        await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, cybernetics))
                        return # Don't CB anything else this step

                # Next, prioritize CB on gates
                for gateway in (self.units(GATEWAY).ready | self.units(WARPGATE).ready):
                    if not gateway.is_idle and not gateway.has_buff(CHRONOBOOSTENERGYCOST):
                        await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, gateway))
                        return # Don't CB anything else this step
                
                if not nexus.is_idle and not nexus.has_buff(CHRONOBOOSTENERGYCOST) and self.cb_on_nexus < 2:
                    await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, nexus))
                    self.cb_on_nexus += 1
                    return # Don't CB anything else this step

            # Late game (l)      
            else:
                for forge in self.units(FORGE).ready:
                    if not forge.is_idle and not forge.has_buff(CHRONOBOOSTENERGYCOST):
                        await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, forge))
                        return # Don't CB anything else this step
                
                if self.units(TEMPLARARCHIVE).ready.exists:
                    templar = self.units(TEMPLARARCHIVE).first
                    if not templar.is_idle and not templar.has_buff(CHRONOBOOSTENERGYCOST):
                        await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, templar))
                        return # Don't CB anything else this step

                for gateway in (self.units(GATEWAY).ready | self.units(WARPGATE).ready):
                    if not gateway.is_idle and not gateway.has_buff(CHRONOBOOSTENERGYCOST):
                        await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, gateway))
                        return # Don't CB anything else this step


    async def build_forge(self):
        if not self.already_pending(FORGE) and self.can_afford(FORGE):
            pylons = self.units(PYLON).ready
            if len(pylons) > 0:
                await self.build(FORGE, near=pylons.closest_to(self.units(NEXUS).first))

def main():
    sc2.run_game(sc2.maps.get("Abyssal Reef LE"), [
        Bot(Race.Protoss, BotAA()),
        Computer(Race.Terran, Difficulty.Hard)
    ], realtime=False)

if __name__ == '__main__':
    main()