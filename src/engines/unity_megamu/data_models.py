from src.bases.engines.data_models import (
    GameContext,
    EngineSettings,
    Viewport,
    ChatFrame,
    EngineMeta,
    SimulatedDataMemory,
    LocalPlayer,
    PlayerInventory,
    Storage,
    Merchant,
    SimulatedFuncParams,
    ChannelConnection, LoginScreen
)


class UnityMegaMUPlayerInventory(PlayerInventory):
    ext1_storage: Storage | None = None
    ext2_storage: Storage | None = None
    ruuh: int = 0


class UnityMegaMUMerchant(Merchant):
    pass


class UnityMegaMUChannelConnection(ChannelConnection):
    send_count: int = 0


class UnityMegaMULocalPlayer(LocalPlayer):
    pass


class UnityMegaMUSettings(EngineSettings):
    pass


class UnityMegaMUViewport(Viewport):
    object_list_addr: int


class UnityMegaMUChatFrame(ChatFrame):
    pass



class UnityMegaMULoginScreen(LoginScreen):
    login_locked: bool = False


class UnityMegaMUGameContext(GameContext):
    viewport: UnityMegaMUViewport | None = None
    chat_frame: UnityMegaMUChatFrame | None = None
    player_inventory: UnityMegaMUPlayerInventory | None = None
    merchant: UnityMegaMUMerchant | None = None

    player_body_object_class_addr: int | None = None  # to check if the GameBody is PlayerBody
    viewport_body_object_class_addr: int | None = None  # to check if the ViewportObject is Body


class UnityMegaMUSimulatedFuncParams(SimulatedFuncParams):
    ## simulated data
    data_attack_coord: int
    data_submit_text: int
    data_move_coord: int
    data_item_dropping_coord: int
    data_stat_points: int
    data_notification_list: int
    data_account_username: int
    data_account_password: int

    ## pointers
    ptr_il2cpp_thread: int  # holding remote thead for the triggers
    ptr_game_context: int
    ptr_login_screen: int
    ptr_lobby_screen: int
    ptr_target_channel_id: int
    ptr_target_character_slot: int
    ptr_local_player: int
    ptr_target_window: int
    ptr_target_stat_index: int
    ptr_player_window: int
    ptr_chat_frame: int
    ptr_target_body: int
    ptr_target_body_index: int
    ptr_attack_skill: int
    ptr_picked_up_item: int
    ptr_picked_up_viewport_object_index: int
    ptr_item_to_drop: int
    ptr_item_to_use: int
    ptr_item_to_repair: int
    ptr_player_active_skills: int
    ptr_target_npc: int
    ptr_target_storage: int
    ptr_target_storage_slot_index: int
    ptr_viewport_object_is_item: int
    ptr_target_viewport_object: int
    ptr_target_viewport_object_index: int
    ptr_target_party_member_index: int
    ptr_current_dialog: int
    ptr_game_data_tables: int
    ptr_world_manager: int
    ptr_world_cell: int
    ptr_func_triggerer_rsp_cache: int
    ptr_save_notification_rsp_cache: int
    ptr_stop_or_die_statue_awake_rsp_cache: int
    ptr_target_func: int
    ptr_game_events: int
    ptr_stop_or_die_statue: int


class UnityMegaMUSimulatedDataMemory(SimulatedDataMemory):
    game_func_params: UnityMegaMUSimulatedFuncParams


