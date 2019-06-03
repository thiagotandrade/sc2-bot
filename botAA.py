'''
    Just change await self.do(unit.attack(attack_target)) to list.append(unit.attack(attack_target)) 
    and in the last part of your on_step await self.do_actions(list).
    Remember to clear your list after every step.
'''

import sc2
from sc2 import run_game, maps, Race, Difficulty
from sc2.player import Bot, Computer
from sc2.constants import NEXUS, PROBE, PYLON

# This fix is required for the queued order system to work correctly (self.execute_order_queue())



class BotAA(sc2.BotAI):

    order_queue = []

    async def on_step(self, iteration):
        await self.distribute_workers()
        await self.build_workers()
        await self.build_pylons()
        await self.execute_order_queue()

    async def do(self, action):
        self.order_queue.append(action)

    # Execute all orders in self.order_queue and reset it
    async def execute_order_queue(self):
        await self.do_actions(self.order_queue)
        self.order_queue = [] # Reset order queue

    async def build_workers(self):
        for nexus in self.units(NEXUS).ready.noqueue:
            if self.can_afford(PROBE):
                await self.do(nexus.train(PROBE))
    
    async def build_pylons(self):
        # supply_left: População restante 
        if self.supply_left < 5 and not self.already_pending(PYLON):
            nexuses = self.units(NEXUS).ready
            if nexuses.exists:
                if self.can_afford(PYLON):
                    await self.build(PYLON, near=nexuses.first)

run_game(maps.get("AbyssalReefLE"), [
    Bot(Race.Protoss, BotAA()),
    Computer(Race.Terran, Difficulty.Easy)
], realtime=False)