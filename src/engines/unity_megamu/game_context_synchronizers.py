import asyncio
import ctypes
import json
import struct
from json import JSONDecodeError
from datetime import timedelta

from src.bases.engines.prototypes import EnginePrototype
from src.bases.engines.game_context_synchronizers import EngineGameContextSynchronizer
from src.bases.engines.data_models import (
    GameScreen, PlayerSkill, Skill, ViewportObject, PlayerBody, MonsterBody, NPCBody, SummonBody, GameCoord,
    Monster, NPC, GameItem, Item, Storage, GameBody, Coord, Window, Merchant, World, Effect,
    GameEffect, PartyManager, PartyMember, Dialog, WorldCell, ServerChannel, LobbyScreen, GameNotification
)
from src.utils import capture_error, get_now
from src.bases.errors import Error
from src.constants.engine import (
    ITEM_LOCATION_INVENTORY,
    ITEM_LOCATION_GROUND,
    ITEM_LOCATION_MERCHANT_STORAGE, OFFENSIVE_SKILL_TYPE, BUFF_SKILL_TYPE
)
from .data_models import (
    UnityMegaMUGameContext,
    UnityMegaMUChatFrame,
    UnityMegaMUViewport,
    UnityMegaMUPlayerInventory,
    UnityMegaMULocalPlayer,
    UnityMegaMUMerchant, UnityMegaMULoginScreen
)
from src.constants.engine.unity_megamu import (
    FUNC_VIEWPORT_OBJECT_IS_ITEM,
    FUNC_PLAYER_GET_ACTIVE_SKILLS, FUNC_GET_GAME_DATA_TABLES, FUNC_GET_GAME_CONTEXT
)


