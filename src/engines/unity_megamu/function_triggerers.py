import asyncio
from typing import Callable
from functools import wraps

from src.bases.engines.function_triggerers import EngineFunctionTriggerer
from src.bases.engines.data_models import (
    PlayerSkill, GameBody, World, GameItem,
    ViewportObject, NPCBody, Coord, GameCoord, Window, Item, PartyMember, PlayerBody, GameText
)
from src.constants.engine.game_funcs import (
    FUNC_SUBMIT_TEXT,
    FUNC_PLAYER_MOVE,
    FUNC_PLAYER_ATTACK,
    FUNC_PLAYER_PICKUP_ITEM,
    FUNC_PLAYER_USE_ITEM,
    FUNC_PLAYER_DROP_ITEM,
    FUNC_PLAYER_INTERACT_NPC,
    FUNC_PLAYER_PURCHASE_ITEM,
    FUNC_WINDOW_CLOSE,
    FUNC_PLAYER_TELEPORT,
    FUNC_MOVE_TO_PARTY_MEMBER,
    FUNC_SEND_PARTY_RQ,
    FUNC_KICK_PARTY_MEMBER,
    FUNC_ADD_STATS,
    FUNC_REPAIR_ITEM,
    FUNC_HANDLE_PARTY_REQUEST,
    FUNC_LOGIN_SCREEN_SELECT_CHANNEL,
    FUNC_LOGIN_SCREEN_SUBMIT_ACCOUNT_CREDENTIAL,
    FUNC_LOBBY_SCREEN_SELECT_CHARACTER,
    FUNC_GET_GAME_CONTEXT,
    FUNC_PLAYER_GET_ACTIVE_SKILLS,
    FUNC_VIEWPORT_OBJECT_IS_ITEM,
    FUNC_GET_GAME_DATA_TABLES,
    FUNC_GET_GAME_EVENTS
)
from src.bases.errors import Error
from src.utils import str_to_bytes, capture_error


def ensure_no_conflicts(func: Callable):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # check if there's any function being triggered
        while self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=self.engine.simulated_data_memory.game_func_params.ptr_target_func,
        ):
            await asyncio.sleep(0.05)

        # trigger function
        result = await func(self, *args, **kwargs)

        # wait until function completely triggered
        while self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=self.engine.simulated_data_memory.game_func_params.ptr_target_func,
        ):
            await asyncio.sleep(0.05)

        return result

    return wrapper


