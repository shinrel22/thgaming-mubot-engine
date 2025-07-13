import asyncio
import os
import time
from datetime import timedelta

from src.bases.engines import GameItem, PlayerSkill, Coord
from src.bases.engines.data_models import (
    ViewportObject, NPC, EngineOperatorTrainingSpot,
    WorldFastTravel,
    WorldMonsterSpot,
    EngineLevelTrainingBreakpointSetting, GameCoord, World, LocalPlayer, WorldCell,
)
from src.bases.errors import Error
from src.bases.engines.operators import EngineOperator
from src.constants import DATA_DIR
from src.constants.engine import (
    ENGINE_TRAINING_MODE,
    SD_POTION_ITEM_TYPE,
    MP_POTION_ITEM_TYPE,
    HP_POTION_ITEM_TYPE,
    PLAYER_STR_STAT,
    PLAYER_AGI_STAT,
    PLAYER_VIT_STAT,
    PLAYER_ENE_STAT,
    PLAYER_CMD_STAT,
    NPC_MERCHANT_TYPE,
    POTION_ITEM_TYPE,
    STAY_AND_KS,
    BOOST_ITEM_TYPE,
    EXP_BOOST_ITEM_TYPE,
    EXP_BOOST_EFFECT_TYPE,
    RESET_TRAINING_TYPE,
    MASTER_TRAINING_TYPE, GAME_PLAYING_SCREEN
)
from src.utils import (calculate_distance,
                       capture_error,
                       calculate_point_distribution,
                       get_now,
                       load_data_file)