class UnityMegaMUEngineGameContextSynchronizer(EngineGameContextSynchronizer):

    def decrypt_obscured_int(self, address: int) -> int:
        if not self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=address + 0x8,
                value_size=1
        ):
            return 0

        # current crypto key
        key = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address,
            value_size=4
        )

        # encrypted value
        encrypted_value = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + 0x4,
            value_size=4
        )
        return key ^ encrypted_value

    @classmethod
    def init_context(cls, engine: EnginePrototype) -> UnityMegaMUGameContext:
        result = UnityMegaMUGameContext(
            addr=0,
            screen=GameScreen(
                addr=0,
                screen_id=0
            ),
        )

        return result

    async def update_context(self) -> None:
        while not self.engine.game_context.addr:
            await self.engine.function_triggerer.get_game_context()
            self.engine.game_context.addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=self.engine.simulated_data_memory.game_func_params.ptr_game_context
            )
            await asyncio.sleep(2)

        addr = self.engine.game_context.addr

        is_loaded = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.loaded_flag_offset,
            value_size=1
        ) == 1

        self.engine.game_context.loaded = is_loaded

        if not is_loaded:
            await asyncio.sleep(1)
            return

        self._update_channel_list()

        self._update_login_screen()

        self._update_lobby_screen()

        is_channel_switching = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.channel_switcher_offset,
            offsets=[self.engine.meta.channel_switching_flag_offset]
        ) == 1

        self.engine.game_context.is_channel_switching = is_channel_switching

        if is_channel_switching:
            await asyncio.sleep(1)
            return

        channel_id = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.channel_connection_offset,
            offsets=[self.engine.meta.channel_connection_channel_id_offset],
            value_size=0x4
        )
        self.engine.game_context.channel_id = channel_id

        self._update_screen()

        try:
            self._update_current_dialog()
        except Exception as e:
            capture_error(e)

        if self.engine.game_context.screen.screen_id != 4:
            await asyncio.sleep(1)
            return

        if self.engine.game_context.screen.is_loading or self.engine.game_context.screen.is_world_loading:
            await asyncio.sleep(1)
            return

        local_player_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.local_player_offset,
        )
        if local_player_addr:
            player_body_object_class_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=local_player_addr,
                offsets=[self.engine.meta.player_body_object_class_offset]
            )
            self.engine.game_context.player_body_object_class_addr = player_body_object_class_addr

            self._update_local_player(local_player_addr)

            self._update_notifications()
            await self._update_viewport()
            self._update_chat_frame()
            self._update_player_inventory()
            self._update_party_manager()
            self._update_merchant()

    async def load_player_active_skills(self) -> dict[int, PlayerSkill]:
        if not self.engine.game_context.local_player:
            return dict()

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_local_player,
            data=self.engine.game_context.local_player.addr.to_bytes(length=8, byteorder='little')
        )

        await self.engine.function_triggerer.get_player_skills()

        return self._load_player_skills(
            address=self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=self.engine.simulated_data_memory.game_func_params.ptr_player_active_skills
            )
        )

    def _update_party_manager(self) -> PartyManager | None:

        address = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.local_player.addr + self.engine.meta.player_party_manager_offset
        )
        if not address:
            return None

        is_in_party = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_manager_in_party_flag_offset,
            value_size=0x1
        ) == 1

        is_leader = False
        if is_in_party:
            is_leader = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=address + self.engine.meta.party_manager_leader_flag_offset,
                value_size=0x1
            ) == 1

        members = {}

        if is_in_party:
            member_list_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=address + self.engine.meta.party_manager_member_list_offset,
            )

            member_list = self.engine.cs_type_parser.parse_generic_list(member_list_addr)

            for member_addr in member_list.items:
                member = self._load_party_member(address=member_addr)
                members[member.addr] = member

        result = PartyManager(
            addr=address,
            is_in_party=is_in_party,
            is_leader=is_leader,
            members=members,
        )

        self.engine.game_context.party_manager = result

        return result

    def _load_party_member(self, address: int) -> PartyMember:
        index = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_index_offset,
            value_size=0x4
        )

        is_leader = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_leader_flag_offset,
            value_size=0x1
        ) == 1
        player_name = ''
        player_name_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_name_offset,
        )
        if player_name_addr:
            player_name = self.engine.cs_type_parser.parse_string(player_name_addr)

        hp_rate = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_hp_rate_offset,
            value_size=0x4
        )
        hp_rate = struct.unpack('f', struct.pack('I', hp_rate))[0]

        mp_rate = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_mp_rate_offset,
            value_size=0x4
        )
        mp_rate = struct.unpack('f', struct.pack('I', mp_rate))[0]

        world_id = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_world_id_offset,
            value_size=0x4
        )

        channel_id = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_channel_id_offset,
            value_size=0x4
        )

        coord_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_coord_offset,
        )
        coord = self._load_coord_from_addr(address=coord_addr)
        viewport_index = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.party_member_viewport_index_offset,
            value_size=0x4
        )
        if viewport_index == ctypes.c_uint(-1).value:
            viewport_index = None

        return PartyMember(
            addr=address,
            index=index,
            is_leader=is_leader,
            coord=coord,
            viewport_index=viewport_index,
            world_id=world_id,
            channel_id=channel_id,
            hp_rate=hp_rate,
            mp_rate=mp_rate,
            player_name=player_name
        )

    def _load_player_skills(self, address: int) -> dict[int, PlayerSkill]:
        result = dict()

        global_skills = self.engine.game_database.skills

        skill_list = self.engine.cs_type_parser.parse_list(
            address=address,
        )
        for skill_addr in skill_list.items:
            skill_id = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=skill_addr + self.engine.meta.skill_id_offset
            )
            if skill_id in global_skills:
                skill = global_skills[skill_id]
            else:
                skill_name = self.engine.cs_type_parser.parse_string(
                    address=self.engine.os_api.get_value_from_pointer(
                        h_process=self.engine.h_process,
                        pointer=skill_addr + self.engine.meta.skill_name_offset
                    )
                )

                skill = Skill(
                    id=skill_id,
                    name=skill_name,
                )
            if not skill.desc:
                skill_desc = self.engine.cs_type_parser.parse_string(
                    address=self.engine.os_api.get_value_from_pointer(
                        h_process=self.engine.h_process,
                        pointer=skill_addr + self.engine.meta.skill_desc_pointer_offset,
                        offsets=[self.engine.meta.skill_desc_offset]
                    )
                )
                if skill_desc:
                    skill.desc = skill_desc

            skill_elemental_id = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=skill_addr + self.engine.meta.skill_elemental_id_offset,
                value_size=self.engine.meta.skill_elemental_id_length
            )
            skill_type = OFFENSIVE_SKILL_TYPE
            if skill_elemental_id == ctypes.c_uint(-1).value:
                skill_elemental_id = None
                skill_type = BUFF_SKILL_TYPE
            skill.type = skill_type
            skill.elemental_id = skill_elemental_id

            if not skill.effect_id:
                effect_id = self.engine.os_api.get_value_from_pointer(
                    h_process=self.engine.h_process,
                    pointer=skill_addr + self.engine.meta.skill_effect_id_offset,
                    value_size=0x4
                )
                if effect_id is not None:
                    skill.effect_id = effect_id

            global_skills[skill_id] = skill

            skill_range = self.decrypt_obscured_int(
                address=skill_addr + self.engine.meta.skill_range_offset
            )
            cooldown = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=skill_addr + self.engine.meta.skill_cooldown_offset,
                value_size=0x4
            )

            player_skill = PlayerSkill(
                skill=skill,
                skill_id=skill_id,
                range=skill_range,
                addr=skill_addr,
                cooldown=cooldown
            )
            result[skill_id] = player_skill

        return result

    def _update_merchant(self) -> UnityMegaMUMerchant | None:
        addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.game_ui_offset,
            offsets=[
                self.engine.meta.merchant_offset
            ]
        )
        if not addr:
            self.engine.game_context.merchant_window = None
            return None

        merchant_window = self._load_window(
            address=self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=addr + self.engine.meta.merchant_window_offset
            )
        )
        merchant_storage = self._load_storage(
            address=self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=addr + self.engine.meta.merchant_storage_offset
            )
        )

        merchant = UnityMegaMUMerchant(
            addr=addr,
            window=merchant_window,
            storage=merchant_storage,
        )

        self.engine.game_context.merchant = merchant

        return merchant

    def _load_window(self, address: int) -> Window:
        is_open = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.window_open_flag_offset,
            value_size=1
        ) == 1

        is_dialog = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.window_dialog_flag_offset,
            value_size=1
        ) == 1

        return Window(
            addr=address,
            is_open=is_open,
            is_dialog=is_dialog
        )

    def load_merchant_storage_items(self) -> dict[int, GameItem]:
        if not self.engine.game_context.merchant:
            return dict()

        if not self.engine.game_context.merchant.window.is_open:
            return dict()

        if not self.engine.game_context.merchant.storage:
            return dict()

        self._load_storage_items(self.engine.game_context.merchant.storage)

        return self.engine.game_context.merchant.storage.items

    def _update_player_inventory(self) -> UnityMegaMUPlayerInventory | None:
        inventory_window_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.game_ui_offset,
            offsets=[
                self.engine.meta.inventory_window_offset
            ]
        )

        player_inventory_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.local_player_offset,
            offsets=[
                self.engine.meta.player_inventory_offset
            ]
        )

        if not inventory_window_addr or not player_inventory_addr:
            self.engine.game_context.player_inventory = None
            return None

        zen_addr = player_inventory_addr + self.engine.meta.player_inventory_zen_offset
        zen = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=zen_addr,
            value_size=4
        )
        ruuh_addr = player_inventory_addr + self.engine.meta.player_inventory_ruuh_offset
        ruuh = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=ruuh_addr,
            value_size=4
        )

        items: dict[int, GameItem] = {}

        item_list_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=player_inventory_addr + self.engine.meta.player_inventory_item_list_offset,
        )
        item_list = self.engine.cs_type_parser.parse_list(address=item_list_addr, keep_none=True)
        for slot_index, item_addr in enumerate(item_list.items):
            if not item_addr:
                continue
            game_item = self._load_game_item(
                location=ITEM_LOCATION_INVENTORY,
                address=item_addr,
                storage_slot_index=slot_index
            )
            items[item_addr] = game_item

        inventory = UnityMegaMUPlayerInventory(
            addr=player_inventory_addr,
            items=items,
            zen=zen,
            ruuh=ruuh,
        )

        self.engine.game_context.player_inventory = inventory

        return inventory

    def _load_storage(self, address: int) -> Storage:
        enable = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.storage_enable_offset,
            value_size=1
        ) >= 1
        row_count = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.storage_row_count_offset,
            value_size=4
        )
        col_count = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.storage_col_count_offset,
            value_size=4
        )

        return Storage(
            addr=address,
            enable=enable,
            row_count=row_count,
            col_count=col_count
        )

    def _load_storage_items(self, storage: Storage) -> dict[int, GameItem]:

        result = {}

        slots_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=storage.addr + self.engine.meta.storage_slots_offset
        )

        slots_dict = self.engine.cs_type_parser.parse_generic_dict(address=slots_addr)
        for dict_entry in slots_dict.entries:
            slot_addr = dict_entry.value
            slot_index = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=slot_addr + self.engine.meta.storage_slot_index_offset,
                value_size=self.engine.meta.storage_slot_index_length
            )
            item_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=slot_addr + self.engine.meta.storage_slot_item_pointer_offset,
            )
            if not item_addr:
                continue

            game_item = self._load_game_item(
                location=ITEM_LOCATION_MERCHANT_STORAGE,
                address=item_addr,
                storage_slot_addr=slot_addr,
                storage_slot_index=slot_index
            )
            result[item_addr] = game_item

        storage.items = result

        return result

    def _update_local_player(self, address: int) -> UnityMegaMULocalPlayer:
        reset_count = self.decrypt_obscured_int(
            address=address + self.engine.meta.player_reset_count_offset
        )

        player_body = self._load_game_body(address=address, is_local_player=True)

        exp_addr = address + self.engine.meta.player_exp_offset
        exp = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=exp_addr,
            value_size=8
        )

        exp_rate = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.game_ui_offset,
            offsets=[
                self.engine.meta.player_frame_offset,
                *self.engine.meta.player_exp_rate_offsets
            ],
            value_size=4
        )
        exp_rate = struct.unpack('f', struct.pack('I', exp_rate))[0]

        skill_list_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.player_skill_manager_offset,
            offsets=[self.engine.meta.player_skill_list_offset]
        )

        strength = self.decrypt_obscured_int(
            address=address + self.engine.meta.player_strength_offset
        )
        agility = self.decrypt_obscured_int(
            address=address + self.engine.meta.player_agility_offset
        )
        vitality = self.decrypt_obscured_int(
            address=address + self.engine.meta.player_vitality_offset
        )
        energy = self.decrypt_obscured_int(
            address=address + self.engine.meta.player_energy_offset
        )
        command = self.decrypt_obscured_int(
            address=address + self.engine.meta.player_command_offset
        )
        free_stat_points = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.player_free_stat_point_offset,
            value_size=0x4
        )

        effects = {}
        global_effects = self.engine.game_database.effects

        effect_dict_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.player_effect_offset,
            offsets=[
                self.engine.meta.player_effect_dict_offset
            ]
        )

        master_level = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.player_master_level_offset,
            value_size=0x4
        ) or 0

        effect_dict = self.engine.cs_type_parser.parse_generic_dict(address=effect_dict_addr)
        for dict_entry in effect_dict.entries:
            effect_addr = dict_entry.value
            if not effect_addr:
                continue

            effect_id = dict_entry.key

            effect = global_effects.get(effect_id)
            if not effect:
                effect = Effect(id=effect_id)

            if not effect.name:
                try:
                    effect.name = self.engine.cs_type_parser.parse_string(
                        address=self.engine.os_api.get_value_from_pointer(
                            h_process=self.engine.h_process,
                            pointer=effect_addr + self.engine.meta.effect_data_offset,
                            offsets=[
                                self.engine.meta.effect_name_offset
                            ]
                        )
                    )
                except Exception as e:
                    print('Failed to load effect name at: ', hex(effect_addr))
                    raise e
            if not effect.desc:
                try:
                    effect.desc = self.engine.cs_type_parser.parse_string(
                        address=self.engine.os_api.get_value_from_pointer(
                            h_process=self.engine.h_process,
                            pointer=effect_addr + self.engine.meta.effect_data_offset,
                            offsets=[
                                self.engine.meta.effect_desc_offset
                            ]
                        )
                    )
                except Exception as e:
                    print('Failed to load effect desc at: ', hex(effect_addr))
                    raise e
            global_effects[effect_id] = effect

            game_effect = GameEffect(
                effect_id=effect_id,
                effect=effect,
                addr=effect_addr
            )
            effects[effect_addr] = game_effect

        local_player = UnityMegaMULocalPlayer(
            **player_body.model_dump(),
            skills=self._load_player_skills(address=skill_list_addr),
            master_level=master_level,
            exp=exp,
            exp_rate=exp_rate,
            reset_count=reset_count,
            str=strength,
            agi=agility,
            vit=vitality,
            ene=energy,
            cmd=command,
            effects=effects,
            free_stat_points=free_stat_points
        )

        self.engine.game_context.local_player = local_player

        return local_player

    def _update_chat_frame(self) -> UnityMegaMUChatFrame | None:
        addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.game_ui_offset,
            offsets=[
                self.engine.meta.chat_frame_offset
            ]
        )
        if not addr:
            self.engine.game_context.chat_frame = None
            return None

        char_limit = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.chat_frame_input_field_offset,
            offsets=[
                self.engine.meta.input_field_char_limit_offset
            ]
        )

        self.engine.game_context.chat_frame = UnityMegaMUChatFrame(
            addr=addr,
            char_limit=char_limit
        )
        return self.engine.game_context.chat_frame

    def _update_notifications(self):
        noti_list_addr = self.engine.simulated_data_memory.game_func_params.data_notification_list
        for noti_title_addr in self.engine.cs_type_parser.parse_list(
            address=noti_list_addr
        ).items:
            if not noti_title_addr:
                continue
            try:
                noti_title = self.engine.cs_type_parser.parse_string(noti_title_addr)
            except Exception as e:
                self._logger.error('Failed to load notification title at: ', hex(noti_title_addr))
                capture_error(e)
                continue

            noti_title = noti_title.strip().upper()
            if not noti_title:
                continue

            noti = GameNotification(
                title=noti_title.strip().upper(),
                timestamp=get_now(),
            )
            self.engine.game_context.notifications.insert(0, noti)
            self._logger.info(noti.model_dump())

        self.engine.cs_type_parser.write_list(
            address=noti_list_addr,
            data=[]
        )

        # only cache for 50 notis
        self.engine.game_context.notifications = self.engine.game_context.notifications[:50]

    def _update_current_dialog(self) -> Dialog | None:
        dialog_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.simulated_data_memory.game_func_params.ptr_current_dialog
        )
        if not dialog_addr:
            return None

        window_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=dialog_addr + self.engine.meta.dialog_window_offset,
        )

        focused_window_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.window_handler_offset,
            offsets=[
                self.engine.meta.window_handler_focused_window_offset
            ]
        )
        if window_addr != focused_window_addr:
            return None

        window = self._load_window(
            address=window_addr
        )

        title = ''
        title_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=dialog_addr + self.engine.meta.dialog_title_offset,
            offsets=[self.engine.meta.text_value_offset]
        )
        if title_addr:
            try:
                title = self.engine.cs_type_parser.parse_string(address=title_addr)
            except Exception as e:
                self._logger.error('Failed to load title at: ', hex(title_addr))
                capture_error(e)

        message = ''
        message_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=dialog_addr + self.engine.meta.dialog_message_offset,
            offsets=[self.engine.meta.text_value_offset]
        )
        if message_addr:
            try:
                message = self.engine.cs_type_parser.parse_string(address=message_addr)
            except Exception as e:
                self._logger.error('Failed to load message at: ', hex(message_addr))
                capture_error(e)

        result = Dialog(
            addr=dialog_addr,
            title=title,
            message=message,
            window=window
        )

        self.engine.game_context.current_dialog = result

        return result

    async def _update_viewport(self) -> UnityMegaMUViewport | None:
        viewport_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.viewport_offset,
        )
        if not viewport_addr:
            self.engine.game_context.viewport = None
            return None

        object_list_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=viewport_addr + self.engine.meta.viewport_object_list_offset
        )

        object_list = self.engine.cs_type_parser.parse_generic_dict(
            address=object_list_addr,
        )

        objects = dict()
        object_count = object_list.count
        object_monsters = dict()
        object_players = dict()
        object_npcs = dict()
        object_items = dict()
        object_summons = dict()

        npc_count = 0
        monster_count = 0
        player_count = 0
        item_count = 0
        summon_count = 0

        for cs_dict_entry in object_list.entries:
            if cs_dict_entry.hash_code == ctypes.c_uint(-1).value:
                continue
            viewport_object_addr = cs_dict_entry.value
            object_index = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=viewport_object_addr + self.engine.meta.viewport_object_index_offset,
                value_size=self.engine.meta.viewport_object_index_length
            )
            game_object_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=viewport_object_addr + self.engine.meta.viewport_game_object_offset,
            )

            viewport_body_object_class_addr = self.engine.game_context.viewport_body_object_class_addr
            if viewport_body_object_class_addr is None:
                await self.engine.function_triggerer.is_viewport_object_item(
                    address=viewport_object_addr
                )
                is_item = self.engine.os_api.get_value_from_pointer(
                    h_process=self.engine.h_process,
                    pointer=self.engine.simulated_data_memory.game_func_params.ptr_viewport_object_is_item,
                    value_size=0x1
                ) == 1
            else:
                viewport_object_class_addr = self.engine.os_api.get_value_from_pointer(
                    h_process=self.engine.h_process,
                    pointer=viewport_object_addr
                )
                is_item = viewport_object_class_addr != viewport_body_object_class_addr

            if is_item:
                # Viewport.ObjectItem
                try:
                    object_coord = self._load_coord_from_addr(
                        address=self.engine.os_api.get_value_from_pointer(
                            h_process=self.engine.h_process,
                            pointer=viewport_object_addr + self.engine.meta.viewport_object_item_coord_offset
                        )
                    )
                except Exception as e:
                    print('Failed to load viewport item coord', hex(viewport_object_addr))
                    raise e
                game_object = self._load_game_item(
                    address=game_object_addr,
                    coord=object_coord,
                    location=ITEM_LOCATION_GROUND
                )
            else:
                # Viewport.ObjectBody
                if self.engine.game_context.viewport_body_object_class_addr is None:
                    self.engine.game_context.viewport_body_object_class_addr = self.engine.os_api.get_value_from_pointer(
                        h_process=self.engine.h_process,
                        pointer=viewport_object_addr
                    )

                try:
                    game_object = self._load_viewport_body(
                        address=game_object_addr,
                    )
                except Exception as e:
                    print('Failed to load viewport body', hex(viewport_object_addr))
                    capture_error(e)
                    continue
                object_coord = game_object.current_coord

            viewport_object = ViewportObject(
                index=object_index,
                addr=viewport_object_addr,
                object_addr=game_object_addr,
                object_coord=object_coord,
                object=game_object,
                object_type=game_object.__class__.__name__,
            )

            if isinstance(game_object, PlayerBody):
                player_count += 1
                object_players[viewport_object.addr] = viewport_object
            elif isinstance(game_object, MonsterBody):
                monster_count += 1
                object_monsters[viewport_object.addr] = viewport_object
            elif isinstance(game_object, NPCBody):
                npc_count += 1
                object_npcs[viewport_object.addr] = viewport_object
            elif isinstance(game_object, SummonBody):
                summon_count += 1
                object_summons[viewport_object.addr] = viewport_object
            else:
                item_count += 1
                object_items[viewport_object.addr] = viewport_object
            objects[viewport_object.addr] = viewport_object

        viewport = UnityMegaMUViewport(
            addr=viewport_addr,
            objects=objects,
            object_monsters=object_monsters,
            object_players=object_players,
            object_items=object_items,
            object_npcs=object_npcs,
            object_summons=object_summons,
            object_count=object_count,
            npc_count=npc_count,
            player_count=player_count,
            monster_count=monster_count,
            item_count=item_count,
            summon_count=summon_count,
            object_list_addr=object_list_addr,
        )
        self.engine.game_context.viewport = viewport

        return self.engine.game_context.viewport

    def _load_coord_from_addr(self, address: int) -> GameCoord:
        x = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.coord_x_offset,
            value_size=self.engine.meta.coord_x_length
        )
        y = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.coord_y_offset,
            value_size=self.engine.meta.coord_y_length
        )
        return GameCoord(x=x, y=y, addr=address)

    def _update_screen(self) -> GameScreen:

        addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.screen_offset,
        )
        if addr:
            screen_id = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=addr + self.engine.meta.screen_id_offset,
                value_size=4
            )
            screen = self.engine.game_database.screens.get(screen_id)
            world_id = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=addr + self.engine.meta.screen_world_id_offset,
                value_size=0x4
            )
            world = None
            if world_id is not None:
                world = self.engine.game_database.worlds.get(world_id)
                if not world:
                    world = World(id=world_id)
                if not world.default_coord:
                    world_default_coord_addr = self.engine.os_api.get_value_from_pointer(
                        h_process=self.engine.h_process,
                        pointer=self.engine.game_context.addr + self.engine.meta.world_manager_offset,
                        offsets=[
                            self.engine.meta.game_world_data_offset,
                            self.engine.meta.game_world_default_coord_offset,
                        ]
                    )
                    if world_default_coord_addr:
                        default_coord = self._load_coord_from_addr(world_default_coord_addr)
                        world.default_coord = Coord(x=default_coord.x, y=default_coord.y)

            is_loading = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=addr + self.engine.meta.screen_loading_flag_offset,
                value_size=0x1
            ) == 1

            is_world_loading = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=addr + self.engine.meta.world_loading_flag_offset,
                value_size=0x1
            ) == 1

            game_screen = GameScreen(
                addr=addr,
                screen=screen,
                screen_id=screen_id,
                world_id=world_id,
                world=world,
                is_loading=is_loading,
                is_world_loading=is_world_loading,
            )

            self.engine.game_context.screen = game_screen
        else:
            screen_id = 0
            screen = self.engine.game_database.screens.get(screen_id)
            game_screen = GameScreen(
                addr=0,
                screen=screen,
                screen_id=screen_id,
                is_loading=True,
                is_world_loading=True,
            )
            self.engine.game_context.screen = game_screen

        return self.engine.game_context.screen

    def _load_game_body(self, address: int,
                        is_local_player: bool = False) -> NPCBody | SummonBody | PlayerBody | MonsterBody:
        object_class_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address,
        )

        index = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_body_index_offset,
            value_size=0x4
        )

        name_addr = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_name_offset,
                size=8
            ),
            byteorder='little'
        )
        if name_addr:
            name = self.engine.cs_type_parser.parse_string(
                address=name_addr
            )
        else:
            name = ''

        class_id = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_class_id_offset,
                size=4
            ),
            byteorder='little'
        )
        level = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_level_offset,
                size=4
            ),
            byteorder='little'
        )
        current_hp = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_current_hp_offset,
                size=4
            ),
            byteorder='little'
        )
        max_hp = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_max_hp_offset,
                size=4
            ),
            byteorder='little'
        )
        current_mp = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_current_mp_offset,
                size=4
            ),
            byteorder='little'
        )
        max_mp = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_max_mp_offset,
                size=4
            ),
            byteorder='little'
        )
        current_sd = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_current_sd_offset,
                size=4
            ),
            byteorder='little'
        )
        max_sd = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_max_sd_offset,
                size=4
            ),
            byteorder='little'
        )
        current_ag = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_current_ag_offset,
                size=4
            ),
            byteorder='little'
        )
        max_ag = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_max_ag_offset,
                size=4
            ),
            byteorder='little'
        )
        current_coord_addr = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_current_coord_offset,
                size=8
            ),
            byteorder='little'
        )
        current_coord = self._load_coord_from_addr(address=current_coord_addr)
        target_coord_addr = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_target_coord_offset,
                size=8
            ),
            byteorder='little'
        )
        target_coord = self._load_coord_from_addr(address=target_coord_addr)
        is_destroying = int.from_bytes(
            self.engine.os_api.read_memory(
                h_process=self.engine.h_process,
                address=address + self.engine.meta.game_body_is_destroying_offset,
                size=1
            ),
            byteorder='little'
        ) == 1

        world_cell_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_body_world_cell_offset,
        )

        in_safe_zone = self._world_cell_is_safezone(world_cell_addr)

        body_data = dict(
            addr=address,
            index=index,
            current_coord=current_coord,
            target_coord=target_coord,
            is_destroying=is_destroying,
            name=name,
            class_id=class_id,
            level=level,
            current_hp=current_hp,
            max_hp=max_hp,
            current_mp=current_mp,
            max_mp=max_mp,
            current_sd=current_sd,
            max_sd=max_sd,
            current_ag=current_ag,
            max_ag=max_ag,
            in_safe_zone=in_safe_zone
        )

        body_skeleton_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_body_skeleton_offset,
        )

        if object_class_addr == self.engine.game_context.player_body_object_class_addr or is_local_player:
            body_sub_class = PlayerBody
        else:
            monster_id = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=body_skeleton_addr + self.engine.meta.skeleton_monster_id_offset,
                value_size=0x4
            )

            monster_info_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=body_skeleton_addr + self.engine.meta.skeleton_monster_info_offset,
            )
            monster_unknown2 = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=monster_info_addr + self.engine.meta.monster_unknown2_offset,
                value_size=self.engine.meta.monster_unknown2_length
            )
            monster_code_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=monster_info_addr + self.engine.meta.monster_code_offset,
            )
            monster_code = self.engine.cs_type_parser.parse_string(monster_code_addr)

            if 'monster' in monster_code.lower() or not monster_unknown2:
                summon_owner_name_addr = self.engine.os_api.get_value_from_pointer(
                    h_process=self.engine.h_process,
                    pointer=address + self.engine.meta.game_body_summon_owner_name_offset,
                )

                monsters = self.engine.game_database.monsters

                if monster_id in monsters:
                    monster = monsters[monster_id]
                else:
                    monster_name = name
                    monster = Monster(
                        id=monster_id,
                        name=monster_name,
                        code=monster_code
                    )

                if not monster.level:
                    monster.level = level

                if self.engine.game_context.screen.world_id not in monster.world_ids:
                    monster.world_ids.append(self.engine.game_context.screen.world_id)

                monsters[monster_id] = monster

                body_data['monster'] = monster
                body_data['monster_id'] = monster_id

                if summon_owner_name_addr:
                    body_sub_class = SummonBody
                    body_data['owner_name'] = self.engine.cs_type_parser.parse_string(summon_owner_name_addr)
                else:
                    body_sub_class = MonsterBody
            else:
                body_sub_class = NPCBody

                npc_id = class_id

                global_context_npcs = self.engine.game_database.npcs

                if npc_id in global_context_npcs:
                    npc = global_context_npcs[npc_id]
                else:
                    npc_name = name
                    npc_code = monster_code
                    npc = NPC(
                        id=npc_id,
                        name=npc_name,
                        code=npc_code,
                    )
                world_id = self.engine.game_context.screen.world_id
                coords = npc.worlds.get(world_id) or []
                npc_coord = Coord(
                    x=current_coord.x,
                    y=current_coord.y,
                )
                if npc_coord not in coords:
                    coords.append(npc_coord)

                npc.worlds[world_id] = coords
                global_context_npcs[npc_id] = npc

                body_data['npc'] = npc
                body_data['npc_id'] = npc_id

        if body_sub_class is PlayerBody:
            player_class = None
            if class_id in self.engine.game_database.player_classes:
                player_class = self.engine.game_database.player_classes[class_id]
            body_data['player_class'] = player_class

        return body_sub_class(**body_data)

    def _load_world_cells(self) -> dict[str, WorldCell]:

        cell_list_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.world_manager_offset,
            offsets=[
                self.engine.meta.game_world_data_offset,
                self.engine.meta.game_world_cell_list_offset,
            ]
        )

        cell_list = self.engine.cs_type_parser.parse_list(cell_list_addr)

        result = dict()

        for x in range(256):
            for y in range(256):
                cell_index = x * 256 + y
                cell_addr = cell_list.items[cell_index]
                flags = self.engine.os_api.get_value_from_pointer(
                    h_process=self.engine.h_process,
                    pointer=cell_addr + self.engine.meta.world_cell_flags_offset,
                    value_size=self.engine.meta.world_cell_flags_length
                )
                cell = WorldCell(
                    is_safezone=self._world_cell_is_safezone(cell_addr, flags),
                    walkable=self._world_cell_walkable(cell_addr, flags),
                    coord=Coord(x=x, y=y),
                )
                result[cell.coord.code] = cell

        return result

    def _world_cell_is_safezone(self, address: int, flags: int = None) -> bool:
        if flags is None:
            flags = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=address + self.engine.meta.world_cell_flags_offset,
                value_size=self.engine.meta.world_cell_flags_length
            )
        return (flags & 0x01) != 0

    def _world_cell_walkable(self, address: int, flags: int = None) -> bool:
        if flags is None:
            flags = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=address + self.engine.meta.world_cell_flags_offset,
                value_size=self.engine.meta.world_cell_flags_length
            )

        # Check if bit 2 (0x04) is set
        if flags & 0x04:
            return False

        # Check if bit 3 (0x08) is set
        if flags & 0x08:
            return False

        # Return True only if bit 4 (0x10) is NOT set
        return not (flags & 0x10)

    def _load_viewport_body(self,
                            address: int,
                            ) -> MonsterBody | PlayerBody | NPCBody | SummonBody:
        return self._load_game_body(address=address)

    def _parse_item_info(self, address: int) -> Item:
        item_id = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.item_id_offset,
            value_size=0x4
        )
        item_name_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.item_name_offset,
        )
        item_name = self.engine.cs_type_parser.parse_string(item_name_addr)

        item_code_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.item_code_offset,
        )
        item_code = self.engine.cs_type_parser.parse_string(item_code_addr)

        item_width = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.item_width_offset,
            value_size=0x4
        )

        item_height = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.item_height_offset,
            value_size=0x4
        )
        return Item(
            id=item_id,
            name=item_name,
            code=item_code,
            width=item_width,
            height=item_height,
        )

    async def _load_game_data_tables(self) -> int:
        await self.engine.function_triggerer.get_game_data_tables()

        return self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.simulated_data_memory.game_func_params.ptr_game_data_tables,
        )

    def _load_game_item(self,
                        address: int,
                        location: str,
                        coord: GameCoord | None = None,
                        storage_slot_index: int | None = None,
                        storage_slot_addr: int | None = None,
                        ) -> GameItem:

        if location == ITEM_LOCATION_GROUND:
            if not coord:
                raise Error(
                    message=f'Missing coord for location: {location}'
                )

        item_info = self._parse_item_info(address=self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_item_info_offset,
        ))
        item_id = item_info.id

        global_context_items = self.engine.game_database.items

        if item_id in global_context_items:
            item = global_context_items[item_id]
        else:
            item = Item(
                id=item_info.id,
                name=item_info.name,
                code=item_info.code,
            )

        if not item.width:
            item.width = item_info.width

        if not item.height:
            item.height = item_info.height

        global_context_items[item_id] = item

        improvement = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_item_improvement_offset,
            value_size=self.engine.meta.game_item_improvement_length
        )

        quantity = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_item_quantity_offset,
            value_size=self.engine.meta.game_item_quantity_length
        )

        durability = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=address + self.engine.meta.game_item_durability_offset,
            value_size=self.engine.meta.game_item_durability_length
        )

        return GameItem(
            item=item,
            item_id=item_id,
            improvement=improvement,
            quantity=quantity,
            durability=durability,
            addr=address,
            coord=coord,
            location=location,
            storage_slot_addr=storage_slot_addr,
            storage_slot_index=storage_slot_index
        )

    def _update_login_screen(self):
        addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.login_screen_offset,
        )
        if not addr:
            return

        last_state = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.login_screen_last_state_offset,
            value_size=0x4
        )
        current_state = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.login_screen_current_state_offset,
            value_size=0x4
        )
        login_locked = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.login_screen_lock_flag_offset,
            value_size=0x1
        ) == 1
        server_response_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.login_screen_offset,
            offsets=self.engine.meta.login_screen_server_response_offsets
        )
        if server_response_addr:
            try:
                server_response = json.loads(self.engine.cs_type_parser.parse_string(server_response_addr))
            except JSONDecodeError:
                server_response = dict()
        else:
            server_response = dict()

        self.engine.game_context.login_screen = UnityMegaMULoginScreen(
            addr=addr,
            server_response=server_response,
            login_locked=login_locked,
            current_state=current_state,
            last_state=last_state
        )

    def _update_lobby_screen(self):
        addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.lobby_screen_offset,
        )
        if not addr:
            return

        character_slots = dict()

        character_slot_list_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=addr + self.engine.meta.lobby_screen_character_slot_list_offset,
        )
        for character_slot_addr in self.engine.cs_type_parser.parse_list(character_slot_list_addr).items:
            character_info_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=character_slot_addr + self.engine.meta.lobby_screen_character_slot_character_info_offset,
            )
            if not character_info_addr:
                continue
            character_slot = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=character_info_addr + self.engine.meta.character_slot_offset,
                value_size=0x4
            )
            character_name_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=character_info_addr + self.engine.meta.character_name_offset,
            )
            character_name = self.engine.cs_type_parser.parse_string(character_name_addr)
            character_slots[character_name.lower().strip()] = character_slot

        self.engine.game_context.lobby_screen = LobbyScreen(
            addr=addr,
            character_slots=character_slots
        )

    def _update_channel_list(self) -> dict[int, ServerChannel]:
        result = dict()
        list_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.channel_list_offsets[0],
            offsets=self.engine.meta.channel_list_offsets[1:]
        )
        if not list_addr:
            return result

        channel_list = self.engine.cs_type_parser.parse_generic_list(list_addr)
        for channel_addr in channel_list.items:
            channel_current_load = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=channel_addr + self.engine.meta.channel_current_load_offset,
                value_size=0x4
            )

            channel_id = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=channel_addr + self.engine.meta.channel_info_offset,
                offsets=[
                    self.engine.meta.channel_id_offset
                ],
                value_size=0x4
            )

            channel_code_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=channel_addr + self.engine.meta.channel_info_offset,
                offsets=[
                    self.engine.meta.channel_code_offset
                ],
            )
            channel_code = self.engine.cs_type_parser.parse_string(channel_code_addr)

            channel_name_addr = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=channel_addr + self.engine.meta.channel_info_offset,
                offsets=[
                    self.engine.meta.channel_code_offset
                ],
            )
            channel_name = self.engine.cs_type_parser.parse_string(channel_name_addr)

            result[channel_id] = ServerChannel(
                addr=channel_addr,
                id=channel_id,
                name=channel_name,
                current_load=channel_current_load / 100,
                code=channel_code,
            )

        self.engine.game_context.channels = result

        return result
