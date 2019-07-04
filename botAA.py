'''
    bot_ai.py:
        Linha 518. O parametro max_distance por padrão é 20 (está 8)
    
    Ideias:
    -> Cancelar a construção de estruturas que estejam sendo atacadas.
    -> Definir quais unidades inimigas devem ser atacadas primeiro (priorizar a unidade mais "valiosa" que esteja mais perto)
    -> Sobre Upgrades:
        It usually comes down to preference but most people will tell you to prioritize weapons upgrades against Zerg and fellow Protoss, and to prioritize armor upgrades against Terran.
        Keep in mind this is when working off one Forge, as soon as you get two Forges that you can continuously upgrade out of, this is irrelevant.
        Also, save shields for last ALWAYS
    
    função main_base_ramp para ver a rampa principal
'''
import random

import sc2
from sc2 import Difficulty, Race, maps, run_game, position
from sc2.constants import *
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
        # Make sure to expand in late game (every 2.5 minutes)
        self.expand_every = 2.5 * 60

        self.strategy = "e"
        #### Initial values for the early game ####
        self.prefered_base_count = 2
        self.gateways_per_nexus = 1
        self.defense_type_per_nexus = 1
        self.min_army_size = 10
        self.stalker_ratio = 1
        self.colossus_ratio = self.immortal_ratio = self.voidray_ratio = 0
        #### End of Early game initial values ####


    async def on_step(self, iteration):
        self.iteration = iteration
        
        if self.strategy == "e" and (self.time > 180 or self.vespene > 400 or self.minerals > 800):
            await self.chat_send("Entering late game strategy. Current time: " + self.time_formatted)
            self.strategy = "l"
            self.gateways_per_nexus = 2.5
            self.defense_type_per_nexus = 1.5

        if self.iteration % 50 == 0:
            await self.distribute_workers()
            
        await self.manage_bases()
        await self.offensive_force_buildings()
        await self.build_offensive_force()
        await self.manage_army()
        await self.scouting()
        await self.manage_upgrades()
        await self.idle_workers()

        if self.strategy == "e":
            await self.early_game_strategy()
        elif self.strategy == "l":
            await self.late_game_strategy()
      
        #Execute all orders
        await self.execute_actions_list()


    async def do(self, action):
        self.actions_list.append(action)


    async def early_game_strategy(self):
        # Expand up to 2 nexus
        if self.units(NEXUS).amount < self.prefered_base_count:
            await self.expand()

        # Research Warpgate
        if self.units(CYBERNETICSCORE).ready.exists and self.can_afford(RESEARCH_WARPGATE):
            cybernetics = self.units(CYBERNETICSCORE).first
            if cybernetics.is_idle and await self.has_ability(RESEARCH_WARPGATE, cybernetics):
                await self.do(cybernetics(RESEARCH_WARPGATE))

        # Patrol from enemy base to the center of the map
        # Check if we already have a scout  
        if self.time >= 60:   
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
                if self.nearby_enemy_units(scout).exists:
                    await self.do(scout(PATROL, target=self.game_info.map_center.towards(self.enemy_start_locations[0], 20)))


    # TODO: implement late game strategy
    async def late_game_strategy(self):        

        self.prefered_base_count = 1 + int(self.time / self.expand_every)
        current_base_count = await self.current_base_count()

        if current_base_count < self.prefered_base_count:
            await self.expand()
        
        # Increase the minimum army size by every value of self.expand_every minutes
        if self.time % self.expand_every == 0 and self.min_army_size < 60: 
            self.min_army_size += 10 
            await self.chat_send("Current min army size: " + str(self.min_army_size) + " (@" + self.time_formatted + ")" )
    
        if not self.proxy_built:
            await self.build_proxy_pylon()

        # In late game, we want to have 2 forges to upgrade ground units
        if self.units(FORGE).amount < 2:
            await self.build_forges()
        
        if self.units(TWILIGHTCOUNCIL).amount < 1:
            await self.build_twilight_council()

        '''
                        EARLY                               LATE
            (Gateway > Cybernetics Core) -> (Twilight Council > Templar Archives)
                                         -> (Robotics Facility > Robotics Bay)
            Construir robotics bay, twilight consul para construir Colossus e High Templar
        '''

    async def current_base_count(self):
        # Only count bases as active if they have at least 10 ideal harvesters (will decrease as it's mined out)
        return self.units(NEXUS).ready.filter(lambda unit: unit.ideal_harvesters >= 10).amount 


    # Focus on ground units then colossus and high templars upgrades
    async def manage_upgrades(self):
        
        for forge in self.units(FORGE).ready:
            if forge.is_idle:
                for upgrade_level in range(1, 4):
                    upgrade_weapon_id = getattr(sc2.constants, "FORGERESEARCH_PROTOSSGROUNDWEAPONSLEVEL" + str(upgrade_level))
                    upgrade_armor_id = getattr(sc2.constants, "FORGERESEARCH_PROTOSSGROUNDARMORLEVEL" + str(upgrade_level))
                    shield_armor_id = getattr(sc2.constants, "FORGERESEARCH_PROTOSSSHIELDSLEVEL" + str(upgrade_level))
                    if await self.has_ability(upgrade_weapon_id, forge):
                        if self.can_afford(upgrade_weapon_id):
                            await self.do(forge(upgrade_weapon_id))
                        return
                    elif await self.has_ability(upgrade_armor_id, forge):
                        if self.can_afford(upgrade_armor_id):
                            await self.do(forge(upgrade_armor_id))
                        return
                    elif await self.has_ability(shield_armor_id, forge):
                        if self.can_afford(shield_armor_id):
                            await self.do(forge(shield_armor_id))
                        return
        
        if self.enemy_race != Race.Zerg:
            robotics = self.units(ROBOTICSBAY)
            if robotics.filter(lambda r: r.ready and r.is_idle) and await self.has_ability(RESEARCH_EXTENDEDTHERMALLANCE, robotics) and self.can_afford(RESEARCH_EXTENDEDTHERMALLANCE):
                await self.do(robotics(RESEARCH_EXTENDEDTHERMALLANCE))
                return

        #else:
        # if race is not zerg, train colossus upgrades, else dont
        '''
        Early Game:
            Se já existir cybernetics e estiver idle, treinar warpgate
            Se já existir forge e não estiver treinando, treinar arma nv 1
            Se já existir forge e não estiver treinando, treinar armor nv 1
        Late game:
            Pesquisar Upgrades de arma e armor nivel 2 no forge
            Pesquisar thermal lance (Robotics Bay) e psionic storm (templar archives)
        '''

    # Execute all orders in self.actions_list and reset it
    async def execute_actions_list(self):
        await self.do_actions(self.actions_list)
        self.actions_list = [] # Reset actions list
              

    async def build_workers(self, nexus):
        if nexus.is_idle and self.can_afford(PROBE) and nexus.assigned_harvesters < (nexus.ideal_harvesters + 3) and self.workers.amount < self.max_workers and self.supply_used < 180:
            await self.do(nexus.train(PROBE))

    # Force idle workers near nexus to mine
    async def idle_workers(self):
        if self.workers.idle.exists:
            worker = self.workers.idle.first
            await self.do(worker.gather(self.state.mineral_field.closest_to(worker.position)))
            

    async def build_pylons(self, nexus):
        # supply_left: Available Population to Produce 
        if nexus and self.supply_left < 5 and not self.already_pending(PYLON) and self.supply_cap < 190 and self.can_afford(PYLON):
            await self.build(PYLON, near=nexus.position.towards(self.game_info.map_center, 10))


    async def scouting(self):
        if self.time > 120: 
            scout = None

            # Check if we already have a scout            
            for worker in self.workers:
                if len(worker.orders) >= 1 and worker.orders[0].ability.id == PATROL:
                    scout = worker
            
            expansion_location = random.choice(list(self.expansion_locations.keys()))

            # If we don't have any, assign one to be the closest to chosen expansion location
            if not scout:
                scout = self.workers.closest_to(expansion_location)
                if not scout:
                    return
                    
            if scout.orders:
                # If scout was not designated to patrol, do it now
                if not scout.orders[0].ability.id == PATROL:
                    await self.do(scout(PATROL, target=expansion_location))
                    return
                
                # If we arrived at our destination, choose another one
                #target = self.unit_target_position(scout)
                target = scout.order_target
                if scout.distance_to(target) <= 2:
                    await self.do(scout(PATROL, target=expansion_location))
                    return
            
            # If there are enemies nearby, run away
            if self.nearby_enemy_units(scout).exists:
                await self.do(scout(PATROL, target=self.game_info.map_center))
                return          

    def nearby_enemy_units(self, unit):
        return self.known_enemy_units.filter(lambda u: u.type_id not in self.units_to_ignore and u.type_id not in self.known_enemy_structures).closer_than(20, unit)

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


    async def build_defenses(self, nexus):
        # TODO: -> Better distribute photon cannons along nexuses
        # We only want to build photons after we have the desired amount of gateways, as it is our main defense
        if nexus and ((self.units(GATEWAY).amount + self.units(WARPGATE).amount) / self.units(NEXUS).amount) >= self.gateways_per_nexus:
            pylons = self.units(PYLON).ready.closer_than(20, nexus)
            if pylons:
                pylon = pylons.closest_to(nexus)
                if pylon:
                    if self.can_afford(PHOTONCANNON) and (self.units(PHOTONCANNON).amount / self.units(NEXUS).amount) < self.defense_type_per_nexus and self.units(PHOTONCANNON).closer_than(20, nexus).amount < self.defense_type_per_nexus:
                        await self.build(PHOTONCANNON, near=pylon.position.towards(nexus, 10))
                        return
                    if self.can_afford(SHIELDBATTERY) and (self.units(SHIELDBATTERY).amount / self.units(NEXUS).amount) < self.defense_type_per_nexus and self.units(SHIELDBATTERY).closer_than(20, nexus).amount < self.defense_type_per_nexus:
                        await self.build(SHIELDBATTERY, near=pylon.position.towards(nexus, 10))
                        return
        

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
            
            elif (self.units(GATEWAY).amount + self.units(WARPGATE).amount) / self.units(NEXUS).amount < self.gateways_per_nexus:
                if self.can_afford(GATEWAY) and not self.already_pending(GATEWAY):
                    await self.build(GATEWAY, near=position)


    async def build_offensive_force(self):
        # For each gateway, if we can, morph into warpgate. If not, train stalker
        for gw in self.units(GATEWAY).ready.idle:
            await self.do(gw(RALLY_BUILDING, self.main_base_ramp.top_center))
            if await self.has_ability(MORPH_WARPGATE, gw) and self.can_afford(MORPH_WARPGATE):
                await self.do(gw(MORPH_WARPGATE))
            else:
                if self.can_afford(STALKER) and self.supply_left > 0:
                    await self.do(gw.train(STALKER))

        for warpgate in self.units(WARPGATE).ready.idle:
            # Warp Stalkers to the closest pylon from enemy base
            if await self.has_ability(WARPGATETRAIN_ZEALOT, warpgate) and self.can_afford(STALKER):
                pos = self.units(PYLON).ready.closest_to(self.find_target(self.state)).position.to2.random_on_distance(4)
                placement = await self.find_placement(WARPGATETRAIN_STALKER, pos, placement_step=1)
                if placement:
                    await self.do(warpgate.warp_in(STALKER, placement))


    def find_target(self, state):
        if len(self.known_enemy_units) > 0:
            return random.choice(self.known_enemy_units)
        elif len(self.known_enemy_structures) > 0:
            return random.choice(self.known_enemy_structures)
        else:
            return self.enemy_start_locations[0]
         

    # TODO: Better attack conditions. Separate between attack and defense. Assign units only to defend?
    async def manage_army(self):
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
        for nexus in self.units(NEXUS).ready:
            await self.build_workers(nexus)
            await self.handle_chronoboost(nexus)
            await self.build_assimilators(nexus)
            await self.build_pylons(nexus)
            await self.build_defenses(nexus)


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


    async def build_twilight_council(self):
        if not self.already_pending(TWILIGHTCOUNCIL) and self.can_afford(TWILIGHTCOUNCIL):
            pylons = self.units(PYLON).ready
            if len(pylons) > 0:
                await self.build(TWILIGHTCOUNCIL, near=pylons.closest_to(self.units(NEXUS).first))


    async def build_forges(self):
        if not self.already_pending(FORGE) and self.can_afford(FORGE):
            pylons = self.units(PYLON).ready
            if len(pylons) > 0:
                await self.build(FORGE, near=pylons.closest_to(self.units(NEXUS).first))


    async def build_proxy_pylon(self):
        if self.units(WARPGATE).ready.exists and self.can_afford(PYLON):
            worker = self.units(PROBE).closest_to(self.units(NEXUS).first)

            if worker is not None:   
                # TODO: change proxy location to be closer to enemy natural
                p = self.game_info.map_center.towards(self.find_target(self.state), 25)         
                await self.build(PYLON, near=p, unit=worker)
                self.proxy_built = True


def main():
    sc2.run_game(sc2.maps.get("Kings Cove LE"), [
        Bot(Race.Protoss, BotAA()),
        Computer(Race.Zerg, Difficulty.Hard)
    ], realtime=False)

if __name__ == '__main__':
    main()