class UnityMegaMUEngineMeta(EngineMeta):
    game_assembly_dll: str = 'GameAssembly.dll'
    unity_player_dll: str = 'UnityPlayer.dll'
    main_exe: str = 'MEGAMU.exe'

    ## offsets from game context addr
    screen_offset: int
    window_handler_offset: int
    autologin_offset: int
    channel_switcher_offset: int
    local_player_offset: int
    channel_connection_offset: int
    channel_list_offsets: list[int]
    user_account_offset: int
    viewport_offset: int
    game_ui_offset: int
    lobby_screen_offset: int
    login_screen_offset: int
    npc_interacter_offset: int
    world_manager_offset: int
    loaded_flag_offset: int

    ## offsets from channel addr
    channel_info_offset: int
    channel_current_load_offset: int
    # offsets from channel_info
    channel_id_offset: int
    channel_code_offset: int
    channel_name_offset: int

    ## offsets from autologin addr
    autologin_flag_offsets: list[int]

    ## offsets from lobby screen addr
    lobby_screen_character_slot_list_offset: int
    lobby_screen_current_character_slot_offset: int
    # offsets from lobby screen character slot addr
    lobby_screen_character_slot_character_info_offset: int

    ## offsets from login ui addr
    login_screen_last_state_offset: int
    login_screen_current_state_offset: int
    login_screen_lock_flag_offset: int
    login_screen_username_input_offset: int
    login_screen_server_response_offsets: list[int]

    ## offsets from user account addr
    user_account_info_offset: int
    # offsets from user account info addr
    account_username_offset: int
    account_token_offset: int
    account_character_list_offset: int
    account_hardware_id_offset: int

    ## offsets from character addr
    character_slot_offset: int
    character_name_offset: int
    character_level_offset: int
    character_class_offset: int

    ## offsets from channel switcher
    channel_switching_flag_offset: int

    ## offsets from channel connection addr
    channel_connection_channel_id_offset: int

    ## offsets from world manager addr
    game_world_data_offset: int

    ## offsets from game world data addr
    game_world_default_coord_offset: int
    game_world_cell_list_offset: int

    # offsets from world info addr
    world_id_offset: int
    world_name_offset: int

    ## offsets from world cell addr
    world_cell_flags_offset: int
    world_cell_flags_length: int

    ## offsets from world fast travel addr
    world_fast_travel_name_offset: int
    world_fast_travel_code_offset: int
    world_fast_travel_zen_require_offset: int
    world_fast_travel_lvl_require_offset: int

    ## offsets from local player addr
    player_skill_manager_offset: int
    player_effect_offset: int
    player_inventory_offset: int
    player_party_manager_offset: int
    player_helper_offset: int
    player_free_stat_point_offset: int
    player_master_level_offset: int
    player_exp_offset: int
    player_strength_offset: int
    player_agility_offset: int
    player_vitality_offset: int
    player_energy_offset: int
    player_command_offset: int
    player_reset_count_offset: int

    # offsets from local player object class addr
    player_body_object_class_offset: int

    ## offsets from party manager addr
    party_manager_in_party_flag_offset: int
    party_manager_leader_flag_offset: int
    party_manager_member_list_offset: int

    ## offsets from party member addr
    party_member_index_offset: int
    party_member_name_offset: int
    party_member_leader_flag_offset: int
    party_member_channel_id_offset: int
    party_member_hp_rate_offset: int
    party_member_mp_rate_offset: int
    party_member_world_id_offset: int
    party_member_coord_offset: int
    party_member_viewport_index_offset: int

    ## offsets from player effect addr
    player_effect_dict_offset: int

    ## offsets from effect addr
    effect_data_offset: int
    ## offsets from effect data addr
    effect_id_offset: int
    effect_name_offset: int
    effect_desc_offset: int

    ## offsets from player inventory addr
    player_inventory_item_list_offset: int
    player_inventory_max_slots: int
    player_inventory_zen_offset: int
    player_inventory_ruuh_offset: int

    # offsets from game ui addr
    chat_frame_offset: int
    noti_frame_offset: int
    player_frame_offset: int
    player_window_offset: int
    event_window_offset: int
    inventory_window_offset: int
    merchant_offset: int

    ## offsets from event window addr
    event_list_offset: int
    # offsets from event addr
    event_data_offset: int
    event_time_offset: int
    # offsets from event data addr
    event_id_offset: int
    event_name_offset: int

    # offsets from merchant window addr
    merchant_window_offset: int
    merchant_storage_offset: int

    ## offsets from window handler addr
    window_handler_focused_window_offset: int

    # offsets from window addr
    window_dialog_flag_offset: int
    window_open_flag_offset: int

    # offsets from player frame addr
    player_exp_rate_offsets: list[int]

    # offsets from inventory window addr
    inventory_window_main_storage_offset: int
    inventory_window_ext1_storage_offset: int
    inventory_window_ext2_storage_offset: int

    # offsets from storage addr
    storage_col_count_offset: int
    storage_row_count_offset: int
    storage_slots_offset: int
    storage_item_count_offset: int
    storage_enable_offset: int

    # offsets from item slot addr
    storage_slot_index_offset: int
    storage_slot_index_length: int
    storage_slot_item_pointer_offset: int

    # offsets from chat frame addr
    chat_frame_input_field_offset: int

    # offsets from input field addr
    input_field_text_offset: int
    input_field_char_limit_offset: int

    # offsets from viewport addr
    viewport_object_list_offset: int
    # offsets from viewport object item addr
    viewport_object_item_coord_offset: int
    # offsets from viewport object addr
    viewport_game_object_offset: int
    viewport_object_index_offset: int
    viewport_object_index_length: int

    # offsets from game body addr
    game_body_index_offset: int
    game_body_name_offset: int
    game_body_level_offset: int
    game_body_class_id_offset: int
    game_body_current_hp_offset: int
    game_body_max_hp_offset: int
    game_body_current_mp_offset: int
    game_body_max_mp_offset: int
    game_body_current_sd_offset: int
    game_body_max_sd_offset: int
    game_body_current_ag_offset: int
    game_body_max_ag_offset: int
    game_body_current_coord_offset: int
    game_body_target_coord_offset: int
    game_body_summon_owner_name_offset: int
    game_body_is_destroying_offset: int
    game_body_skeleton_offset: int
    game_body_movement_offset: int
    game_body_world_cell_offset: int

    # offsets from body movement addr
    game_body_moving_flag_offset: int

    # offsets from skeleton addr
    skeleton_monster_id_offset: int
    skeleton_monster_info_offset: int

    # offsets from monster info addr
    monster_id_offset: int
    monster_name_offset: int
    monster_code_offset: int
    monster_unknown1_offset: int
    monster_unknown1_length: int
    monster_unknown2_offset: int
    monster_unknown2_length: int

    # offsets from game item addr
    game_item_durability_offset: int
    game_item_durability_length: int
    game_item_quantity_offset: int
    game_item_quantity_length: int
    game_item_improvement_offset: int
    game_item_improvement_length: int
    game_item_info_offset: int

    ## offsets from item info addr
    item_id_offset: int
    item_name_offset: int
    item_code_offset: int
    item_width_offset: int
    item_height_offset: int

    coord_length: int
    coord_header_length: int
    coord_x_offset: int
    coord_y_offset: int
    coord_x_length: int
    coord_y_length: int

    # offsets from screen addr
    screen_id_offset: int
    screen_loading_flag_offset: int
    world_loading_flag_offset: int
    screen_world_id_offset: int

    # offsets from local player skill manager addr
    player_skill_list_offset: int

    ## offsets from skill addr
    skill_id_offset: int
    skill_name_offset: int
    skill_cooldown_offset: int
    skill_cooldown_length: int
    skill_range_offset: int
    skill_elemental_id_offset: int
    skill_elemental_id_length: int
    skill_desc_pointer_offset: int
    skill_desc_offset: int
    skill_effect_id_offset: int

    ## offsets from dialog addr
    dialog_title_offset: int
    dialog_message_offset: int
    dialog_window_offset: int
    dialog_start_time_offset: int

    ## offsets from text component
    text_value_offset: int

    ## offsets from game data table addr
    table_effect_offset: int
    table_world_offset: int

    ## offsets from effect table world addr
    table_world_generic_list_offset: int
    table_world_fast_travel_generic_list_offsets: list[int]

    ## offsets from stop or die statue addr
    stop_or_die_red_signal_flag_offset: int
