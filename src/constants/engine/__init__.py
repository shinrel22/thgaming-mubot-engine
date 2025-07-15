# game screens
GAME_INIT_SCREEN: str = 'GameInitScreen'
GAME_LOGIN_SCREEN: str = 'GameLoginScreen'
GAME_CHAR_SELECTION_SCREEN: str = 'GameCharSelectionScreen'
GAME_PLAYING_SCREEN: str = 'GamePlayingScreen'

# workers
GAME_CONTEXT_SYNCHRONIZER: str = 'GameContextSynchronizer'
ENGINE_OPERATOR: str = 'EngineOperator'

# engine modes
ENGINE_IDLE_MODE: str = 'EngineIdle'
ENGINE_TRAINING_MODE: str = 'EngineTraining'
ENGINE_PARTICIPATING_EVENT_MODE: str = 'EngineParticipatingEvent'

RESET_TRAINING_TYPE: str = 'ResetTrainingType'
MASTER_TRAINING_TYPE: str = 'MasterTrainingType'

# item locations
ITEM_LOCATION_INVENTORY: str = 'Inventory'
ITEM_LOCATION_GROUND: str = 'Ground'
ITEM_LOCATION_MERCHANT_STORAGE: str = 'MerchantStorage'

# NPC types
NPC_MERCHANT_TYPE: str = 'Merchants'
NPC_WAREHOUSE_KEEPER_TYPE: str = 'WarehouseKeepers'

# skill types
OFFENSIVE_SKILL_TYPE: str = 'Offensives'
BUFF_SKILL_TYPE: str = 'Buffs'

# item types
POTION_ITEM_TYPE: str = 'Potions'
HP_POTION_ITEM_TYPE: str = 'HpPotions'
MP_POTION_ITEM_TYPE: str = 'MpPotions'
SD_POTION_ITEM_TYPE: str = 'SdPotions'
TOWN_PORTAL_SCROLL_ITEM_TYPE: str = 'TownPortalScrolls'
JEWEL_ITEM_TYPE: str = 'Jewels'
ZEN_ITEM_TYPE: str = 'Zen'
DROP_BOX_ITEM_TYPE: str = 'DropBoxes'
RUUH_BOX_ITEM_TYPE: str = 'RuuhBoxes'
KUNDUN_BOX_ITEM_TYPE: str = 'KundunBoxes'
EVENT_ITEM_TYPE: str = 'EventItems'
BOOST_ITEM_TYPE: str = 'BoostItems'
EXP_BOOST_ITEM_TYPE: str = 'ExpBoostItems'

# item rarities
EXC_ITEM_RARITY: str = 'ExcRarity'
ANC_ITEM_RARITY: str = 'AncRarity'

# player stats
PLAYER_STR_STAT: str = 'str'
PLAYER_AGI_STAT: str = 'agi'
PLAYER_VIT_STAT: str = 'vit'
PLAYER_ENE_STAT: str = 'ene'
PLAYER_CMD_STAT: str = 'cmd'

FIND_OTHER_SPOTS: str = 'FindOtherSpots'
STAY_AND_KS: str = 'StayAndKs'

# effect types
EXP_BOOST_EFFECT_TYPE: str = 'ExpBoostEffects'

# game events
GAME_EVENT_QUIZ: str = 'GameEventQuiz'
GAME_EVENT_STOP_OR_DIE: str = 'GameEventStopOrDie'
GAME_EVENT_RED_DRAGON_INVASION: str = 'GameEventRedDragonInvasion'
GAME_EVENT_GOLDEN_DRAGON_INVASION: str = 'GameEventGoldenDragonInvasion'
GAME_EVENT_DEMON_INVASION: str = 'GameEventDemonInvasion'
GAME_EVENT_SKELETON_KING_INVASION: str = 'GameEventSkeletonKingInvasion'
GAME_EVENT_MOSS_MERCHANT: str = 'GameEventMossMerchant'
GAME_EVENT_MEGA_DROP: str = 'GameEventMegaDrop'
GAME_EVENT_LOREN_TREASURE: str = 'GameEventLorenTreasure'
GAME_EVENT_CHAOS_INVASION: str = 'GameEventChaosInvasion'
GAME_EVENT_DUNGEON_ZOMBIE: str = 'GameEventDungeonZombie'
GAME_EVENT_LOST_TOWER_SURVIVAL: str = 'GameEventLostTowerSurvival'

# event participation statuses
EVENT_PARTICIPATION_WAITING_STATUS: str = 'EventParticipationWaiting'
EVENT_PARTICIPATION_STARTED_STATUS: str = 'EventParticipationStarted'
EVENT_PARTICIPATION_ENDED_STATUS: str = 'EventParticipationEnded'

NOTIFICATION_IGNORE_PATTERNS: list[str] = [
    r'^\+\d+\s+EXPERIENCE$'  # exp notification
]
