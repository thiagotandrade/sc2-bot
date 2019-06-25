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
from sc2 import Difficulty, Race, maps, run_game, position
from sc2.constants import (
    ASSIMILATOR, CYBERNETICSCORE, GATEWAY, NEXUS, 
    PROBE, PYLON, STALKER, EFFECT_CHRONOBOOSTENERGYCOST, 
    CHRONOBOOSTENERGYCOST, WARPGATE, FORGE, TEMPLARARCHIVE,
    PHOTONCANNON, RESEARCH_WARPGATE, MORPH_WARPGATE, PATROL, WARPGATETRAIN_ZEALOT,
    WARPGATETRAIN_STALKER, WARPGATETRAIN_HIGHTEMPLAR, WARPGATETRAIN_SENTRY,
    COLOSSUS, IMMORTAL, VOIDRAY, ROBOTICSFACILITY,
    DRONE, SCV, PROBE, EGG, LARVA, OVERLORD, OVERSEER, OBSERVER, BROODLING, INTERCEPTOR, MEDIVAC, CREEPTUMOR, CREEPTUMORBURROWED, CREEPTUMORQUEEN, CREEPTUMORMISSILE)
from sc2.player import Bot, Computer


class BotAA(sc2.BotAI):
    def __init__(self):
        self.actions_list = []
        self.iteration = 0
        self.max_workers = 75
        # Number of times that we used Chronoboost on nexus
        self.cb_on_nexus = 0
        self.units_to_ignore = [DRONE, SCV, PROBE, EGG, LARVA, OVERLORD, OVERSEER, OBSERVER, BROODLING, INTERCEPTOR, MEDIVAC, CREEPTUMOR, CREEPTUMORBURROWED, CREEPTUMORQUEEN, CREEPTUMORMISSILE]
        self.proxy_built = False        
        
        self.strategy = "e"
        #### Initial values for the early game ####
        self.gateways_per_nexus = 1
        self.cannons_per_nexus = 1
        self.min_army_size = 20
        self.stalker_ratio = 1
        self.colossus_ratio = self.immortal_ratio = self.voidray_ratio = 0
        #### End of Early game initial values ####
        
        

    async def on_step(self, iteration):
        self.iteration = iteration
        if self.iteration == 0:
            print(dir(self))
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
            
        await self.manage_bases()
        await self.build_pylons()
        await self.offensive_force_buildings()
        await self.build_offensive_force()
        await self.attack()
        await self.scouting()
        #await self.idle_workers()
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
            await self.build_forges()

        # Research Warpgate
        if self.units(CYBERNETICSCORE).ready.exists and self.can_afford(RESEARCH_WARPGATE):
            cybernetics = self.units(CYBERNETICSCORE).first
            if cybernetics.is_idle and await self.has_ability(RESEARCH_WARPGATE, cybernetics):
                await self.do(cybernetics(RESEARCH_WARPGATE))

        # Patrol from enemy base to the center of the map
        # Check if we already have a scout     
        scout = None       
        for worker in self.workers:
            if len(worker.orders) >= 1 and worker.orders[0].ability.id == PATROL:
                scout = worker
        # If we don't have a scout, assign one
        if not scout:
            scout = self.workers.closest_to(self.start_location)
            # If we still don't have a scout, do nothing
            if scout:
                await self.do(scout(PATROL, target=self.enemy_start_locations[0]))
        else:
            target = self.unit_target_position(scout)
            if scout.distance_to(target) < 5 or self.nearby_enemy_units(scout).exists:
                await self.do(scout(PATROL, target=self.game_info.map_center))
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

        if not self.proxy_built:
            await self.build_proxy_pylon()

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
        if self.supply_left <= 5 and not self.already_pending(PYLON) and self.supply_cap < 190 and self.can_afford(PYLON):
            await self.build(PYLON, near=nexus.position.towards(self.game_info.map_center, 10))


    async def scouting(self):
        if self.time > 120: 
            scout = None

            # Check if we already have a scout            
            for worker in self.workers:
                #if self.has_order([PATROL], worker):
                if len(worker.orders) >= 1 and worker.orders[0].ability.id == PATROL:
                    scout = worker
            
            expansion_location = random.choice(list(self.expansion_locations.keys()))

            # If we don't have any, assign one to be the closest to chosen expansion location
            if not scout:
                scout = self.workers.closest_to(expansion_location)
                if not scout:
                    return
            
            # If scout was not designated to patrol, do it now
            if not scout.orders[0].ability.id == PATROL:
            #if not self.has_order([PATROL], scout):
                await self.do(scout(PATROL, target=expansion_location))
                return
            
            # If we arrived at our destination, choose another one
            target = self.unit_target_position(scout)
            if scout.distance_to(target) < 10:
                await self.do(scout(PATROL, target=expansion_location))
                return
            
            # If there are enemies nearby, run away
            if self.nearby_enemy_units(scout).exists:
                await self.do(scout(PATROL, target=self.game_info.map_center))
                return          

    def nearby_enemy_units(self, unit):
        return self.known_enemy_units.filter(lambda u: u.type_id not in self.units_to_ignore).closer_than(10, unit)

    def unit_target_position(self, scout):
        return sc2.position.Point2((scout.orders[0].target.x, scout.orders[0].target.y))

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
        # TODO: -> Better distribute photon cannons along nexuses
        #       -> Also some logic to build shield battery.
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
        # We only want to start training after we have 2 nexuses
        if self.units(NEXUS).amount >= 2:
            # For each gateway, if we can, morph into warpgate. If not, train stalker
            for gw in self.units(GATEWAY).ready.idle:
                #await self.do(gw(RALLY_BUILDING, self.units(NEXUS).closest_to(self.enemy_start_locations[0])))
                if await self.has_ability(MORPH_WARPGATE, gw) and self.can_afford(MORPH_WARPGATE):
                    await self.do(gw(MORPH_WARPGATE))
                else:
                    if self.can_afford(STALKER) and self.supply_left > 0:
                        await self.do(gw.train(STALKER))

            for warpgate in self.units(WARPGATE).ready.idle:
                # Warp Stalkers to the closest pylon from enemy base
                if await self.has_ability(WARPGATETRAIN_ZEALOT, warpgate) and self.can_afford(STALKER):
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


    # TODO: Better attack conditions. Separate between attack and defense. Assign units only to defend?
    async def attack(self):
        #army_rate= 5 * (self.time / 60) - 20
        #if self.units(STALKER).amount > army_rate and army_rate > 0:
        if self.units(STALKER).amount > self.min_army_size:
            for s in self.units(STALKER).idle:
                await self.do(s.attack(self.find_target(self.state)))

        # Defend from enemies near our nexuses
        elif self.units(STALKER).amount > 3 and len(self.known_enemy_units) > 0:
            close_enemy_units = await self.nexus_has_enemy_nearby()
            if len(close_enemy_units) > 0:
                for s in self.units(STALKER).idle:
                    await self.do(s.attack(random.choice(close_enemy_units).position.towards(self.enemy_start_locations[0])))


    async def nexus_has_enemy_nearby(self):
        nexus_with_enemy = []
        for nexus in self.units(NEXUS):
            if self.nearby_enemy_units(nexus):
                nexus_with_enemy.append(nexus)
        return nexus_with_enemy


    async def manage_bases(self):
        # Managing workers, assimilators, chronoboost
        for nexus in self.units(NEXUS).ready:

            await self.build_workers(nexus)
            await self.handle_chronoboost(nexus)
            await self.build_assimilators(nexus)


    # Check if an unit has an ability available
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


    async def build_forges(self):
        if not self.already_pending(FORGE) and self.can_afford(FORGE):
            pylons = self.units(PYLON).ready
            if len(pylons) > 0:
                await self.build(FORGE, near=pylons.closest_to(self.units(NEXUS).first))


    async def build_proxy_pylon(self):
        # Build pylon near enemy base and use the probe who as scout
        # TODO: Choose better condition to place proxy
        # Maybe check before if we have a scout already
        if self.units(WARPGATE).amount > 1 and self.can_afford(PYLON):
            worker = self.units(PROBE).closest_to(self.units(NEXUS).first)

            if worker is not None:   
                # TODO: change proxy location to be closer to enemy natural
                p = self.game_info.map_center.towards(self.find_target(self.state), 25)         
                await self.build(PYLON, near=p, unit=worker)
                self.proxy_built = True


    # Check if a unit has a specific order. Supports multiple units/targets. Returns unit count.
    def has_order(self, orders, units):
        if type(orders) != list:
            orders = [orders]

        count = 0

        if type(units) == sc2.unit.Unit:
            unit = units
            if len(unit.orders) >= 1 and unit.orders[0].ability.id in orders:
                count += 1
        else:
            for unit in units:
                if len(unit.orders) >= 1 and unit.orders[0].ability.id in orders:
                  count += 1

        return count


def main():
    sc2.run_game(sc2.maps.get("Cyber Forest LE"), [
        Bot(Race.Protoss, BotAA()),
        Computer(Race.Protoss, Difficulty.Hard)
    ], realtime=False)

if __name__ == '__main__':
    main()