class UnityMegaMUEngineOperator(EngineOperator):

    async def handle_game_events(self):
        while not self.engine.shutdown_event.is_set():
            await asyncio.sleep(0.1)

    async def handle_dialog_events(self):
        while not self.engine.shutdown_event.is_set():
            await asyncio.sleep(0.1)

            if not self.engine.game_context.current_dialog:
                continue

            try:
                await self._handle_dialog_events()
            except Exception as e:
                capture_error(e)

    async def _handle_dialog_events(self):
        pass
        # if dialog.title == 'PARTY':
        #     if dialog.message in [
        #         'Do you want to leave the party?'
        #     ]:
        #         return
        #     if dialog.message.startswith('Do you want to remove'):
        #         return
        #
        #     pattern = r"with\s+(\w+)[.!?]?\s*$"
        #     match = re.search(pattern, dialog.message)
        #     if not match:
        #         self.engine.function_triggerer.close_window(dialog.window)
        #         return
        #
        #     player_name = match.group(1)
        #     viewport_player = None
        #     for vpp in self.engine.game_context.viewport.object_players.values():
        #         if vpp.object.name == player_name:
        #             viewport_player = vpp
        #             break
        #
        #     if not viewport_player:
        #         self.engine.function_triggerer.close_window(dialog.window)
        #         return
        #
        #     receiving_logic = self.engine.settings.party.receiving_logic
        #
        #     if receiving_logic == REJECT_ALL:
        #         self.engine.function_triggerer.close_window(dialog.window)
        #         return
        #
        #     if receiving_logic == ACCEPT_ALL:
        #         self.engine.function_triggerer.handle_party_request(
        #             viewport_player=viewport_player,
        #             accept=True
        #         )
        #         self.engine.function_triggerer.close_window(dialog.window)
        #         return
        #
        #     if receiving_logic == ACCEPT_FROM_LIST:
        #         name_list = [name.lower().strip() for name in self.engine.settings.party.accept_requests_from]
        #         if viewport_player.object.name.lower() in name_list:
        #             self.engine.function_triggerer.handle_party_request(
        #                 viewport_player=viewport_player,
        #                 accept=True
        #             )
        #             self.engine.function_triggerer.close_window(dialog.window)

    async def handle_protection(self):
        while not self.engine.shutdown_event.is_set():
            await asyncio.sleep(0.1)
            try:
                await self._handle_protection()
            except Exception as e:
                capture_error(e)

    async def _refresh_player_skills(self):
        updated_at = self._player_skills_updated_at
        if updated_at and updated_at + timedelta(seconds=5) > get_now():
            return

        self._player_skills = await self.engine.game_context_synchronizer.load_player_active_skills()
        self._player_skills_updated_at = get_now()

    async def _handle_protection(self):
        settings = self.engine.settings.protection
        player = self.engine.game_context.local_player
        screen_id = self.engine.game_context.screen.screen_id

        if (not player or player.in_safe_zone
                or self.engine.meta.screen_mappings[GAME_PLAYING_SCREEN] != screen_id
                or self.engine.game_context.is_channel_switching
                or not self.engine.game_context.player_inventory):
            await asyncio.sleep(2)
            return

        hp_rate = (player.current_hp / player.max_hp) * 100
        hp_percent_to_use_potion = settings.recovery.hp_percent_to_use_potion or 0
        hp_percent_to_use_skills = settings.recovery.hp_percent_to_use_skills or 0

        sd_rate = (player.current_sd / player.max_sd) * 100
        sd_percent_to_use_potion = settings.recovery.sd_percent_to_use_potion or 0
        sd_percent_to_use_skills = settings.recovery.sd_percent_to_use_skills or 0

        mp_rate = (player.current_mp / player.max_mp) * 100
        mp_percent_to_use_potion = settings.recovery.mp_percent_to_use_potion or 0
        mp_percent_to_use_skills = settings.recovery.mp_percent_to_use_skills or 0

        if settings.recovery.use_hp_potions and hp_percent_to_use_potion > 0:
            if hp_rate < hp_percent_to_use_potion:
                hp_potion = self._get_item_from_inventory(
                    item_type=HP_POTION_ITEM_TYPE
                )
                if hp_potion:
                    now = get_now()
                    cooldown = self._potion_cooldowns.get(HP_POTION_ITEM_TYPE) or now
                    if cooldown <= now:
                        await self.engine.function_triggerer.use_item(
                            hp_potion
                        )
                        self._potion_cooldowns[
                            HP_POTION_ITEM_TYPE
                        ] = now + timedelta(seconds=self.engine.game_server.potion_cooldown)

        if settings.recovery.use_mp_potions and mp_percent_to_use_potion > 0:
            if mp_rate < mp_percent_to_use_potion:
                mp_potion = self._get_item_from_inventory(
                    item_type=MP_POTION_ITEM_TYPE
                )
                if mp_potion:
                    now = get_now()
                    cooldown = self._potion_cooldowns.get(MP_POTION_ITEM_TYPE) or now
                    if cooldown <= now:
                        await self.engine.function_triggerer.use_item(
                            mp_potion
                        )
                        self._potion_cooldowns[
                            MP_POTION_ITEM_TYPE
                        ] = now + timedelta(seconds=self.engine.game_server.potion_cooldown)

        if settings.recovery.use_sd_potions and sd_percent_to_use_potion > 0:
            if sd_rate < sd_percent_to_use_potion:
                sd_potion = self._get_item_from_inventory(
                    item_type=SD_POTION_ITEM_TYPE
                )
                if sd_potion:
                    now = get_now()
                    cooldown = self._potion_cooldowns.get(SD_POTION_ITEM_TYPE) or now
                    if cooldown <= now:
                        await self.engine.function_triggerer.use_item(
                            sd_potion
                        )
                        self._potion_cooldowns[
                            SD_POTION_ITEM_TYPE
                        ] = now + timedelta(seconds=self.engine.game_server.potion_cooldown)

        if settings.recovery.use_skills_for_hp and hp_percent_to_use_skills > 0:
            if hp_rate < hp_percent_to_use_skills and settings.recovery.skill_ids_for_hp:
                for skill_id in settings.recovery.skill_ids_for_hp:
                    await self._cast_skill(skill_id)

        if settings.recovery.use_skills_for_mp and mp_percent_to_use_skills > 0:
            if mp_rate < mp_percent_to_use_skills and settings.recovery.skill_ids_for_mp:
                for skill_id in settings.recovery.skill_ids_for_mp:
                    await self._cast_skill(skill_id)

        if settings.recovery.use_skills_for_sd and sd_percent_to_use_skills > 0:
            if sd_rate < sd_percent_to_use_skills and settings.recovery.skill_ids_for_sd:
                for skill_id in settings.recovery.skill_ids_for_sd:
                    await self._cast_skill(skill_id)

    def _get_item_from_inventory(self, item_type: str) -> GameItem | None:
        result = None

        for game_item in self.engine.game_context.player_inventory.items.values():
            if item_type in game_item.item.types:
                result = game_item
                break

        return result

    async def _back_to_town(self):
        town_id = self.engine.settings.protection.back_to_town.town_id

        while self.engine.game_context.screen.world_id != town_id:
            await self.engine.function_triggerer.change_world(town_id)
            await asyncio.sleep(5)

    async def handle_training(self):
        while not self.engine.shutdown_event.is_set():
            try:
                await self._handle_training()
            except Exception as e:
                capture_error(e)
            await asyncio.sleep(0.1)

    async def _refresh_auto_accept_pt_settings(self):
        if self.engine.settings.party.auto_accept_while_training:
            await self.engine.function_triggerer.send_chat('/re auto')
        else:
            await self.engine.function_triggerer.send_chat('/re on')

    async def _handle_training(self, training_spot: EngineOperatorTrainingSpot = None):
        if not self.engine.game_context.local_player:
            return None

        await self._refresh_auto_accept_pt_settings()
        auto_accept_pt_requests = self.engine.settings.party.auto_accept_while_training

        if self.engine.game_context.local_player.in_safe_zone:
            # trigger in town logic here
            await self._go_shopping()
            await self._move_items_to_warehouse()

        if self._need_to_back_to_town():
            await self._back_to_town()
            return await self._handle_training(training_spot=training_spot)

        # first reset check
        training_type = await self._check_training_type()
        if training_type == RESET_TRAINING_TYPE:
            if self._player_resetable():
                await self._reset_player()

        if not training_spot:
            training_spot = await self._find_training_spot()

        last_player_levels = self._get_player_levels()

        while True:
            if self.engine.settings.party.auto_accept_while_training != auto_accept_pt_requests:
                await self._refresh_auto_accept_pt_settings()
                auto_accept_pt_requests = self.engine.settings.party.auto_accept_while_training

            current_player_levels = self._get_player_levels()
            if last_player_levels < current_player_levels:
                if training_spot.training_type == RESET_TRAINING_TYPE:
                    if self._player_resetable():
                        await self._reset_player()
                        return None
                if not self._training_spot_valid(training_spot):
                    training_spot = await self._find_training_spot()
            last_player_levels = current_player_levels

            await self._ensure_items_are_picked_up(training_spot)

            if not self._within_area(
                    world=training_spot.world,
                    radius=self.engine.settings.location.training_radius,
                    coord=training_spot.monster_spot.coord
            ):
                await self._ensure_within_training_area(training_spot)

            viewport_monster = self._get_viewport_monster(training_spot)

            await self._ensure_boost_items_are_used()

            if not viewport_monster:
                await asyncio.sleep(0.1)
                continue

            await self._ensure_buffs_are_casted(
                self.engine.settings.skills.pve.buff_skill_ids,
            )

            await self._ensure_monster_in_sight(training_spot, viewport_monster)

            await self._attack_monster(
                training_spot,
                viewport_monster,
            )

            if self._need_to_back_to_town():
                await self._back_to_town()
                return await self._handle_training(
                    training_spot=training_spot,
                )
            await asyncio.sleep(0.1)

    def _need_to_back_to_town(self) -> bool:
        settings = self.engine.settings.protection.back_to_town
        if settings.when_no_hp_potions_left:
            if not self._get_item_from_inventory(
                    item_type=HP_POTION_ITEM_TYPE
            ):
                return True

        if settings.when_no_mp_potions_left:
            if not self._get_item_from_inventory(
                    item_type=MP_POTION_ITEM_TYPE
            ):
                return True
        if settings.when_no_sd_potions_left:
            if not self._get_item_from_inventory(
                    item_type=SD_POTION_ITEM_TYPE
            ):
                return True

        return False

    async def _attack_monster(self,
                              training_spot: EngineOperatorTrainingSpot,
                              viewport_monster: ViewportObject,
                              max_attempts: int = 50
                              ):

        attempts = 0
        monster_hp = viewport_monster.object.current_hp

        await self._refresh_player_skills()

        while self._viewport_monster_attackable(training_spot, viewport_monster) and attempts < max_attempts:

            await self._ensure_items_are_picked_up(training_spot)

            offensive_skill_ids = self.engine.settings.skills.pve.offensive_skill_ids
            if offensive_skill_ids:
                for skill_id in self.engine.settings.skills.pve.offensive_skill_ids:
                    await self._cast_skill(skill_id, target=viewport_monster)

            else:
                await self.engine.function_triggerer.melee_attack(
                    target=viewport_monster
                )

            vpm = self.engine.game_context.viewport.object_monsters.get(viewport_monster.addr)
            if not vpm:
                return

            if vpm.object.current_hp >= monster_hp:
                attempts += 1
            else:
                attempts = 0
            monster_hp = vpm.object.current_hp
            await asyncio.sleep(0.1)

        vpm = self.engine.game_context.viewport.object_monsters.get(viewport_monster.addr)
        if vpm and (vpm.object.current_hp > 0 or not vpm.object.is_destroying):
            self._ignore_monster(vpm)
            return

        self._ignored_monsters.pop(viewport_monster.addr, None)

    def _get_player_levels(self) -> int:
        player = self.engine.game_context.local_player

        if player.level >= self.engine.game_server.max_level:
            return player.level + player.master_level

        return player.level

    async def _ensure_buffs_are_casted(self,
                                       buff_skill_ids: list[int]):
        if not buff_skill_ids:
            return

        await self._refresh_player_skills()

        current_effect_ids = list(map(
            lambda x: x.effect.id,
            self.engine.game_context.local_player.effects.values()
        ))

        for buff_skill_id in buff_skill_ids:
            if buff_skill_id not in self._player_skills:
                continue
            bs = self._player_skills[buff_skill_id]
            if bs.skill.effect_id in current_effect_ids:
                continue
            await self._cast_skill(buff_skill_id)

    async def _ensure_boost_items_are_used(self):
        if not self.engine.settings.inventory.use_boost_items:
            return

        if not self.engine.settings.inventory.boost_item_ids:
            return

        current_effect_ids = set()
        current_effect_types = set()

        for game_effect in self.engine.game_context.local_player.effects.values():
            current_effect_ids.add(game_effect.effect_id)
            for effect_type in game_effect.effect.types:
                current_effect_types.add(effect_type)

        for game_item in self.engine.game_context.player_inventory.items.values():

            if game_item.item_id not in self.engine.settings.inventory.boost_item_ids:
                continue

            if BOOST_ITEM_TYPE not in game_item.item.types:
                continue

            if EXP_BOOST_ITEM_TYPE in game_item.item.types:
                # Can't apply exp boost twice
                if EXP_BOOST_EFFECT_TYPE in current_effect_types:
                    continue
                await self.engine.function_triggerer.use_item(game_item)
                current_effect_types.add(EXP_BOOST_EFFECT_TYPE)

    async def _cast_skill(self,
                          skill_id: int,
                          target: ViewportObject = None,
                          coord: Coord = None):

        await self._refresh_player_skills()

        skill = self._player_skills.get(skill_id)
        if not skill:
            return

        now = get_now()

        if skill.cooldown > 0:
            if skill.skill_id in self._skill_cooldowns:
                if self._skill_cooldowns[skill.skill_id] > now:
                    return
            else:
                self._skill_cooldowns[skill.skill_id] = now + timedelta(milliseconds=skill.cooldown)

        await self.engine.function_triggerer.cast_skill(skill, target, coord)

    async def _ensure_items_are_repaired(self):
        if not self.engine.game_context.player_inventory:
            return

        for game_item in self.engine.game_context.player_inventory.items.values():
            if game_item.storage_slot_index is None:
                continue
            if game_item.storage_slot_index > 11:
                continue
            if game_item.durability <= 5:
                await self.engine.function_triggerer.repair_item(game_item)

    async def _ensure_items_are_picked_up(self,
                                          training_spot: EngineOperatorTrainingSpot,
                                          max_attempts: int = 5
                                          ):
        if not self.engine.game_context.viewport.object_items:
            return

        vpi_to_pickup: list[ViewportObject] = []

        item_ids = []
        if self.engine.settings.inventory.pickup_from_list:
            item_ids = self.engine.settings.inventory.pickup_item_ids
        item_types = self.engine.settings.inventory.pickup_item_types

        for vpi in self.engine.game_context.viewport.object_items.values():
            if not self.engine.settings.inventory.pickup_outside_training_radius:
                if calculate_distance(
                        (
                                vpi.object_coord.x,
                                vpi.object_coord.y,
                        ),
                        (
                                training_spot.monster_spot.coord.x,
                                training_spot.monster_spot.coord.y
                        )
                ) > self.engine.settings.location.training_radius:
                    continue

            if vpi.object.item_id in item_ids:
                vpi_to_pickup.append(vpi)
                continue

            for item_type in vpi.object.item.types:
                if item_type in item_types:
                    vpi_to_pickup.append(vpi)
                    break

        if not vpi_to_pickup:
            return

        for vpi in vpi_to_pickup:

            attempts: int = 0

            while self._item_pickable(vpi) and attempts <= (max_attempts * 10):

                # move to item
                while calculate_distance(
                        (
                                vpi.object_coord.x
                                , vpi.object_coord.y
                        ),
                        (
                                self.engine.game_context.local_player.current_coord.x,
                                self.engine.game_context.local_player.current_coord.y
                        )
                ) > 2:
                    await self.engine.function_triggerer.move_to_coord(vpi.object_coord)
                    await asyncio.sleep(0.1)

                await self.engine.function_triggerer.pickup_item(vpi)
                attempts += 1
                await asyncio.sleep(0.1)

    def _item_pickable(self, viewport_item: ViewportObject) -> bool:

        viewport_items = self.engine.game_context.viewport.object_items

        if viewport_item.addr not in viewport_items:
            return False

        return True

    async def _move_items_to_warehouse(self):
        pass

    def _player_resetable(self) -> bool:
        return self.engine.game_context.local_player.level >= self.engine.game_server.max_level

    def _viewport_monster_attackable(self,
                                     training_spot: EngineOperatorTrainingSpot,
                                     viewport_monster: ViewportObject,
                                     ) -> bool:
        viewport_monsters = self.engine.game_context.viewport.object_monsters
        if viewport_monster.addr not in viewport_monsters:
            return False

        vpm = viewport_monsters[viewport_monster.addr]

        if vpm.object.in_safe_zone:
            return False

        if vpm.object.is_destroying:
            return False

        if vpm.object.current_hp <= 0:
            return False

        training_radius = self.engine.settings.location.training_radius
        avoid_monster_ids = training_spot.setting.avoid_monster_ids

        # other monsters in the training area
        other_vp_monsters_in_area = list(filter(
            lambda _vpm: (calculate_distance(
                (training_spot.monster_spot.coord.x, training_spot.monster_spot.coord.y),
                (_vpm.object_coord.x, _vpm.object_coord.y),
            ) <= training_radius
                          and _vpm.addr != vpm.addr
                          and _vpm.object.monster_id not in avoid_monster_ids),
            viewport_monsters.values()
        ))

        if vpm.object.monster_id in training_spot.setting.avoid_monster_ids:
            # avoid attacking if there are other monsters
            if other_vp_monsters_in_area:
                return False

        if self.engine.settings.location.chase_beyond_radius:
            return True

        distance = calculate_distance(
            (training_spot.monster_spot.coord.x, training_spot.monster_spot.coord.y),
            (vpm.object_coord.x, vpm.object_coord.y),
        )
        return distance <= training_radius

    async def _reset_player(self):
        if self.engine.game_context.local_player.reset_count >= self.engine.game_server.max_rr:
            return

        while self.engine.game_context.local_player.level >= self.engine.game_server.max_level:
            await self.engine.function_triggerer.reset_player(
                command=self.engine.game_server.ingame_rr_command
            )
            await asyncio.sleep(3)

        if self.engine.game_context.party_manager.is_in_party:
            if not self.engine.settings.party.leave_party_after_rr:
                return
            for pm in self.engine.game_context.party_manager.members.values():
                if pm.player_name == self.engine.game_context.local_player.name:
                    await self.engine.function_triggerer.kick_party_member(pm)
                    break

    def _get_viewport_monster(self, training_spot) -> ViewportObject | None:
        results = self._get_viewport_monsters(training_spot)

        if not results:
            return None
        return results[0]

    def _get_viewport_monsters(self, training_spot: EngineOperatorTrainingSpot) -> list[ViewportObject]:

        player = self.engine.game_context.local_player
        training_radius = self.engine.settings.location.training_radius

        result: list[tuple[
            int,  # monster levels
            int,  # monster current hp
            float,  # distance to player
            ViewportObject
        ]] = []

        for vpm in self.engine.game_context.viewport.object_monsters.values():
            if vpm.addr in self._ignored_monsters:
                continue

            if vpm.object.in_safe_zone:
                continue

            if vpm.object.is_destroying:
                continue

            if vpm.object.current_hp <= 0:
                continue

            vpm_relative_coord = self._get_relative_coord_with_training_spot_map(
                training_spot,
                vpm.object_coord
            )

            vpm_distance_from_spot = calculate_distance(
                (vpm_relative_coord.x, vpm_relative_coord.y),
                (training_radius, training_radius)
            )
            if vpm_distance_from_spot > training_radius:
                continue

            path_to_vpm_from_ts = self.engine.world_map_handler.find_path(
                cells=training_spot.map,
                start=(training_radius, training_radius),
                goal=(vpm_relative_coord.x,
                      vpm_relative_coord.y),
                map_size=training_radius * 2
            )
            if not path_to_vpm_from_ts:
                continue

            # path too long to reach the monster,
            if len(path_to_vpm_from_ts) > training_radius * 1.5:
                continue

            vpm_distance_from_player = calculate_distance(
                (player.current_coord.x, player.current_coord.y),
                (vpm.object_coord.x, vpm.object_coord.y),
            )
            result.append((
                vpm.object.level,
                vpm.object.current_hp,
                vpm_distance_from_player,
                vpm
            ))

        # prioritize by monster levels and distance to player
        result = sorted(result, key=lambda x: (x[0], x[1], x[2]))

        return list(map(lambda x: x[3], result))

    def _load_world_monster_spots(self, world_id: int) -> list[WorldMonsterSpot]:
        result = []

        filepath = os.path.join(
            DATA_DIR,
            self.engine.game_server.code,
            'monster_spots',
            f'{world_id}.jsonl',
        )
        if not os.path.exists(filepath):
            return result

        for wms in load_data_file(filepath):
            result.append(WorldMonsterSpot(**wms))

        return result

    async def _check_training_type(self) -> str:
        if self.engine.game_context.local_player.reset_count == 0:
            await asyncio.sleep(2)
        if self.engine.game_context.local_player.reset_count < self.engine.game_server.max_rr:
            return RESET_TRAINING_TYPE
        return MASTER_TRAINING_TYPE

    async def _find_training_spot(self) -> EngineOperatorTrainingSpot:
        if self.engine.game_context.local_player.reset_count == 0:
            await asyncio.sleep(2)

        training_type = await self._check_training_type()

        level_breakpoint: EngineLevelTrainingBreakpointSetting = None

        player_levels = self._get_player_levels()

        if training_type == RESET_TRAINING_TYPE:
            reset_breakpoint = None
            reset_breakpoints = sorted(
                self.engine.settings.location.reset_breakpoints,
                key=lambda i: i.from_resets,
                reverse=True,
            )

            for bp in reset_breakpoints:
                if bp.from_resets <= self.engine.game_context.local_player.reset_count:
                    reset_breakpoint = bp
                    break

            if not reset_breakpoint:
                raise Error(code='NotResetBreakpointFound')

            level_breakpoints = sorted(reset_breakpoint.level_breakpoints,
                                       key=lambda x: x.from_levels, reverse=True)
            to_levels = self.engine.game_server.max_level
        else:
            level_breakpoints = sorted(self.engine.settings.location.master_breakpoints,
                                       key=lambda x: x.from_levels, reverse=True)
            to_levels = self.engine.game_server.max_level + self.engine.game_server.max_master_level

        for index, lbp in enumerate(level_breakpoints):
            if lbp.from_levels <= player_levels:
                level_breakpoint = lbp
                if index > 0:
                    next_breakpoint = level_breakpoints[index - 1]
                    to_levels = next_breakpoint.from_levels
                break

        if not level_breakpoint:
            raise Error(code='FailedToFindLevelBreakpoint')

        available_monster_spots: list[tuple[
            float,  # monster score
            int,  # path length from fast travel
            WorldMonsterSpot
        ]] = []

        for monster_id in level_breakpoint.target_monster_ids:
            if monster_id in level_breakpoint.avoid_monster_ids:
                continue

            for world in self.engine.game_database.worlds.values():
                if not world.fast_travels:
                    continue

                if world.id in level_breakpoint.avoid_world_ids:
                    continue

                monster_spots = self._load_world_monster_spots(world.id)
                if not monster_spots:
                    continue

                for monster_spot in monster_spots:

                    if monster_id not in monster_spot.monsters:
                        continue

                    if not monster_spot.fast_travels:
                        continue

                    # check monster avoidance
                    if set(level_breakpoint.avoid_monster_ids).intersection(
                            set(monster_spot.monsters.keys())
                    ):
                        continue

                    nearest_reachable_ft = self._get_nearest_fast_travel_to_monster_spot(
                        monster_spot=monster_spot,
                        lte_player_levels=True
                    )

                    if not nearest_reachable_ft:
                        continue

                    monster_score = 0
                    for ms_monster_id in monster_spot.monsters.keys():
                        ms_monster = self.engine.game_database.monsters[ms_monster_id]
                        ms_monster_numbers = monster_spot.monsters.get(ms_monster_id, 0)
                        ms_monster_ratio = ms_monster_numbers / monster_spot.total_monsters
                        ms_score = (
                                (monster_spot.total_monsters / 10)
                                + (ms_monster.level * ms_monster_ratio)
                        )
                        if monster_score < ms_score:
                            monster_score = ms_score

                    available_monster_spots.append((
                        monster_score,
                        len(monster_spot.fast_travels[nearest_reachable_ft.code]),
                        monster_spot
                    ))

        if not available_monster_spots:
            raise Error(code='FailedToFindTrainingSpot')

        available_monster_spots = sorted(available_monster_spots, key=lambda x: (-x[0], x[1]))

        matched_monster_spot = None
        matched_fast_travel = None

        world_maps: dict[int, dict[str, WorldCell]] = {}

        for _, _, ms in available_monster_spots:

            fast_travel = self._get_nearest_fast_travel_to_monster_spot(
                monster_spot=ms,
                lte_player_levels=True
            )
            if ms.world_id not in world_maps:
                world_maps[ms.world_id] = self.engine.world_map_handler.load_world_cells(ms.world_id)

            world_map = world_maps[ms.world_id]

            await self._go_to(
                ms.world_id,
                ms.coord,
                fast_travel,
                world_cells=world_map,
                path_to_coord_from_fast_travel=ms.fast_travels[fast_travel.code]
            )

            # check if there are any other players in the training area
            viewport_players_in_area = list(filter(
                lambda i: calculate_distance(
                    (i.object_coord.x, i.object_coord.y),
                    (ms.coord.x, ms.coord.y),
                ) <= self.engine.settings.location.training_radius,
                self.engine.game_context.viewport.object_players.values()
            ))

            if not viewport_players_in_area:
                matched_monster_spot = ms
                matched_fast_travel = fast_travel
                break

            has_party_members = False
            while viewport_players_in_area:
                vpp = viewport_players_in_area.pop()
                if self._player_in_party(vpp):
                    has_party_members = True
                    await asyncio.sleep(0.1)
                    continue

                if ((not self.engine.game_context.party_manager.is_in_party
                     or self.engine.game_context.party_manager.is_leader
                     or len(self.engine.game_context.party_manager.members) < self.engine.game_server.max_party_members)
                        and self.engine.settings.party.auto_send_while_training):
                    accepted = await self._try_partying_player(vpp, ms)
                    if accepted:
                        has_party_members = True
                await asyncio.sleep(0.1)

            if has_party_members:
                matched_monster_spot = ms
                matched_fast_travel = fast_travel
                break

            # the monster spot is occupied
            occupied_at = get_now()
            self._occupied_monster_spots[ms.code] = occupied_at

            if self.engine.settings.location.occupancy_handling == STAY_AND_KS:
                matched_monster_spot = ms
                matched_fast_travel = fast_travel
                break

        if not matched_monster_spot:
            # all available spots are occupied,
            # so we'll just pick the best one
            _, _, matched_monster_spot = available_monster_spots[0]
            matched_fast_travel = self._get_nearest_fast_travel_to_monster_spot(
                monster_spot=matched_monster_spot,
                lte_player_levels=True
            )

        world = self.engine.game_database.worlds[matched_monster_spot.world_id]

        # load the map around the monster spot
        ms_map = self.engine.world_map_handler.crop(
            bounding_box=self._get_training_spot_bounding_box(),
            center=(matched_monster_spot.coord.x, matched_monster_spot.coord.y),
            world_id=matched_monster_spot.world_id,
        )

        return EngineOperatorTrainingSpot(
            monster_spot=matched_monster_spot,
            monster_spots=available_monster_spots,
            world=world,
            fast_travel=matched_fast_travel,
            setting=level_breakpoint,
            to_levels=to_levels,
            map=ms_map,
            training_type=training_type,
            world_map=world_maps[world.id]
        )

    def _get_nearest_fast_travel_to_monster_spot(self,
                                                 monster_spot: WorldMonsterSpot,
                                                 lte_player_levels: bool = False,
                                                 ) -> WorldFastTravel | None:
        player_levels = self._get_player_levels()
        world = self.engine.game_database.worlds[monster_spot.world_id]
        result = None
        length = None
        for ftc, pts in monster_spot.fast_travels.items():
            ft = world.fast_travels[ftc]
            if lte_player_levels and ft.lvl_require > player_levels:
                continue
            pts_length = len(pts)
            if result is None:
                result = ft
                length = pts_length
            else:
                if length > pts_length:
                    result = ft
                    length = pts_length

        return result

    async def _ensure_monster_in_sight(self,
                                       training_spot: EngineOperatorTrainingSpot,
                                       viewport_monster: ViewportObject,
                                       max_attempts: int = 5
                                       ):

        attempts = 0
        while attempts < max_attempts:
            player_relative_coord = self._get_relative_coord_with_training_spot_map(
                training_spot,
                self.engine.game_context.local_player.current_coord
            )
            vpm = self.engine.game_context.viewport.object_monsters.get(viewport_monster.addr)
            if not vpm:
                return

            vpm_relative_coord = self._get_relative_coord_with_training_spot_map(
                training_spot,
                vpm.object_coord
            )

            if self.engine.world_map_handler.has_line_of_sight(
                    cells=training_spot.map,
                    point_1=(player_relative_coord.x, player_relative_coord.y),
                    point_2=(vpm_relative_coord.x, vpm_relative_coord.y),
            ):
                return

            await self.engine.function_triggerer.move_to_coord(vpm.object_coord)
            attempts += 1
            await asyncio.sleep(1)

        # can't get to it,
        # so we ignore this monster
        self._ignore_monster(viewport_monster)

    def _ignore_monster(self, viewport_monster: ViewportObject):
        self._ignored_monsters[viewport_monster.addr] = get_now() + timedelta(seconds=15)

    def _get_training_spot_bounding_box(self) -> tuple[int, int, int, int]:
        return tuple([self.engine.settings.location.training_radius] * 4)

    def _get_relative_coord_with_training_spot_map(self,
                                                   training_spot: EngineOperatorTrainingSpot,
                                                   coord: Coord | GameCoord
                                                   ) -> Coord:
        training_radius = self.engine.settings.location.training_radius

        dx = training_spot.monster_spot.coord.x - coord.x
        dy = training_spot.monster_spot.coord.y - coord.y

        return Coord(
            x=training_radius + dx,
            y=training_radius + dy,
        )

    async def _try_partying_player(self,
                                   viewport_player: ViewportObject,
                                   monster_spot: WorldMonsterSpot = None,
                                   ) -> bool:

        player = self.engine.game_context.local_player
        vpp = self.engine.game_context.viewport.object_players.get(viewport_player.addr)
        if not vpp:
            return False

        max_attempts = self.engine.settings.party.max_sending_attempts
        wait_count = 0
        wait_time = 10
        attempts: int = 0
        last_sent = self._party_requests_sent.get(vpp.object.name)
        while (self._player_valid_to_party(vpp, monster_spot)
               and attempts < max_attempts):
            while calculate_distance(
                    (player.current_coord.x, player.current_coord.y),
                    (vpp.object_coord.x, vpp.object_coord.y),
            ) > 2:
                await self.engine.function_triggerer.move_to_coord(vpp.object_coord)
                await asyncio.sleep(1)
                player = self.engine.game_context.local_player
                vpp = self.engine.game_context.viewport.object_players.get(viewport_player.addr)
                if not vpp:
                    return self._player_in_party(viewport_player)

            now = get_now()
            if not last_sent or last_sent + timedelta(seconds=wait_time) <= now:
                await self.engine.function_triggerer.send_chat('pt pls')
                await self.engine.function_triggerer.send_party_request(
                    viewport_player=vpp,
                )
                last_sent = now
                self._party_requests_sent[vpp.object.name] = now
                attempts += 1

            while wait_count < wait_time and not self._player_in_party(vpp):
                player = self.engine.game_context.local_player
                vpp = self.engine.game_context.viewport.object_players.get(viewport_player.addr)
                if not vpp:
                    return self._player_in_party(viewport_player)
                wait_count += 1
                await asyncio.sleep(1)

        return self._player_in_party(viewport_player)

    def _player_valid_to_party(self,
                               viewport_player: ViewportObject,
                               monster_spot: WorldMonsterSpot = None,
                               ) -> bool:
        if self._player_in_party(viewport_player):
            return False

        if viewport_player.addr not in self.engine.game_context.viewport.object_players:
            return False

        if viewport_player.object.name in self._party_requests_sent:
            last_sent = self._party_requests_sent[viewport_player.object.name]
            if last_sent + timedelta(minutes=5) > get_now():
                return False

        if monster_spot:
            vpp = self.engine.game_context.viewport.object_players[viewport_player.addr]
            if calculate_distance(
                    (vpp.object_coord.x, vpp.object_coord.y),
                    (monster_spot.coord.x, monster_spot.coord.y),
            ) > self.engine.settings.location.training_radius:
                return False
        return True

    def _player_in_party(self, viewport_player: ViewportObject) -> bool:
        if not self.engine.game_context.party_manager.is_in_party:
            return False
        member_names = [pm.player_name.strip().lower() for pm in
                        self.engine.game_context.party_manager.members.values()]
        return viewport_player.object.name.strip().lower() in member_names

    def _training_spot_valid(self,
                             training_spot: EngineOperatorTrainingSpot,
                             ):

        player_level = self._get_player_levels()
        return training_spot.setting.from_levels <= player_level < training_spot.to_levels

    @staticmethod
    def gen_training_spot_code(channel_id: int, world_id: int, coord: Coord):
        return f'{channel_id}${world_id}${coord.x}-{coord.y}'

    async def _ensure_within_training_area(self,
                                           training_spot: EngineOperatorTrainingSpot,
                                           ):
        while self.engine.game_context.is_channel_switching:
            await asyncio.sleep(1)

        fast_travel = training_spot.fast_travel
        path_to_ms_from_tf = training_spot.monster_spot.fast_travels[fast_travel.code]
        player_levels = self._get_player_levels()

        already_change_world_with_fast_travel = False
        while self.engine.game_context.screen.world_id != training_spot.world.id:
            if fast_travel.lvl_require <= player_levels:
                await self._change_world(training_spot.world.id, fast_travel.code)
                already_change_world_with_fast_travel = True
            else:
                await self._change_world(training_spot.world.id)

        while not self._within_area(
                world=training_spot.world,
                coord=training_spot.monster_spot.coord,
                radius=self.engine.settings.location.training_radius,
        ):

            if (fast_travel.lvl_require <= player_levels
                    and not already_change_world_with_fast_travel):
                path_to_ts_from_player = self.engine.world_map_handler.find_path(
                    cells=training_spot.world_map,
                    start=(
                        self.engine.game_context.local_player.current_coord.x,
                        self.engine.game_context.local_player.current_coord.y
                    ),
                    goal=(
                        training_spot.monster_spot.coord.x,
                        training_spot.monster_spot.coord.y
                    )
                )
                if not path_to_ts_from_player or len(path_to_ts_from_player) > len(path_to_ms_from_tf):
                    await self._change_world(training_spot.world.id, fast_travel.code)

            if self.engine.game_context.screen.world_id != training_spot.world.id:
                return await self._ensure_within_training_area(training_spot)

            await self.engine.function_triggerer.move_to_coord(training_spot.monster_spot.coord)

            await asyncio.sleep(1)

        return None

    async def _go_to(self,
                     world_id: int,
                     coord: Coord,
                     fast_travel: WorldFastTravel = None,
                     distance_error: int = 2,
                     world_cells: dict[str: WorldCell] = None,
                     path_to_coord_from_fast_travel: list[Coord] = None,
                     ):
        while self.engine.game_context.is_channel_switching:
            await asyncio.sleep(1)

        if not world_cells:
            world_cells = self.engine.world_map_handler.load_world_cells(world_id)

        player_levels = self._get_player_levels()

        if self.engine.game_context.screen.world_id != world_id:
            if fast_travel and fast_travel.lvl_require <= player_levels:
                await self._change_world(world_id, fast_travel.code)
            else:
                await self._change_world(world_id)

        while calculate_distance(
                (
                        self.engine.game_context.local_player.current_coord.x,
                        self.engine.game_context.local_player.current_coord.y
                ),
                (
                        coord.x,
                        coord.y
                ),
        ) > distance_error:

            path_to_coord_from_player = self.engine.world_map_handler.find_path(
                cells=world_cells,
                start=(
                    self.engine.game_context.local_player.current_coord.x,
                    self.engine.game_context.local_player.current_coord.y
                ),
                goal=(
                    coord.x,
                    coord.y
                )
            )
            if fast_travel and fast_travel.lvl_require <= player_levels:
                if not path_to_coord_from_fast_travel:
                    path_to_coord_from_fast_travel = self.engine.world_map_handler.find_path(
                        cells=world_cells,
                        start=(
                            fast_travel.coord.x,
                            fast_travel.coord.y
                        ),
                        goal=(
                            coord.x,
                            coord.y
                        )
                    )

                if not path_to_coord_from_player or len(path_to_coord_from_player) > len(
                        path_to_coord_from_fast_travel):
                    await self._change_world(world_id, fast_travel.code)

            if self.engine.game_context.screen.world_id != world_id:
                return await self._go_to(
                    world_id=world_id,
                    coord=coord,
                    fast_travel=fast_travel,
                    distance_error=distance_error,
                    world_cells=world_cells,
                    path_to_coord_from_fast_travel=path_to_coord_from_fast_travel
                )

            await self.engine.function_triggerer.move_to_coord(coord)
            await asyncio.sleep(1)

        return None

    async def _change_world(self, world_id: int, fast_travel_code: str = None):
        await self.engine.function_triggerer.change_world(
            world_id,
            fast_travel_code=fast_travel_code
        )
        await asyncio.sleep(3)

        while self.engine.game_context.screen.world_id != world_id:
            await self.engine.function_triggerer.change_world(
                world_id,
                fast_travel_code=fast_travel_code
            )
            await asyncio.sleep(3)

        while self.engine.game_context.screen.is_loading or self.engine.game_context.screen.is_world_loading:
            await asyncio.sleep(1)

    def _within_area(self, world: World, coord: Coord, radius: int) -> bool:
        if self.engine.game_context.screen.world_id != world.id:
            return False
        player_coord = self.engine.game_context.local_player.current_coord
        return calculate_distance(
            (player_coord.x, player_coord.y),
            (coord.x, coord.y)
        ) <= radius

    async def _sell_items(self):
        pass

    def _find_npc(self, world_id: int, npc_type: str, sellig_item_types: list[str] = None) -> NPC | None:
        for npc in self.engine.game_database.npcs.values():
            if world_id not in npc.worlds.keys():
                continue
            if npc_type not in npc.types:
                continue

            if sellig_item_types:
                if not npc.selling_item_types:
                    continue

                for item_type in npc.selling_item_types:
                    if item_type in sellig_item_types:
                        return npc
            else:
                return npc

        return None

    async def _interact_npc(self, npc: NPC):
        nearest_coord = None
        current_distance = None

        player = self.engine.game_context.local_player

        for world_id, coords in npc.worlds.items():
            if world_id != self.engine.game_context.screen.world_id:
                continue

            for coord in coords:
                distance = calculate_distance(
                    (coord.x, coord.y),
                    (player.current_coord.x, player.current_coord.y)
                )
                if nearest_coord:
                    if distance < current_distance:
                        current_distance = distance
                        nearest_coord = coord
                else:
                    nearest_coord = coord
                    current_distance = distance

        if not nearest_coord:
            raise Error(code='FailedToFindNPCNearestCoord')

        while calculate_distance(
                (nearest_coord.x, nearest_coord.y),
                (player.current_coord.x, player.current_coord.y)
        ) > 3:
            await self.engine.function_triggerer.move_to_coord(nearest_coord)
            await asyncio.sleep(2)
            player = self.engine.game_context.local_player

        viewport_npc = None
        for vpn in self.engine.game_context.viewport.object_npcs.values():
            if vpn.object.npc_id == npc.id:
                viewport_npc = vpn

        if not viewport_npc:
            raise Error(
                code='FailedToFindViewportNPC'
            )

        while not self.engine.game_context.merchant.window.is_open:
            await self.engine.function_triggerer.move_to_coord(nearest_coord)
            await asyncio.sleep(1)
            await self.engine.function_triggerer.interact_npc(viewport_npc)

    async def _go_shopping(self):
        if not self.engine.game_context.local_player.in_safe_zone:
            return

        inv_settings = self.engine.settings.inventory

        current_hp_potions: int = 0
        current_mp_potions: int = 0

        for gi in self.engine.game_context.player_inventory.items.values():
            if HP_POTION_ITEM_TYPE in gi.item.types:
                current_hp_potions += gi.quantity

            if MP_POTION_ITEM_TYPE in gi.item.types:
                current_mp_potions += gi.quantity

        potion_merchant_npc = self._find_npc(
            world_id=self.engine.game_context.screen.world_id,
            npc_type=NPC_MERCHANT_TYPE,
            sellig_item_types=[POTION_ITEM_TYPE]
        )

        if inv_settings.buy_hp_potions and potion_merchant_npc:
            if inv_settings.num_of_hp_potions > current_hp_potions:

                if not self.engine.game_context.merchant.window.is_open:
                    await self._interact_npc(potion_merchant_npc)

                target_hp_potion = None
                for gi in self.engine.game_context_synchronizer.load_merchant_storage_items().values():
                    if HP_POTION_ITEM_TYPE not in gi.item.types:
                        continue

                    if target_hp_potion:
                        if target_hp_potion.quantity < gi.quantity:
                            target_hp_potion = gi
                    else:
                        target_hp_potion = gi

                if target_hp_potion:
                    while current_hp_potions < inv_settings.num_of_hp_potions:
                        await self.engine.function_triggerer.purchase_item(target_hp_potion)
                        current_hp_potions += target_hp_potion.quantity
                        await asyncio.sleep(0.1)

        if inv_settings.buy_mp_potions and inv_settings.num_of_mp_potions > 0 and potion_merchant_npc:
            if inv_settings.num_of_mp_potions > current_mp_potions:
                if not self.engine.game_context.merchant.window.is_open:
                    await self._interact_npc(potion_merchant_npc)

                target_mp_potion = None
                for gi in self.engine.game_context_synchronizer.load_merchant_storage_items().values():
                    if MP_POTION_ITEM_TYPE not in gi.item.types:
                        continue

                    if target_mp_potion:
                        if target_mp_potion.quantity < gi.quantity:
                            target_mp_potion = gi
                    else:
                        target_mp_potion = gi

                if target_mp_potion:
                    while current_mp_potions < inv_settings.num_of_mp_potions:
                        await self.engine.function_triggerer.purchase_item(target_mp_potion)
                        current_mp_potions += target_mp_potion.quantity
                        await asyncio.sleep(0.1)

        while self.engine.game_context.merchant.window.is_open:
            await self.engine.function_triggerer.close_window(
                self.engine.game_context.merchant.window
            )
            await asyncio.sleep(0.1)

    # ensure no mem leak
    def _clear_ignored_monsters(self):
        vpm_addrs = list(self._ignored_monsters.keys())
        for vpm_addr in vpm_addrs:
            ignorance_expire = self._ignored_monsters[vpm_addr]
            if ignorance_expire + timedelta(seconds=5) <= get_now():
                self._ignored_monsters.pop(vpm_addr, None)

    async def handle_basis_tasks(self):
        while not self.engine.shutdown_event.is_set():
            try:
                await self._handle_auto_stats()
                await self._handle_item_dropping()
                await self._ensure_items_are_repaired()
                self._clear_ignored_monsters()
            except Exception as e:
                capture_error(e)
            await asyncio.sleep(5)

    async def _handle_item_dropping(self):

        if not self.engine.game_context.player_inventory:
            return

        if self.engine.settings.inventory.only_drop_while_training:
            if self.engine.mode != ENGINE_TRAINING_MODE:
                return

        inv_items = self.engine.game_context.player_inventory.items

        drop_item_ids = self.engine.settings.inventory.drop_item_ids

        if not drop_item_ids:
            return

        for gi in inv_items.values():
            if gi.item_id not in drop_item_ids:
                continue

            await self.engine.function_triggerer.drop_item(gi)
            await asyncio.sleep(0.1)

    async def _handle_auto_stats(self):
        player = self.engine.game_context.local_player

        if not player:
            return

        if player.free_stat_points < 100:
            return

        auto_stats = self.engine.settings.stats.auto_stats

        current_stats: dict[str, int] = {
            PLAYER_STR_STAT: getattr(player, PLAYER_STR_STAT, 0),
            PLAYER_AGI_STAT: getattr(player, PLAYER_AGI_STAT, 0),
            PLAYER_VIT_STAT: getattr(player, PLAYER_VIT_STAT, 0),
            PLAYER_ENE_STAT: getattr(player, PLAYER_ENE_STAT, 0),
            PLAYER_CMD_STAT: getattr(player, PLAYER_CMD_STAT, 0),
        }

        needed_stats: dict[str, int] = {}
        for stat, (point, enabled) in auto_stats.items():
            if enabled:
                needed_stats[stat] = point
            else:
                needed_stats[stat] = 0

        adding_stats: dict[str, int] = calculate_point_distribution(
            free_points=player.free_stat_points,
            current_stats=current_stats,
            needed_stats=needed_stats,
        )

        for stat_code, adding_amount in adding_stats.items():
            if not adding_amount:
                continue
            await self.engine.function_triggerer.add_stats(stat_code, adding_amount)
