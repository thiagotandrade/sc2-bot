'''
    bot_ai.py:
        Linha 518. O parametro max_distance por padrão é 20 (está 8)
    -> Implementar as estratégias de early e late
    -> Melhorar a localização na construção das estruturas (tá travando os workers)
    -> Cancelar a construção de estruturas que estejam sendo atacadas.

    Sobre Upgrades:
        It usually comes down to preference but most people will tell you to prioritize weapons upgrades against Zerg and fellow Protoss, and to prioritize armor upgrades against Terran.
        Keep in mind this is when working off one Forge, as soon as you get two Forges that you can continuously upgrade out of, this is irrelevant.
        Also, save shields for last ALWAYS
'''
import random

import sc2
from sc2 import Difficulty, Race, maps, run_game
from sc2.constants import (
    ASSIMILATOR, CYBERNETICSCORE, GATEWAY, NEXUS, 
    PROBE, PYLON, STALKER, EFFECT_CHRONOBOOSTENERGYCOST, 
    CHRONOBOOSTENERGYCOST, WARPGATE, FORGE, TEMPLARARCHIVE)
from sc2.player import Bot, Computer


class BotAA(sc2.BotAI):
    def __init__(self):
        self.actions_list = []
        self.iteration = 0
        self.strategy = "e"
        

    async def on_step(self, iteration):
        self.iteration = iteration

        if self.strategy == "e":
            await self.early_game_strategy()
        elif self.strategy == "l":
            await self.late_game_strategy()

        if self.iteration % 10 == 0:
            await self.distribute_workers()

        await self.build_workers()
        await self.build_pylons()
        await self.build_assimilators()
        await self.expand()
        await self.manage_bases()
        await self.offensive_force_buildings()
        await self.build_offensive_force()
        await self.attack()
      
        #Execute all orders
        await self.execute_actions_list()


    async def do(self, action):
        self.actions_list.append(action)

    # TODO: implement early game strategy
    async def early_game_strategy(self):
        '''
            Treinar probes (Já é feito por outra função) 
            construir pylon > gateway > cybernetics > pylon
            assim que gateway estiver pronto, construir 1 zealot
            assim que cybernetics core estiver pronto, construir 1 adept
        '''
        return

    # TODO: implement late game strategy
    async def late_game_strategy(self):
        return

    # Execute all orders in self.order_queue and reset it
    async def execute_actions_list(self):
        await self.do_actions(self.actions_list)
        self.actions_list = [] # Reset order queue


    async def build_workers(self):
        for nexus in self.units(NEXUS).ready.idle:
            if self.can_afford(PROBE):
                await self.do(nexus.train(PROBE))
    

    async def build_pylons(self):
        # supply_left: Available Population to Produce 
        if self.supply_left <= 6 and not self.already_pending(PYLON) and self.supply_cap < 200:
            nexuses = self.units(NEXUS).ready
            if nexuses.exists:
                if self.can_afford(PYLON):
                    await self.build(PYLON, near=nexuses.first)


    async def build_assimilators(self):
        for nexus in self.units(NEXUS).ready:
            vespenes = self.state.vespene_geyser.closer_than(15.0, nexus)
            for vespene in vespenes:
                if not self.can_afford(ASSIMILATOR):
                    break
                worker = self.select_build_worker(vespene.position)
                if worker is None:
                    break
                if not self.units(ASSIMILATOR).closer_than(1.0, vespene).exists:
                    await self.do(worker.build(ASSIMILATOR, vespene))


    async def expand(self):
        if self.units(NEXUS).amount < 3  and self.can_afford(NEXUS):
            await self.expand_now()


    async def offensive_force_buildings(self):
        if self.units(PYLON).ready.exists:
            pylon = self.units(PYLON).ready.random
            if self.units(GATEWAY).ready.exists and not self.units(CYBERNETICSCORE):
                if self.can_afford(CYBERNETICSCORE) and not self.already_pending(CYBERNETICSCORE):
                    await self.build(CYBERNETICSCORE, near=pylon)
            elif len(self.units(GATEWAY)) < 3:
                if self.can_afford(GATEWAY) and not self.already_pending(GATEWAY):
                    await self.build(GATEWAY, near=pylon)


    async def build_offensive_force(self):
        for gw in self.units(GATEWAY).ready.idle:
            if self.can_afford(STALKER) and self.supply_left > 0:
                    await self.do(gw.train(STALKER))


    def find_target(self, state):
        if len(self.known_enemy_units) > 0:
            return random.choice(self.known_enemy_units)
        elif len(self.known_enemy_structures) > 0:
            return random.choice(self.known_enemy_structures)
        else:
            return self.enemy_start_locations[0]


    async def attack(self):
        if self.units(STALKER).amount > 15:
            for s in self.units(STALKER).idle:
                await self.do(s.attack(self.find_target(self.state)))

        elif self.units(STALKER).amount > 3 and len(self.known_enemy_units) > 0:
            for s in self.units(STALKER).idle:
                await self.do(s.attack(random.choice(self.known_enemy_units)))


    async def manage_bases(self):
        # Do some logic for each nexus
        for nexus in self.units(NEXUS).ready:

            await self.handle_chronoboost(nexus)


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
                
                if not nexus.is_idle and not nexus.has_buff(CHRONOBOOSTENERGYCOST):
                    await self.do(nexus(EFFECT_CHRONOBOOSTENERGYCOST, nexus))
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

def main():
    sc2.run_game(sc2.maps.get("Abyssal Reef LE"), [
        Bot(Race.Protoss, BotAA()),
        Computer(Race.Terran, Difficulty.Medium)
    ], realtime=False)

if __name__ == '__main__':
    main()