class UnityMegaMUEngineFunctionTriggerer(EngineFunctionTriggerer):

    @ensure_no_conflicts
    async def is_viewport_object_item(self, address: int):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_viewport_object,
            data=address.to_bytes(8, 'little')
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_VIEWPORT_OBJECT_IS_ITEM
            ].triggers['main'],
        )

    @ensure_no_conflicts
    async def get_game_events(self):
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_GET_GAME_EVENTS
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def get_game_data_tables(self):
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_GET_GAME_DATA_TABLES
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def get_game_context(self):
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_GET_GAME_CONTEXT
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def get_player_skills(self):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_local_player,
            data=self.engine.game_context.local_player.addr.to_bytes(length=8, byteorder='little')
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_GET_ACTIVE_SKILLS
            ].triggers['main']
        )

    def prepare_text(self,
                     address: int,
                     text: str,
                     text_class_addr: int
                     ) -> GameText:
        text_length = len(text)
        text_as_bytes = str_to_bytes(string=text)
        text_length_as_bytes = text_length.to_bytes(4, 'little')

        text_header = text_class_addr.to_bytes(16, 'little')
        data_to_write = text_header + text_length_as_bytes + text_as_bytes
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=address,
            data=data_to_write
        )
        return GameText(
            addr=address,
            value=text,
        )

    @ensure_no_conflicts
    async def _submit_text(self, text: str):
        if not self.engine.game_context.chat_frame:
            raise Error(message='Chat frame does not exits yet')
        text_length = len(text)

        if self.engine.game_context.chat_frame.char_limit:
            text_length = min(text_length, self.engine.game_context.chat_frame.char_limit)
            text = text[:text_length]

        chat_frame_input_field_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.chat_frame.addr + self.engine.meta.chat_frame_input_field_offset,
        )
        input_field_text_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=chat_frame_input_field_addr + self.engine.meta.input_field_text_offset,
        )
        string_class_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=input_field_text_addr
        )
        self.prepare_text(
            address=self.engine.simulated_data_memory.game_func_params.data_submit_text,
            text=text,
            text_class_addr=string_class_addr
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_chat_frame,
            data=self.engine.game_context.chat_frame.addr.to_bytes(
                8, 'little'
            )
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_SUBMIT_TEXT
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def send_chat(self, text: str):
        return await self._submit_text(text)

    @ensure_no_conflicts
    async def change_world(self, world_id: int, fast_travel_code: str = None):
        world = self.engine.game_database.worlds.get(world_id)
        if not world:
            raise Error(code='WorldNotFound', message='World not found')

        if fast_travel_code:
            fast_travel = world.fast_travels.get(fast_travel_code)
            if not fast_travel:
                raise Error(code='FastTravelNotFound', message='Fast travel not found')

        if not fast_travel_code:
            if not world.fast_travels:
                raise Error(code='FastTravelNotFound', message='World has no fast travels')
            fast_travel_code = list(world.fast_travels.keys())[0]

        command = f'/move {fast_travel_code}'
        return await self._submit_text(command)

    @ensure_no_conflicts
    async def move_to_coord(self, coord: Coord | GameCoord):
        if not self.engine.game_context.local_player:
            raise Error(
                message='LocalPlayer not found'
            )

        coord_addr = self.engine.simulated_data_memory.game_func_params.data_move_coord
        self.prepare_coord(
            address=coord_addr,
            coord=coord
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_local_player,
            data=self.engine.game_context.local_player.addr.to_bytes(
                8, 'little'
            )
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_MOVE
            ].triggers['main']
        )

    def prepare_coord(self, address: int, coord: Coord) -> GameCoord:
        coord_x_length = self.engine.meta.coord_x_length
        coord_y_length = self.engine.meta.coord_y_length

        coord_class = 0
        if self.engine.game_context.local_player:
            coord_class = self.engine.os_api.get_value_from_pointer(
                h_process=self.engine.h_process,
                pointer=self.engine.game_context.local_player.current_coord.addr,
            )

        coord_header = coord_class.to_bytes(self.engine.meta.coord_header_length, 'little')

        coord_data = (
                coord_header
                + coord.x.to_bytes(coord_x_length, 'little')
                + coord.y.to_bytes(coord_y_length, 'little')
        )
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=address,
            data=coord_data
        )

        return GameCoord(
            x=coord.x,
            y=coord.y,
            addr=address
        )

    @ensure_no_conflicts
    async def move_to_target(self, body: GameBody) -> None:
        raise NotImplementedError

    @ensure_no_conflicts
    async def follow_target(self, body: GameBody) -> None:
        raise NotImplementedError

    @ensure_no_conflicts
    async def reset_player(self, command: str):
        return await self._submit_text(command)

    @ensure_no_conflicts
    async def pickup_item(self, viewport_object: ViewportObject) -> None:
        if not isinstance(viewport_object.object, GameItem):
            raise Error(
                message=f'Wrong viewport object. Must be viewport of {GameItem.__name__} object.'
            )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_picked_up_viewport_object_index,
            data=viewport_object.index.to_bytes(
                self.engine.meta.viewport_object_index_length,
                'little'
            )
        )
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_picked_up_item,
            data=viewport_object.object_addr.to_bytes(
                8, 'little'
            )
        )
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_PICKUP_ITEM
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def use_item(self, item: GameItem):
        if item.storage_slot_index is None:
            raise Error(
                message='Item not found in inventory'
            )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_storage_slot_index,
            data=item.storage_slot_index.to_bytes(
                8,
                'little'
            )
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_USE_ITEM
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def drop_item(self, item: GameItem, coord: Coord = None):
        if item.storage_slot_index is None:
            raise Error(
                message='Item not found in inventory'
            )

        if not coord:
            coord = Coord(
                x=self.engine.game_context.local_player.current_coord.x,
                y=self.engine.game_context.local_player.current_coord.y,
            )

        coord_addr = self.engine.simulated_data_memory.game_func_params.data_item_dropping_coord
        self.prepare_coord(address=coord_addr, coord=coord)

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_storage_slot_index,
            data=item.storage_slot_index.to_bytes(
                8,
                'little'
            )
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_DROP_ITEM
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def interact_npc(self, viewport_npc: ViewportObject):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_npc,
            data=viewport_npc.object_addr.to_bytes(
                8,
                'little'
            )
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_INTERACT_NPC
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def purchase_item(self, item: GameItem) -> None:
        if not item.storage_slot_index:
            raise Error(
                message='Item missing storage slot index'
            )
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_storage_slot_index,
            data=item.storage_slot_index.to_bytes(
                8,
                'little'
            )
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_PURCHASE_ITEM
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def close_window(self, window: Window) -> None:
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_window,
            data=window.addr.to_bytes(
                8,
                'little'
            )
        )
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_WINDOW_CLOSE
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def teleport(self, coord: Coord):
        self.prepare_coord(
            address=self.engine.simulated_data_memory.game_func_params.data_move_coord,
            coord=coord
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_TELEPORT
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def move_to_party_member(self, party_member: PartyMember):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_party_member_index,
            data=party_member.index.to_bytes(8, 'little')
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_MOVE_TO_PARTY_MEMBER
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def send_party_request(self, viewport_player: ViewportObject):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_viewport_object_index,
            data=viewport_player.index.to_bytes(8, 'little')
        )
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_SEND_PARTY_RQ
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def handle_party_request(self,
                                   viewport_player: ViewportObject,
                                   accept: bool = False):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_viewport_object_index,
            data=viewport_player.index.to_bytes(8, 'little')
        )
        if accept:
            trigger_addr = self.engine.simulated_data_memory.game_funcs[
                FUNC_HANDLE_PARTY_REQUEST
            ].triggers['accept']
        else:
            trigger_addr = self.engine.simulated_data_memory.game_funcs[
                FUNC_HANDLE_PARTY_REQUEST
            ].triggers['reject']

        self._register_function(
            address=trigger_addr
        )

    @ensure_no_conflicts
    async def kick_party_member(self, party_member: PartyMember):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_party_member_index,
            data=party_member.index.to_bytes(8, 'little')
        )
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_KICK_PARTY_MEMBER
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def add_stats(self, stat_code: str, amount: int):

        player_window_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.addr + self.engine.meta.game_ui_offset,
            offsets=[self.engine.meta.player_window_offset]
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_player_window,
            data=player_window_addr.to_bytes(8, 'little')
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.data_stat_points,
            data=amount.to_bytes(8, 'little')
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_stat_index,
            data=self.engine.meta.stat_mappings[stat_code].to_bytes(8, 'little')
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_ADD_STATS
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def melee_attack(self, target: ViewportObject):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_body,
            data=target.object_addr.to_bytes(8, 'little')
        )
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_ATTACK
            ].triggers['melee']
        )

    @ensure_no_conflicts
    async def cast_skill(self,
                         skill: PlayerSkill,
                         target: ViewportObject = None,
                         coord: Coord = None,
                         ):

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_attack_skill,
            data=skill.addr.to_bytes(8, 'little')
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_local_player,
            data=self.engine.game_context.local_player.addr.to_bytes(8, 'little')
        )

        if target:
            if isinstance(target.object, GameBody):
                self.engine.os_api.write_memory(
                    h_process=self.engine.h_process,
                    address=self.engine.simulated_data_memory.game_func_params.ptr_target_body,
                    data=target.object_addr.to_bytes(8, 'little')
                )

                self._register_function(
                    address=self.engine.simulated_data_memory.game_funcs[
                        FUNC_PLAYER_ATTACK
                    ].triggers['cast_skill_at_body']
                )
                return

            raise Error(
                message=f"Unsupported object type to cast skill: {type(target.object)}"
            )

        if not coord:
            player = self.engine.game_context.local_player
            coord = Coord(
                x=player.current_coord.x,
                y=player.current_coord.y,
            )

        self.prepare_coord(
            address=self.engine.simulated_data_memory.game_func_params.data_attack_coord,
            coord=coord
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_PLAYER_ATTACK
            ].triggers['cast_skill_at_coord']
        )

    @ensure_no_conflicts
    async def repair_item(self, item: GameItem):
        if item.storage_slot_index is None:
            raise Error(
                message='Item not found in inventory'
            )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_storage_slot_index,
            data=item.storage_slot_index.to_bytes(8, 'little')
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_REPAIR_ITEM
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def login_screen_select_channel(self, channel_id: int):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_channel_id,
            data=channel_id.to_bytes(0x4, 'little')
        )
        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_LOGIN_SCREEN_SELECT_CHANNEL
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def login_screen_submit_credential(self, username: str, password: str):

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_login_screen,
            data=self.engine.game_context.login_screen.addr.to_bytes(8, 'little')
        )

        text_class_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.game_context.login_screen.addr + self.engine.meta.login_screen_username_input_offset,
            offsets=[self.engine.meta.input_field_text_offset, 0]
        )
        self.prepare_text(
            address=self.engine.simulated_data_memory.game_func_params.data_account_username,
            text=username,
            text_class_addr=text_class_addr
        )
        self.prepare_text(
            address=self.engine.simulated_data_memory.game_func_params.data_account_password,
            text=password,
            text_class_addr=text_class_addr
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_LOGIN_SCREEN_SUBMIT_ACCOUNT_CREDENTIAL
            ].triggers['main']
        )

    @ensure_no_conflicts
    async def lobby_screen_select_character(self, slot: int):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_lobby_screen,
            data=self.engine.game_context.lobby_screen.addr.to_bytes(8, 'little')
        )

        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_character_slot,
            data=slot.to_bytes(0x4, 'little')
        )

        self._register_function(
            address=self.engine.simulated_data_memory.game_funcs[
                FUNC_LOBBY_SCREEN_SELECT_CHARACTER
            ].triggers['main']
        )

    def _register_function(self, address: int):
        self.engine.os_api.write_memory(
            h_process=self.engine.h_process,
            address=self.engine.simulated_data_memory.game_func_params.ptr_target_func,
            data=address.to_bytes(8, 'little')
        )
