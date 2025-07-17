import datetime
from pydantic import BaseModel, Field

from src.utils import get_now
from src.constants.engine import (
    GAME_INIT_SCREEN,
    GAME_LOGIN_SCREEN,
    GAME_CHAR_SELECTION_SCREEN,
    GAME_PLAYING_SCREEN, PLAYER_STR_STAT,
    PLAYER_AGI_STAT, PLAYER_VIT_STAT,
    PLAYER_ENE_STAT, PLAYER_CMD_STAT,
    JEWEL_ITEM_TYPE, EVENT_ITEM_TYPE,
    RUUH_BOX_ITEM_TYPE, KUNDUN_BOX_ITEM_TYPE,
    ANC_ITEM_RARITY, FIND_OTHER_SPOTS, STAY_AND_KS, GAME_EVENT_QUIZ, GAME_EVENT_DUNGEON_ZOMBIE,
    GAME_EVENT_LOREN_TREASURE, GAME_EVENT_MEGA_DROP, EVENT_PARTICIPATION_WAITING_STATUS, GAME_EVENT_STOP_OR_DIE,
)


class LanguageDatabase(BaseModel):
    anagram_index: dict
    length_index: dict
    position_index: dict


class Coord(BaseModel):
    x: int
    y: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Coord):
            return False
        return (self.x, self.y) == (other.x, other.y)

    def __hash__(self) -> int:
        return hash((self.x, self.y))  # Hash based on values

    @property
    def code(self) -> str:
        return f'{self.x}-{self.y}'


class SimulatedFuncParams(BaseModel):
    pass


class SimulatedDataMemoryFunc(BaseModel):
    triggers: dict[str, int]
    callbacks: dict[str, int]


class SimulatedDataMemory(BaseModel):
    ptr_base: int

    game_func_params: SimulatedFuncParams
    game_funcs: dict[str, SimulatedDataMemoryFunc] = Field(default_factory=dict)


class FuncCallback(BaseModel):
    offset: int = 0
    prototype: str
    rsp_cache_key: str


class FuncPatch(BaseModel):
    offset: int = 0
    prototype: str


class FuncTrigger(BaseModel):
    prototype: str
    stack_size: int = 0x28
    without_ret: bool = False


class GameFunction(BaseModel):
    index: int = 0
    signature_pattern: str | None = None
    bytecodes: list[str]
    callbacks: dict[str, FuncCallback] = Field(default_factory=dict)
    triggers: dict[str, FuncTrigger] = Field(default_factory=dict)
    patches: dict[str, FuncPatch] = Field(default_factory=dict)


class EngineMeta(BaseModel):
    stat_mappings: dict[str, int] = {
        PLAYER_STR_STAT: 0,
        PLAYER_AGI_STAT: 1,
        PLAYER_VIT_STAT: 2,
        PLAYER_ENE_STAT: 3,
        PLAYER_CMD_STAT: 4,
    }

    screen_mappings: dict[str, int] = {
        GAME_INIT_SCREEN: 0,
        GAME_LOGIN_SCREEN: 2,
        GAME_CHAR_SELECTION_SCREEN: 3,
        GAME_PLAYING_SCREEN: 4,
    }

    event_mappings: dict[int, str] = {
        24: GAME_EVENT_QUIZ,
        94: GAME_EVENT_STOP_OR_DIE,
    }


class Effect(BaseModel):
    id: int
    name: str | None = None
    desc: str | None = None
    types: list[str] = Field(default_factory=list)


class Monster(BaseModel):
    id: int
    name: str
    code: str
    level: int | None = None
    world_ids: list[int] = Field(default_factory=list)


class Item(BaseModel):
    id: int
    name: str
    code: str
    width: int | None = None
    height: int | None = None
    types: list[str] = Field(default_factory=list)
    effect_ids: list[int] = Field(default_factory=list)


class WorldCell(BaseModel):
    coord: Coord
    walkable: bool
    is_safezone: bool


class WorldPortal(BaseModel):
    coord: Coord
    world_id: int
    to_portal_id: int
    lvl_require: int


class WorldMonsterSpot(BaseModel):
    coord: Coord
    monsters: dict[int, int] = Field(default_factory=dict)
    total_monsters: int = 0
    world_id: int
    fast_travels: dict[str, list[Coord]] = Field(default_factory=dict)
    fast_travel_code: str | None = None
    path_to_spot: list[Coord] = Field(default_factory=list)

    @property
    def code(self) -> str:
        return f'{self.world_id}${self.coord.code}'


class WorldFastTravel(BaseModel):
    coord: Coord
    lvl_require: int
    zen_require: int = 0
    name: str | None = None
    code: str


class World(BaseModel):
    id: int
    name: str | None = None
    default_coord: Coord | None = None
    fast_travels: dict[str, WorldFastTravel] = Field(default_factory=dict)
    portals: dict[int, WorldPortal] = Field(default_factory=dict)


class NPC(BaseModel):
    id: int
    name: str
    code: str
    types: list[str] = Field(default_factory=list)
    selling_item_types: list[str] = Field(default_factory=list)
    worlds: dict[int, list[Coord]] = Field(default_factory=dict)


class GameObject(BaseModel):
    addr: int
    object_type_addr: int | None = None


class GameCoord(GameObject, Coord):
    pass


class GameText(GameObject):
    value: str = ''


class GameServer(BaseModel):
    filepath: str
    filename: str
    target_filepath: str
    filedir: str
    name: str
    code: str
    version: str
    patch_version: str
    cache_dir: str
    has_rr_system: bool = True
    ingame_rr_command: str = '/reset'
    game_assembly_filepath: str | None = None
    il2cpp_meta_filepath: str | None = None
    il2cpp_dump_dir: str | None = None
    func_struct_filepath: str | None = None
    max_rr: int = 200
    max_level: int = 400
    has_master_level: bool = False
    max_master_level: int = 700
    max_party_members: int = 5
    potion_cooldown: int = 0  # seconds


class SystemInfo(BaseModel):
    name: str
    code: str
    version: str


class Screen(BaseModel):
    id: int
    name: str


class EngineGameEventSettings(BaseModel):
    code: str
    auto_participate: bool = False
    priority: int = 1
    quiz_first_answer_delay: int = 3


class EnginePVESkillSettings(BaseModel):
    offensive_skill_ids: list[int] = Field(default_factory=list)
    buff_skill_ids: list[int] = Field(default_factory=list)


class EnginePVPSkillSettings(BaseModel):
    offensive_skill_ids: list[int] = Field(default_factory=list)
    buff_skill_ids: list[int] = Field(default_factory=list)


class EngineSkillSettings(BaseModel):
    get_npc_buff: bool = True

    pve: EnginePVESkillSettings = EnginePVESkillSettings()
    pvp: EnginePVPSkillSettings = EnginePVPSkillSettings()


class EngineLevelTrainingBreakpointSetting(BaseModel):
    id: int
    from_levels: int
    target_monster_ids: list[int]
    avoid_monster_ids: list[int] = Field(default_factory=list)
    avoid_world_ids: list[int] = Field(default_factory=list)


class EngineResetTrainingBreakpointSetting(BaseModel):
    id: int
    from_resets: int
    level_breakpoints: list[EngineLevelTrainingBreakpointSetting]


class EngineLocationSettings(BaseModel):
    occupancy_handling: str = STAY_AND_KS
    training_radius: int = 8
    chase_beyond_radius: bool = False

    reset_breakpoints: list[EngineResetTrainingBreakpointSetting] = Field(default_factory=list)
    master_breakpoints: list[EngineLevelTrainingBreakpointSetting] = Field(default_factory=list)


class EngineProtectionRecoverySettings(BaseModel):
    use_hp_potions: bool = True
    use_mp_potions: bool = True
    use_sd_potions: bool = True
    use_skills_for_hp: bool = False
    use_skills_for_sd: bool = False
    use_skills_for_mp: bool = False
    hp_percent_to_use_potion: int = 50
    mp_percent_to_use_potion: int = 20
    sd_percent_to_use_potion: int = 50
    hp_percent_to_use_skills: int = 50
    mp_percent_to_use_skills: int = 20
    sd_percent_to_use_skills: int = 50
    skill_ids_for_hp: list[int] = Field(default_factory=list)
    skill_ids_for_sd: list[int] = Field(default_factory=list)
    skill_ids_for_mp: list[int] = Field(default_factory=list)


class EngineProtectionBackToTownSettings(BaseModel):
    when_no_hp_potions_left: bool = True
    when_no_mp_potions_left: bool = True
    when_no_sd_potions_left: bool = False
    town_id: int = 0


class EngineProtectionSettings(BaseModel):
    recovery: EngineProtectionRecoverySettings = EngineProtectionRecoverySettings()
    back_to_town: EngineProtectionBackToTownSettings = EngineProtectionBackToTownSettings()


class EngineInventorySettings(BaseModel):
    pickup_item_types: list[str] = [
        JEWEL_ITEM_TYPE,
        EVENT_ITEM_TYPE,
        RUUH_BOX_ITEM_TYPE,
        KUNDUN_BOX_ITEM_TYPE
    ]
    pickup_item_rarities: list[str] = [
        ANC_ITEM_RARITY
    ]
    pickup_from_list: bool = False
    pickup_item_ids: list[int] = Field(default_factory=list)
    pickup_outside_training_radius: bool = False

    drop_from_list: bool = False
    only_drop_while_training: bool = False
    drop_item_ids: list[int] = Field(default_factory=list)

    auto_repair: bool = True
    use_boost_items: bool = False
    boost_item_ids: list[int] = Field(default_factory=list)

    buy_hp_potions: bool = True
    buy_mp_potions: bool = True
    num_of_hp_potions: int = 255 * 2
    num_of_mp_potions: int = 255 * 2


class EnginePartySettings(BaseModel):
    auto_accept_while_training: bool = True
    auto_send_while_training: bool = True
    only_send_to_specific_players: bool = False
    players_to_send: list[str] = Field(default_factory=list)
    leave_party_after_rr: bool = False
    max_sending_attempts: int = 1


class EngineStatSettings(BaseModel):
    auto_stats: dict[str, tuple[int, bool]] = {
        PLAYER_STR_STAT: (0, False),
        PLAYER_AGI_STAT: (0, False),
        PLAYER_VIT_STAT: (0, False),
        PLAYER_ENE_STAT: (0, False),
        PLAYER_CMD_STAT: (0, False),
    }


class EngineAutologinSettings(BaseModel):
    enabled: bool = False
    relog_if_disconnected: bool = True
    start_training_after: bool = True
    username: str
    password: str
    character_name: str
    channel_id: int


class EngineAccountSettings(BaseModel):
    pass


class EngineSettings(BaseModel):
    location: EngineLocationSettings = EngineLocationSettings()
    skills: EngineSkillSettings = EngineSkillSettings()
    protection: EngineProtectionSettings = EngineProtectionSettings()
    inventory: EngineInventorySettings = EngineInventorySettings()
    party: EnginePartySettings = EnginePartySettings()
    stats: EngineStatSettings = EngineStatSettings()
    account: EngineAccountSettings = EngineAccountSettings()
    events: dict[str, EngineGameEventSettings] = {
        GAME_EVENT_QUIZ: EngineGameEventSettings(
            code=GAME_EVENT_QUIZ,
            auto_participate=True
        ),
        GAME_EVENT_STOP_OR_DIE: EngineGameEventSettings(
            code=GAME_EVENT_STOP_OR_DIE,
            auto_participate=True
        ),
    }


class GameScreen(GameObject):
    screen_id: int | None = None
    screen: Screen | None = None
    world_id: int | None = None
    world: World | None = None
    is_loading: bool = False
    is_world_loading: bool = False


class Skill(BaseModel):
    id: int
    name: str
    desc: str | None = None
    elemental_id: int | None = None
    type: str | None = None
    effect_id: int | None = None


class PlayerClass(BaseModel):
    id: int
    name: str


class GameDatabase(BaseModel):
    # for caching
    monsters: dict[int, Monster] = Field(default_factory=dict)
    skills: dict[int, Skill] = Field(default_factory=dict)
    items: dict[int, Item] = Field(default_factory=dict)
    player_classes: dict[int, PlayerClass] = Field(default_factory=dict)
    npcs: dict[int, NPC] = Field(default_factory=dict)
    worlds: dict[int, World] = Field(default_factory=dict)
    screens: dict[int, Screen] = Field(default_factory=dict)
    effects: dict[int, Effect] = Field(default_factory=dict)


class PlayerSkill(GameObject):
    skill_id: int
    range: int | None = None
    skill: Skill
    cooldown: int = 0


class GameEffect(GameObject):
    effect_id: int
    effect: Effect


class GameBody(GameObject):
    name: str = None
    index: int = 0
    level: int = 0
    class_id: int = 0
    current_hp: int = 0
    max_hp: int = 0
    current_mp: int = 0
    max_mp: int = 0
    current_sd: int = 0
    max_sd: int = 0
    current_ag: int = 0
    max_ag: int = 0
    is_destroying: bool = False
    is_moving: bool = False
    in_safe_zone: bool = False
    current_coord: GameCoord
    target_coord: GameCoord | None = None
    last_update: datetime.datetime = Field(default_factory=get_now)


class MonsterBody(GameBody):
    monster_id: int
    monster: Monster


class SummonBody(MonsterBody):
    owner_name: str


class NPCBody(GameBody):
    npc_id: int
    npc: NPC


class PlayerBody(GameBody):
    player_class: PlayerClass | None = None


class GameItem(GameObject):
    item_id: int
    improvement: int = 0
    quantity: int = 0
    durability: int = 0
    item: Item
    coord: GameCoord | None = None
    location: str
    storage_slot_index: int | None = None
    storage_slot_addr: int | None = None
    last_update: datetime.datetime = Field(default_factory=get_now)


class Window(GameObject):
    is_open: bool = False
    is_dialog: bool = False


class Storage(GameObject):
    items: dict[int, GameItem] = Field(default_factory=dict)
    row_count: int
    col_count: int
    enable: bool


class Merchant(GameObject):
    window: Window
    storage: Storage


class PlayerInventory(GameObject):
    items: dict[int, GameItem]
    main_storage: Storage | None = None
    zen: int = 0


class PartyMember(GameObject):
    index: int
    player_name: str
    is_leader: bool = False
    hp_rate: float = 0.0
    mp_rate: float = 0.0
    world_id: int
    channel_id: int
    coord: GameCoord
    viewport_index: int | None = None


class PartyManager(GameObject):
    is_in_party: bool = False
    is_leader: bool = False
    members: dict[int, PartyMember] = Field(default_factory=dict)


class LocalPlayer(PlayerBody):
    skills: dict[int, PlayerSkill] = Field(default_factory=dict)
    effects: dict[int, GameEffect] = Field(default_factory=dict)
    master_level: int = 0
    reset_count: int = 0
    exp: int = 0
    exp_rate: float = 0.0
    str: int = 0
    agi: int = 0
    vit: int = 0
    ene: int = 0
    cmd: int = 0
    free_stat_points: int = 0

    @property
    def total_levels(self) -> int:
        return self.level + self.master_level


class ViewportObject(GameObject):
    index: int
    object_addr: int
    object_coord: GameCoord
    object: NPCBody | MonsterBody | PlayerBody | GameItem
    object_type: str


class ChatFrame(GameObject):
    char_limit: int


class Viewport(GameObject):
    objects: dict[int, ViewportObject]

    object_monsters: dict[int, ViewportObject]
    object_players: dict[int, ViewportObject]
    object_npcs: dict[int, ViewportObject]
    object_items: dict[int, ViewportObject]
    object_summons: dict[int, ViewportObject]

    monster_count: int = 0
    player_count: int = 0
    item_count: int = 0
    npc_count: int = 0
    summon_count: int = 0
    object_count: int = 0


class Dialog(GameObject):
    title: str
    message: str
    window: Window


class ServerChannel(GameObject):
    id: int
    name: str
    code: str
    current_load: float


class LoginScreen(GameObject):
    last_state: int
    current_state: int
    server_response: dict = Field(default_factory=dict)


class LobbyScreen(GameObject):
    character_slots: dict[str, int] = Field(default_factory=dict)


class GameNotification(BaseModel):
    title: str
    timestamp: datetime.datetime


class GameEvent(BaseModel):
    id: int
    name: str
    code: str
    time: datetime.datetime


class GameContext(GameObject):
    local_player: LocalPlayer | None = None
    player_inventory: PlayerInventory | None = None
    party_manager: PartyManager | None = None
    screen: GameScreen | None = None
    viewport: Viewport | None = None
    chat_frame: ChatFrame | None = None
    merchant: Merchant | None = None
    current_dialog: Dialog | None = None
    loaded: bool = False
    is_channel_switching: bool = False
    channel_id: int = None
    channels: dict[int, ServerChannel] = Field(default_factory=dict)
    login_screen: LoginScreen | None = None
    lobby_screen: LobbyScreen | None = None
    notifications: list[GameNotification] = Field(default_factory=list)
    events: dict[str, GameEvent] = Field(default_factory=dict)


class EngineOperatorTrainingSpot(BaseModel):
    to_levels: int
    monster_spot: WorldMonsterSpot
    monster_spots: list[tuple[float, int, WorldMonsterSpot]]
    fast_travel: WorldFastTravel
    map: dict[str, WorldCell]
    world_map: dict[str, WorldCell]
    world: World
    setting: EngineLevelTrainingBreakpointSetting
    training_type: str

    @property
    def code(self) -> str:
        data = f'{self.world.id}${self.fast_travel.code}${self.monster_spot.coord.code}'
        return data


class EngineOperatorEventParticipation(BaseModel):
    setting: EngineGameEventSettings
    event: GameEvent
    status: str = EVENT_PARTICIPATION_WAITING_STATUS


class EngineOperatorQuiz(BaseModel):
    title: str
    type: str
    content: str


class ChannelConnection(GameObject):
    id: int
