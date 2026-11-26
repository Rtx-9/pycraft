#!/usr/bin/env python3
"""
PyCraft 2.0 - a Minecraft-style voxel sandbox written in Python.
Requirements:  pip install panda3d numpy
Run:           python pycraft.py

Controls: WASD move, Space jump (double-tap in creative = fly), Shift sneak,
Ctrl sprint, Mouse look, LMB break/attack, RMB place/use/eat/open, MMB pick block,
1-9 / wheel hotbar, E inventory, Q drop, G toggle Survival/Creative,
F toggle flight (creative), F1 hide HUD, F2 screenshot, F3 debug, F11 fullscreen,
Esc pause.
"""
import sys, os, math, random, json, pickle, zlib, wave, heapq, time, threading, gc
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from panda3d.core import loadPrcFileData
loadPrcFileData('', 'window-title PyCraft\nwin-size 1280 720\nsync-video true\n'
                    'textures-power-2 none\nframebuffer-multisample 0\n')
if '--server' in sys.argv:                       # dedicated server: never open a window or an audio device
    loadPrcFileData('', 'window-type none\naudio-library-name null\n')
from panda3d.core import (Geom, GeomNode, GeomTriangles, GeomPoints, GeomVertexData, GeomVertexFormat,
                          GeomVertexArrayFormat, InternalName, Texture, SamplerState, NodePath,
                          TransparencyAttrib, Fog, WindowProperties, KeyboardButton, MouseButton,
                          LineSegs, CardMaker, TextNode, Filename, TextureStage, ModifierButtons,
                          ClockObject, Shader, Camera, PerspectiveLens, Vec3, Vec2, ColorBlendAttrib, AudioSound)
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectSlider, DirectEntry, DGG
from direct.gui.OnscreenText import OnscreenText

DATA_DIR = os.path.join(os.path.expanduser('~'), '.pycraft')
os.makedirs(DATA_DIR, exist_ok=True)
SAVE_PATH = os.path.join(DATA_DIR, 'world.sav')
SETTINGS_PATH = os.path.join(DATA_DIR, 'settings.json')

CS, H, SEA = 16, 96, 40          # chunk size, world height, sea level (z is up)
DAY_LEN = 600.0                  # seconds per full day
REACH = 5.0

# ------------------------------------------------------------------ blocks
AIR = 0
(GRASS, DIRT, STONE, COBBLE, SAND, GRAVEL, LOG, LEAVES, PLANKS, GLASS, WATER, BEDROCK, COAL_ORE,
 IRON_ORE, GOLD_ORE, DIAMOND_ORE, SNOWY_GRASS, CACTUS, BRICKS, TNT, OBSIDIAN, GLOWSTONE, CRAFTING,
 BOOKSHELF, WOOL_WHITE, WOOL_RED, WOOL_BLUE, WOOL_YELLOW, WOOL_GREEN, WOOL_BLACK, BIRCH_LOG,
 BIRCH_LEAVES, SANDSTONE, MOSSY, LAVA, ICE, CLAY, PUMPKIN, MELON, SNOW, STONE_BRICKS, TALL_GRASS,
 FLOWER_RED, FLOWER_YELLOW, DEAD_BUSH, GOLD_BLOCK, IRON_BLOCK, DIAMOND_BLOCK, AUTUMN_LEAVES) = range(1, 50)
WATER_FLOW, LAVA_FLOW = 50, 57    # 50..56 = water levels 1..7, 57..59 = lava levels 1..3
(TORCH, WALL_TORCH, LANTERN, JACK_O_LANTERN, SEA_LANTERN, MAGMA, GLOWSHROOM, CRYSTAL, CHEST, SPAWNER,
 BED, COBWEB, SLIME, SPRUCE_LOG, SPRUCE_LEAVES, SPRUCE_PLANKS, BIRCH_PLANKS, GRANITE, DIORITE, ANDESITE,
 DEEPSLATE, MOSSY_STONE_BRICKS, CRACKED_STONE_BRICKS, EMERALD_ORE, RED_SAND, TERRACOTTA, TERRACOTTA_RED,
 TERRACOTTA_YELLOW, RED_MUSHROOM, BROWN_MUSHROOM, FERN, SUGAR_CANE, BLUE_ORCHID, SAPLING, FARMLAND,
 WHEAT1, WHEAT2, WHEAT3) = range(60, 98)
BED_HEAD, SNOW_LAYER = 98, 99

# id: (name, tiles (str or (top, side, bottom)), hardness, tool, pickaxe tier needed)
BDEF = {
    GRASS: ('Grass Block', ('grass_top', 'grass_side', 'dirt'), .6, 'shovel', 0),
    DIRT: ('Dirt', 'dirt', .5, 'shovel', 0),
    STONE: ('Stone', 'stone', 1.5, 'pickaxe', 1),
    COBBLE: ('Cobblestone', 'cobble', 2, 'pickaxe', 1),
    SAND: ('Sand', 'sand', .5, 'shovel', 0),
    GRAVEL: ('Gravel', 'gravel', .6, 'shovel', 0),
    LOG: ('Oak Log', ('log_top', 'log_side', 'log_top'), 2, 'axe', 0),
    LEAVES: ('Oak Leaves', 'leaves', .2, None, 0),
    PLANKS: ('Oak Planks', 'planks', 2, 'axe', 0),
    GLASS: ('Glass', 'glass', .3, None, 0),
    WATER: ('Water', 'water', -1, None, 0),
    BEDROCK: ('Bedrock', 'bedrock', -1, None, 0),
    COAL_ORE: ('Coal Ore', 'coal_ore', 3, 'pickaxe', 1),
    IRON_ORE: ('Iron Ore', 'iron_ore', 3, 'pickaxe', 2),
    GOLD_ORE: ('Gold Ore', 'gold_ore', 3, 'pickaxe', 3),
    DIAMOND_ORE: ('Diamond Ore', 'diamond_ore', 3, 'pickaxe', 3),
    SNOWY_GRASS: ('Snowy Grass', ('snow', 'snow_side', 'dirt'), .6, 'shovel', 0),
    CACTUS: ('Cactus', ('cactus_top', 'cactus_side', 'cactus_top'), .4, None, 0),
    BRICKS: ('Bricks', 'bricks', 2, 'pickaxe', 1),
    TNT: ('TNT', ('tnt_top', 'tnt_side', 'tnt_bottom'), 0, None, 0),
    OBSIDIAN: ('Obsidian', 'obsidian', 15, 'pickaxe', 4),
    GLOWSTONE: ('Glowstone', 'glowstone', .3, None, 0),
    CRAFTING: ('Crafting Table', ('craft_top', 'craft_side', 'planks'), 2.5, 'axe', 0),
    BOOKSHELF: ('Bookshelf', ('planks', 'bookshelf', 'planks'), 1.5, 'axe', 0),
    WOOL_WHITE: ('White Wool', 'wool_white', .8, None, 0),
    WOOL_RED: ('Red Wool', 'wool_red', .8, None, 0),
    WOOL_BLUE: ('Blue Wool', 'wool_blue', .8, None, 0),
    WOOL_YELLOW: ('Yellow Wool', 'wool_yellow', .8, None, 0),
    WOOL_GREEN: ('Green Wool', 'wool_green', .8, None, 0),
    WOOL_BLACK: ('Black Wool', 'wool_black', .8, None, 0),
    BIRCH_LOG: ('Birch Log', ('birch_top', 'birch_side', 'birch_top'), 2, 'axe', 0),
    BIRCH_LEAVES: ('Birch Leaves', 'birch_leaves', .2, None, 0),
    SANDSTONE: ('Sandstone', ('sandstone_top', 'sandstone_side', 'sandstone_top'), .8, 'pickaxe', 1),
    MOSSY: ('Mossy Cobblestone', 'mossy', 2, 'pickaxe', 1),
    LAVA: ('Lava', 'lava', -1, None, 0),
    ICE: ('Ice', 'ice', .5, 'pickaxe', 0),
    CLAY: ('Clay', 'clay', .6, 'shovel', 0),
    PUMPKIN: ('Pumpkin', ('pumpkin_top', 'pumpkin_side', 'pumpkin_top'), 1, 'axe', 0),
    MELON: ('Melon', ('melon_top', 'melon_side', 'melon_top'), 1, 'axe', 0),
    SNOW: ('Snow Block', 'snow', .2, 'shovel', 0),
    STONE_BRICKS: ('Stone Bricks', 'stone_bricks', 1.5, 'pickaxe', 1),
    TALL_GRASS: ('Tall Grass', 'tall_grass', 0, None, 0),
    FLOWER_RED: ('Poppy', 'flower_red', 0, None, 0),
    FLOWER_YELLOW: ('Dandelion', 'flower_yellow', 0, None, 0),
    DEAD_BUSH: ('Dead Bush', 'dead_bush', 0, None, 0),
    GOLD_BLOCK: ('Block of Gold', 'gold_block', 3, 'pickaxe', 3),
    IRON_BLOCK: ('Block of Iron', 'iron_block', 5, 'pickaxe', 2),
    DIAMOND_BLOCK: ('Block of Diamond', 'diamond_block', 5, 'pickaxe', 3),
    AUTUMN_LEAVES: ('Autumn Leaves', 'autumn_leaves', .2, None, 0),
    TORCH: ('Torch', ('torch_top', 'torch', 'torch_top'), 0, None, 0),
    WALL_TORCH: ('Torch', ('torch_top', 'torch', 'torch_top'), 0, None, 0),
    LANTERN: ('Lantern', ('lantern_top', 'lantern', 'lantern_top'), .5, 'pickaxe', 0),
    JACK_O_LANTERN: ("Jack o'Lantern", ('pumpkin_top', 'jack_face', 'pumpkin_top'), 1, 'axe', 0),
    SEA_LANTERN: ('Sea Lantern', 'sea_lantern', .3, None, 0),
    MAGMA: ('Magma Block', 'magma', .5, 'pickaxe', 1),
    GLOWSHROOM: ('Glowshroom', 'glowshroom', 0, None, 0),
    CRYSTAL: ('Glow Crystal', 'crystal', .4, None, 0),
    CHEST: ('Chest', ('chest_top', 'chest_side', 'chest_top'), 2.5, 'axe', 0),
    SPAWNER: ('Monster Spawner', 'spawner', 5, 'pickaxe', 1),
    BED: ('Bed', ('bed_top', 'bed_side', 'planks'), .2, None, 0),
    COBWEB: ('Cobweb', 'cobweb', 4, 'sword', 0),
    SLIME: ('Slime Block', 'slime', 0, None, 0),
    SPRUCE_LOG: ('Spruce Log', ('spruce_top', 'spruce_side', 'spruce_top'), 2, 'axe', 0),
    SPRUCE_LEAVES: ('Spruce Leaves', 'spruce_leaves', .2, None, 0),
    SPRUCE_PLANKS: ('Spruce Planks', 'spruce_planks', 2, 'axe', 0),
    BIRCH_PLANKS: ('Birch Planks', 'birch_planks', 2, 'axe', 0),
    GRANITE: ('Granite', 'granite', 1.5, 'pickaxe', 1),
    DIORITE: ('Diorite', 'diorite', 1.5, 'pickaxe', 1),
    ANDESITE: ('Andesite', 'andesite', 1.5, 'pickaxe', 1),
    DEEPSLATE: ('Deepslate', ('deepslate_top', 'deepslate', 'deepslate_top'), 3, 'pickaxe', 1),
    MOSSY_STONE_BRICKS: ('Mossy Stone Bricks', 'mossy_stone_bricks', 1.5, 'pickaxe', 1),
    CRACKED_STONE_BRICKS: ('Cracked Stone Bricks', 'cracked_stone_bricks', 1.5, 'pickaxe', 1),
    EMERALD_ORE: ('Emerald Ore', 'emerald_ore', 3, 'pickaxe', 3),
    RED_SAND: ('Red Sand', 'red_sand', .5, 'shovel', 0),
    TERRACOTTA: ('Terracotta', 'terracotta', 1.25, 'pickaxe', 1),
    TERRACOTTA_RED: ('Red Terracotta', 'terracotta_red', 1.25, 'pickaxe', 1),
    TERRACOTTA_YELLOW: ('Yellow Terracotta', 'terracotta_yellow', 1.25, 'pickaxe', 1),
    RED_MUSHROOM: ('Red Mushroom', 'red_mushroom', 0, None, 0),
    BROWN_MUSHROOM: ('Brown Mushroom', 'brown_mushroom', 0, None, 0),
    FERN: ('Fern', 'fern', 0, None, 0),
    SUGAR_CANE: ('Sugar Cane', 'sugar_cane', 0, None, 0),
    BLUE_ORCHID: ('Blue Orchid', 'blue_orchid', 0, None, 0),
    SAPLING: ('Sapling', 'sapling', 0, None, 0),
    FARMLAND: ('Farmland', ('farmland', 'dirt', 'dirt'), .6, 'shovel', 0),
    WHEAT1: ('Wheat Crop', 'wheat1', 0, None, 0),
    WHEAT2: ('Wheat Crop', 'wheat2', 0, None, 0),
    WHEAT3: ('Wheat Crop', 'wheat3', 0, None, 0),
    BED_HEAD: ('Bed', ('bed_head_top', 'bed_side', 'planks'), .2, None, 0),
    SNOW_LAYER: ('Snow Layer', 'snow', .1, 'shovel', 0),
}
(PEBBLE, STONE_SLAB, COBBLE_SLAB, PLANK_SLAB, SANDSTONE_SLAB, SILLY_PORTAL, SILLY_GRASS, SILLY_SOIL, SILLY_STONE,
 SILLY_COBBLE, SILLY_LOG, SILLY_LEAVES, SILLY_PLANKS, SHROOM_STEM, SHROOM_CAP, JELLY, SILLY_CRYSTAL, SILLIUM_ORE,
 SILLIUM_BLOCK, SILLY_BRICKS, SILLY_TUFT, GLOWBLOOM) = range(200, 222)
BDEF.update({
    PEBBLE: ('Pebble', 'pebble', 0, None, 0),
    STONE_SLAB: ('Stone Slab', 'stone', 1.5, 'pickaxe', 1),
    COBBLE_SLAB: ('Cobblestone Slab', 'cobble', 2, 'pickaxe', 1),
    PLANK_SLAB: ('Oak Slab', 'planks', 2, 'axe', 0),
    SANDSTONE_SLAB: ('Sandstone Slab', ('sandstone_top', 'sandstone_side', 'sandstone_top'), .8, 'pickaxe', 1),
    SILLY_PORTAL: ('Sillyland Portal', 'silly_portal', -1, None, 0),
    SILLY_GRASS: ('Silly Grass', ('silly_grass_top', 'silly_grass_side', 'silly_soil'), .6, 'shovel', 0),
    SILLY_SOIL: ('Silly Soil', 'silly_soil', .5, 'shovel', 0),
    SILLY_STONE: ('Silly Stone', 'silly_stone', 1.5, 'pickaxe', 1),
    SILLY_COBBLE: ('Silly Cobblestone', 'silly_cobble', 2, 'pickaxe', 1),
    SILLY_LOG: ('Swirlwood Log', ('silly_log_top', 'silly_log_side', 'silly_log_top'), 2, 'axe', 0),
    SILLY_LEAVES: ('Swirlwood Leaves', 'silly_leaves', .2, None, 0),
    SILLY_PLANKS: ('Swirlwood Planks', 'silly_planks', 2, 'axe', 0),
    SHROOM_STEM: ('Giant Mushroom Stem', 'shroom_stem', 1, 'axe', 0),
    SHROOM_CAP: ('Giant Mushroom Cap', 'shroom_cap', .8, 'axe', 0),
    JELLY: ('Jelly Block', 'jelly', 0, None, 0),
    SILLY_CRYSTAL: ('Prism Crystal', 'silly_crystal', .6, 'pickaxe', 0),
    SILLIUM_ORE: ('Sillium Ore', 'sillium_ore', 3, 'pickaxe', 3),
    SILLIUM_BLOCK: ('Block of Sillium', 'sillium_block', 5, 'pickaxe', 3),
    SILLY_BRICKS: ('Silly Bricks', 'silly_bricks', 1.5, 'pickaxe', 1),
    SILLY_TUFT: ('Silly Tuft', 'silly_tuft', 0, None, 0),
    GLOWBLOOM: ('Glowbloom', 'glowbloom', 0, None, 0),
})
(GRASS_SLAB, SAND_SLAB, SILLY_GRASS_SLAB, CHERRY_LOG, CHERRY_LEAVES, PALM_LOG, PALM_LEAVES, BOSS_ALTAR, CALCITE,
 AMETHYST_BLOCK, HAY_BALE, BEEHIVE, DIRT_PATH, CANDY_BLOCK, CLOUD_BLOCK, BELL) = range(222, 238)
BDEF.update({
    GRASS_SLAB: ('Grass Slab', ('grass_top', 'grass_slab_side', 'dirt'), .6, 'shovel', 0),
    SAND_SLAB: ('Sand Slab', 'sand', .5, 'shovel', 0),
    SILLY_GRASS_SLAB: ('Silly Grass Slab', ('silly_grass_top', 'silly_grass_slab_side', 'silly_soil'), .6, 'shovel', 0),
    CHERRY_LOG: ('Cherry Log', ('cherry_top', 'cherry_side', 'cherry_top'), 2, 'axe', 0),
    CHERRY_LEAVES: ('Cherry Blossoms', 'cherry_leaves', .2, None, 0),
    PALM_LOG: ('Palm Log', ('palm_top', 'palm_side', 'palm_top'), 2, 'axe', 0),
    PALM_LEAVES: ('Palm Fronds', 'palm_leaves', .2, None, 0),
    BOSS_ALTAR: ('Jelly Throne Altar', ('altar_top', 'altar_side', 'silly_bricks'), -1, None, 0),
    CALCITE: ('Calcite', 'calcite', .75, 'pickaxe', 1),
    AMETHYST_BLOCK: ('Amethyst Block', 'amethyst', 1.5, 'pickaxe', 1),
    HAY_BALE: ('Hay Bale', ('hay_top', 'hay_side', 'hay_top'), .5, None, 0),
    BEEHIVE: ('Beehive', ('hive_top', 'hive_side', 'hive_top'), .6, 'axe', 0),
    DIRT_PATH: ('Dirt Path', ('path_top', 'dirt', 'dirt'), .6, 'shovel', 0),
    CANDY_BLOCK: ('Candy Block', 'candy', .8, 'pickaxe', 0),
    CLOUD_BLOCK: ('Cloud', 'cloud', .2, None, 0),
    BELL: ('Village Bell', 'bell', 1, 'pickaxe', 0),
})
SLABS = {STONE_SLAB: STONE, COBBLE_SLAB: COBBLE, PLANK_SLAB: PLANKS, SANDSTONE_SLAB: SANDSTONE, GRASS_SLAB: GRASS,
         SAND_SLAB: SAND, SILLY_GRASS_SLAB: SILLY_GRASS}
for _l in range(1, 8):
    BDEF[WATER_FLOW + _l - 1] = ('Water', 'water', -1, None, 0)
for _l in range(1, 4):
    BDEF[LAVA_FLOW + _l - 1] = ('Lava', 'lava', -1, None, 0)

LEAF_IDS = (LEAVES, BIRCH_LEAVES, SPRUCE_LEAVES, AUTUMN_LEAVES, SILLY_LEAVES, CHERRY_LEAVES, PALM_LEAVES)
PLANTS = (TALL_GRASS, FLOWER_RED, FLOWER_YELLOW, DEAD_BUSH, RED_MUSHROOM, BROWN_MUSHROOM, FERN, SUGAR_CANE,
          BLUE_ORCHID, SAPLING, GLOWSHROOM, CRYSTAL, COBWEB, WHEAT1, WHEAT2, WHEAT3, SILLY_TUFT, GLOWBLOOM)
BOXES = {TORCH: (7 / 16, 7 / 16, 0, 9 / 16, 9 / 16, 10 / 16), WALL_TORCH: (7 / 16, 7 / 16, 0, 9 / 16, 9 / 16, 10 / 16),
         LANTERN: (5 / 16, 5 / 16, 0, 11 / 16, 11 / 16, 9 / 16), CHEST: (1 / 16, 1 / 16, 0, 15 / 16, 15 / 16, 14 / 16),
         BED: (0, 0, 0, 1, 1, 9 / 16), BED_HEAD: (0, 0, 0, 1, 1, 9 / 16), SNOW_LAYER: (0, 0, 0, 1, 1, 2 / 16),
         PEBBLE: (.3, .3, 0, .7, .7, .12), BELL: (.3, .3, 0, .7, .7, .62)}
BOXES.update({_s: (0, 0, 0, 1, 1, .5) for _s in SLABS})
GRASSY = (GRASS, DIRT, SNOWY_GRASS)
SUPPORT = {TALL_GRASS: GRASSY, FLOWER_RED: GRASSY, FLOWER_YELLOW: GRASSY, BLUE_ORCHID: GRASSY, FERN: GRASSY,
           SAPLING: GRASSY, DEAD_BUSH: (SAND, RED_SAND, DIRT, GRASS, TERRACOTTA, TERRACOTTA_RED, TERRACOTTA_YELLOW),
           SUGAR_CANE: (SAND, RED_SAND, GRASS, DIRT, SUGAR_CANE), WHEAT1: (FARMLAND,), WHEAT2: (FARMLAND,),
           WHEAT3: (FARMLAND,), SILLY_TUFT: (SILLY_GRASS, SILLY_SOIL), GLOWBLOOM: (SILLY_GRASS, SILLY_SOIL)}
SOLID_SUPPORT = (RED_MUSHROOM, BROWN_MUSHROOM, GLOWSHROOM, CRYSTAL, TORCH, SNOW_LAYER, PEBBLE)

# ------------------------------------------------------------------ items
(STICK, COAL, IRON_INGOT, GOLD_INGOT, DIAMOND, APPLE, PORK, COOKED_PORK, BEEF, STEAK, CHICKEN,
 COOKED_CHICKEN, MUTTON, COOKED_MUTTON, ROTTEN_FLESH, GUNPOWDER, GOLDEN_APPLE) = range(100, 117)
(SEEDS, WHEAT, BREAD, BONE, BONE_MEAL, STRING, FEATHER, ARROW, BOW, HOE, BUCKET, WATER_BUCKET, LAVA_BUCKET,
 EMERALD, RAW_RABBIT, COOKED_RABBIT, VENISON, COOKED_VENISON, RAW_FISH, COOKED_FISH) = range(160, 180)
(SILLIUM_INGOT, SADDLE, PARAGLIDER, GRAPPLE, SLINGSHOT, JELLY_BALL, PRISM_SHARD, SILLY_BERRY, IRON_SPEAR, BATTLE_AXE,
 DAGGER, SILLIUM_SPEAR, SILLIUM_BLADE, ROYAL_SCEPTER, FISHING_ROD, HONEY) = range(180, 196)
WEAPON_TYPES = ('Spear', 'Mace', 'Dagger', 'Battle Axe')
TIER_NAMES_W = ('Wooden', 'Stone', 'Iron', 'Diamond', 'Sillium')
_WBASE = {0: (3., 1.2, .55, 6.5), 1: (5., 1.6, .95, 4.5), 2: (2., .9, .18, 3.5), 3: (6., 1.8, 1.05, 4.5)}
_LEGACY_W = {(2, 0): IRON_SPEAR, (2, 3): BATTLE_AXE, (2, 2): DAGGER, (4, 0): SILLIUM_SPEAR}
WEAPONS, WEAPON_KIND, WEAPON_IDS = {}, {}, []      # id -> (damage, cooldown, reach); id -> (tier, type)
for _t in range(5):
    for _k in range(4):
        _id = _LEGACY_W.get((_t, _k), 280 + _t * 4 + _k)
        _b = _WBASE[_k]
        WEAPONS[_id] = (round(_b[0] + _b[1] * _t, 1), _b[2], _b[3])
        WEAPON_KIND[_id] = (_t, _k)
        WEAPON_IDS.append(_id)
WEAPONS[SILLIUM_BLADE] = (11, .35, 5.)
WEAPONS[ROYAL_SCEPTER] = (7, .4, 5.)
ITEM_NAMES = {STICK: 'Stick', COAL: 'Coal', IRON_INGOT: 'Iron Ingot', GOLD_INGOT: 'Gold Ingot',
              DIAMOND: 'Diamond', APPLE: 'Apple', PORK: 'Raw Porkchop', COOKED_PORK: 'Cooked Porkchop',
              BEEF: 'Raw Beef', STEAK: 'Steak', CHICKEN: 'Raw Chicken', COOKED_CHICKEN: 'Cooked Chicken',
              MUTTON: 'Raw Mutton', COOKED_MUTTON: 'Cooked Mutton', ROTTEN_FLESH: 'Rotten Flesh',
              GUNPOWDER: 'Gunpowder', GOLDEN_APPLE: 'Golden Apple', SEEDS: 'Wheat Seeds', WHEAT: 'Wheat',
              BREAD: 'Bread', BONE: 'Bone', BONE_MEAL: 'Bone Meal', STRING: 'String', FEATHER: 'Feather',
              ARROW: 'Arrow', BOW: 'Bow', HOE: 'Hoe', BUCKET: 'Bucket', WATER_BUCKET: 'Water Bucket',
              LAVA_BUCKET: 'Lava Bucket', EMERALD: 'Emerald', RAW_RABBIT: 'Raw Rabbit',
              COOKED_RABBIT: 'Cooked Rabbit', VENISON: 'Raw Venison', COOKED_VENISON: 'Cooked Venison',
              RAW_FISH: 'Raw Fish', COOKED_FISH: 'Cooked Fish', SILLIUM_INGOT: 'Sillium Ingot', SADDLE: 'Saddle',
              PARAGLIDER: 'Paraglider', GRAPPLE: 'Grappling Hook', SLINGSHOT: 'Slingshot', JELLY_BALL: 'Jelly Ball',
              PRISM_SHARD: 'Prism Shard', SILLY_BERRY: 'Silly Berry', IRON_SPEAR: 'Iron Spear',
              SILLIUM_BLADE: 'Sillium Blade', ROYAL_SCEPTER: 'Royal Scepter', FISHING_ROD: 'Fishing Rod', HONEY: 'Honey'}
ITEM_NAMES.update({_id: '%s %s' % (TIER_NAMES_W[WEAPON_KIND[_id][0]], WEAPON_TYPES[WEAPON_KIND[_id][1]])
                   for _id in WEAPON_IDS})
# food: (hunger restored, health healed)
FOOD = {APPLE: (4, 3), PORK: (3, 3), COOKED_PORK: (8, 8), BEEF: (3, 3), STEAK: (8, 8),
        CHICKEN: (2, 2), COOKED_CHICKEN: (6, 6), MUTTON: (2, 2), COOKED_MUTTON: (6, 6),
        ROTTEN_FLESH: (4, 1), GOLDEN_APPLE: (6, 20), BREAD: (5, 5), RAW_RABBIT: (3, 2), COOKED_RABBIT: (5, 6),
        VENISON: (3, 3), COOKED_VENISON: (8, 9), RAW_FISH: (2, 2), COOKED_FISH: (5, 6), SILLY_BERRY: (4, 3),
        HONEY: (6, 5)}
TOOL_TYPES = ('pickaxe', 'axe', 'shovel', 'sword')
TIER_NAMES = ('Wooden', 'Stone', 'Iron', 'Diamond', 'Sillium')
TOOLS = {}                                   # id -> (type, tier 1..4)
for _t in range(5):
    for _k, _ty in enumerate(TOOL_TYPES):
        TOOLS[120 + _t * 4 + _k] = (_ty, _t + 1)
        ITEM_NAMES[120 + _t * 4 + _k] = '%s %s' % (TIER_NAMES[_t], _ty.capitalize())
MOB_KINDS = ('pig', 'cow', 'sheep', 'chicken', 'zombie', 'creeper', 'rabbit', 'fox', 'deer', 'goat',
             'penguin', 'duck', 'fish', 'skeleton', 'spider', 'bird', 'butterfly', 'frog', 'horse', 'wolf', 'gloop',
             'floatie', 'imp', 'hopper', 'turtle', 'bear', 'villager', 'bee', 'ant', 'dragonfly', 'mummy', 'yeti',
             'ghost', 'silly_king')
EGG0 = 140
EGG_IDS = [EGG0 + _i if _i < 20 else 240 + _i for _i in range(len(MOB_KINDS))]   # 140..159, then 260+
EGG_MOB = {e: MOB_KINDS[_i] for _i, e in enumerate(EGG_IDS)}
for _i, _m in enumerate(MOB_KINDS):
    ITEM_NAMES[EGG_IDS[_i]] = '%s Spawn Egg' % _m.capitalize()


def isblk(i):
    """Block ids live in 0..99 and 200..255; everything else is an item."""
    return isinstance(i, int) and (i < 100 or 200 <= i < 256)
EMITTING_ITEMS = (TORCH, LANTERN, GLOWSTONE, JACK_O_LANTERN, SEA_LANTERN, GLOWSHROOM, CRYSTAL, LAVA_BUCKET, MAGMA)

DROP = {GRASS: DIRT, SNOWY_GRASS: DIRT, STONE: COBBLE, COAL_ORE: COAL, IRON_ORE: IRON_INGOT,
        GOLD_ORE: GOLD_INGOT, DIAMOND_ORE: DIAMOND, EMERALD_ORE: EMERALD, WALL_TORCH: TORCH, FARMLAND: DIRT,
        SILLY_GRASS: SILLY_SOIL, SILLY_STONE: SILLY_COBBLE, BEEHIVE: HONEY, SILLIUM_ORE: SILLIUM_INGOT, SILLY_CRYSTAL: PRISM_SHARD,
        COBWEB: STRING, WHEAT1: SEEDS, WHEAT2: SEEDS, BED_HEAD: BED}


def item_name(i):
    if isinstance(i, tuple):
        return 'Planks' if i == WOODS else item_name(i[0])
    return BDEF[i][0] if isblk(i) else ITEM_NAMES.get(i, '?')


def max_stack(i):
    return 1 if (i in TOOLS or i in WEAPONS or i in (BOW, HOE, WATER_BUCKET, LAVA_BUCKET, SADDLE, PARAGLIDER, GRAPPLE,
                                                     SLINGSHOT, ROYAL_SCEPTER, FISHING_ROD)) else (16 if i == BUCKET else 64)


def tool_id(tier, typ):
    return 120 + tier * 4 + typ


CREATIVE_ITEMS = [b for b in sorted(BDEF) if not 50 <= b < 60 and b not in (WALL_TORCH, WHEAT1, WHEAT2, WHEAT3, BED_HEAD,
                                                                              SILLY_PORTAL, BOSS_ALTAR)] + \
    list(range(100, 117)) + [i for i in range(160, 196) if i not in WEAPON_KIND] + sorted(TOOLS) + WEAPON_IDS + EGG_IDS

WOODS = (PLANKS, SPRUCE_PLANKS, BIRCH_PLANKS, SILLY_PLANKS)
# (result, count), ingredients [(item or group, n)], needs crafting table nearby
RECIPES = [((PLANKS, 4), [(LOG, 1)], 0), ((BIRCH_PLANKS, 4), [(BIRCH_LOG, 1)], 0),
           ((SPRUCE_PLANKS, 4), [(SPRUCE_LOG, 1)], 0), ((STICK, 4), [(WOODS, 2)], 0),
           ((CRAFTING, 1), [(WOODS, 4)], 0), ((TORCH, 4), [(COAL, 1), (STICK, 1)], 0),
           ((BREAD, 1), [(WHEAT, 3)], 0), ((BONE_MEAL, 3), [(BONE, 1)], 0), ((WOOL_WHITE, 1), [(STRING, 4)], 0),
           ((SANDSTONE, 1), [(SAND, 4)], 0), ((JACK_O_LANTERN, 1), [(PUMPKIN, 1), (TORCH, 1)], 0)]
for _raw, _ck in ((PORK, COOKED_PORK), (BEEF, STEAK), (CHICKEN, COOKED_CHICKEN), (MUTTON, COOKED_MUTTON),
                  (RAW_RABBIT, COOKED_RABBIT), (VENISON, COOKED_VENISON), (RAW_FISH, COOKED_FISH)):
    RECIPES.append(((_ck, 1), [(_raw, 1), (WOODS, 1)], 0))
for _dye, _wool in ((FLOWER_RED, WOOL_RED), (FLOWER_YELLOW, WOOL_YELLOW), (BLUE_ORCHID, WOOL_BLUE),
                    (CACTUS, WOOL_GREEN), (COAL, WOOL_BLACK)):
    RECIPES.append(((_wool, 1), [(WOOL_WHITE, 1), (_dye, 1)], 0))
for _t, _mat in enumerate((WOODS, COBBLE, IRON_INGOT, DIAMOND, SILLIUM_INGOT)):
    for _k, _n, _s in ((0, 1, 3), (1, 3, 1), (2, 1, 1), (3, 4, 2)):
        RECIPES.append(((_LEGACY_W.get((_t, _k), 280 + _t * 4 + _k), 1), [(_mat, _n), (STICK, _s)], 1))
    RECIPES += [((tool_id(_t, 0), 1), [(_mat, 3), (STICK, 2)], 1), ((tool_id(_t, 1), 1), [(_mat, 3), (STICK, 2)], 1),
                ((tool_id(_t, 2), 1), [(_mat, 1), (STICK, 2)], 1), ((tool_id(_t, 3), 1), [(_mat, 2), (STICK, 1)], 1)]
RECIPES += [((CHEST, 1), [(WOODS, 8)], 1), ((BED, 1), [(WOOL_WHITE, 3), (WOODS, 3)], 1),
            ((LANTERN, 1), [(IRON_INGOT, 2), (TORCH, 1)], 1), ((BUCKET, 1), [(IRON_INGOT, 3)], 1),
            ((BOW, 1), [(STICK, 3), (STRING, 3)], 1), ((ARROW, 4), [(STICK, 1), (FEATHER, 1), (GRAVEL, 1)], 1),
            ((HOE, 1), [(STICK, 2), (COBBLE, 2)], 1), ((GLASS, 4), [(SAND, 4), (COAL, 1)], 1),
            ((STONE, 8), [(COBBLE, 8), (COAL, 1)], 1), ((STONE_BRICKS, 4), [(STONE, 4)], 1),
            ((MOSSY_STONE_BRICKS, 1), [(STONE_BRICKS, 1), (LEAVES, 1)], 1),
            ((CRACKED_STONE_BRICKS, 1), [(STONE_BRICKS, 1), (COAL, 1)], 1),
            ((BRICKS, 4), [(CLAY, 4), (COAL, 1)], 1), ((TNT, 1), [(GUNPOWDER, 5), (SAND, 4)], 1),
            ((BOOKSHELF, 1), [(WOODS, 6)], 1), ((GOLDEN_APPLE, 1), [(APPLE, 1), (GOLD_INGOT, 8)], 1),
            ((SEA_LANTERN, 1), [(GLASS, 4), (CRYSTAL, 1)], 1), ((GLOWSTONE, 1), [(CRYSTAL, 4)], 1),
            ((SLIME, 1), [(WOOL_GREEN, 1), (STRING, 2)], 1),
            ((IRON_BLOCK, 1), [(IRON_INGOT, 9)], 1), ((GOLD_BLOCK, 1), [(GOLD_INGOT, 9)], 1),
            ((DIAMOND_BLOCK, 1), [(DIAMOND, 9)], 1),
            ((SILLY_PLANKS, 4), [(SILLY_LOG, 1)], 0), ((JELLY, 1), [(JELLY_BALL, 4)], 0),
            ((STONE_SLAB, 6), [(STONE, 3)], 1), ((COBBLE_SLAB, 6), [(COBBLE, 3)], 1), ((PLANK_SLAB, 6), [(WOODS, 3)], 1),
            ((SANDSTONE_SLAB, 6), [(SANDSTONE, 3)], 1), ((SADDLE, 1), [(WOOL_RED, 3), (IRON_INGOT, 1)], 1),
            ((PARAGLIDER, 1), [(STICK, 3), (WOOL_WHITE, 4), (FEATHER, 2)], 1),
            ((GRAPPLE, 1), [(IRON_INGOT, 3), (STRING, 4)], 1), ((SLINGSHOT, 1), [(STICK, 2), (STRING, 2)], 0),
            ((FISHING_ROD, 1), [(STICK, 3), (STRING, 2)], 0), ((HAY_BALE, 1), [(WHEAT, 9)], 0),
            ((DIRT_PATH, 4), [(DIRT, 4)], 0), ((CANDY_BLOCK, 4), [(SILLY_BERRY, 2), (JELLY_BALL, 2)], 1),
            ((SILLIUM_BLADE, 1), [(SILLIUM_INGOT, 3), (PRISM_SHARD, 2), (STICK, 1)], 1),
            ((SILLY_BRICKS, 4), [(SILLY_STONE, 4)], 1), ((SILLIUM_BLOCK, 1), [(SILLIUM_INGOT, 9)], 1),
            ((SILLY_CRYSTAL, 1), [(PRISM_SHARD, 4)], 1)]


# ------------------------------------------------------------------ lookup tables
def _mask(ids):
    m = np.zeros(256, bool)
    m[list(ids)] = True
    return m


DEFINED = _mask(BDEF)
PLANT, BOX = _mask(PLANTS), _mask(BOXES)
FLUID = _mask([WATER, LAVA] + list(range(50, 60)))
CUBE = DEFINED & ~PLANT & ~BOX
SOLID = (CUBE & ~FLUID & ~_mask([SILLY_PORTAL])) | _mask([CHEST, BED, BED_HEAD] + list(SLABS))
OPAQUE = CUBE & ~FLUID & ~_mask((GLASS, SPAWNER, SLIME, SILLY_PORTAL, JELLY) + LEAF_IDS)    # hides faces + blocks light
LIGHTB = OPAQUE.copy()
HIDES = OPAQUE.copy()                                                  # leaves added in 'fast leaves' mode
AO_OCC = CUBE & ~FLUID & ~_mask([SILLY_PORTAL])
TARGET = (CUBE | PLANT | BOX) & ~FLUID & ~_mask([SILLY_PORTAL])
REPL = _mask([AIR, TALL_GRASS, FERN, DEAD_BUSH, SNOW_LAYER, SILLY_TUFT]) | FLUID
FLOWINTO = _mask([AIR, TORCH, WALL_TORCH, SNOW_LAYER, PEBBLE]) | PLANT
BLAST = TARGET & ~_mask([BEDROCK, OBSIDIAN])
PORTAL_M = _mask([SILLY_PORTAL])
SKYB = OPAQUE | FLUID | _mask(LEAF_IDS)
COST = np.ones(256, np.int16)
COST[FLUID], COST[list(LEAF_IDS)], COST[OPAQUE] = 2, 2, 16
EMIT = np.zeros(256, np.int16)
for _b, _e in ((GLOWSTONE, 15), (TORCH, 14), (WALL_TORCH, 14), (LANTERN, 15), (JACK_O_LANTERN, 15),
               (SEA_LANTERN, 15), (MAGMA, 6), (GLOWSHROOM, 10), (CRYSTAL, 11), (SILLY_PORTAL, 11), (SILLY_CRYSTAL, 12),
               (GLOWBLOOM, 9), (SHROOM_CAP, 7), (JELLY, 5), (SILLIUM_BLOCK, 8), (BOSS_ALTAR, 13), (AMETHYST_BLOCK, 4)):
    EMIT[_b] = _e
FAMILY = np.arange(256, dtype=np.int32)
FAMILY[50:57] = WATER
FAMILY[57:60] = LAVA
EMIT[FAMILY == LAVA] = 15
LEVEL = np.zeros(256, np.int32)
LEVEL[WATER], LEVEL[LAVA] = 8, 4
LEVEL[50:57] = np.arange(1, 8)
LEVEL[57:60] = np.arange(1, 4)
FHEIGHT = np.zeros(256, np.float32)          # fluid surface height inside its cell
FHEIGHT[FAMILY == WATER] = LEVEL[FAMILY == WATER] / 9.
FHEIGHT[FAMILY == LAVA] = LEVEL[FAMILY == LAVA] / 4.5
# render groups: 0 opaque, 1 cutout, 2 water, 3 lava, 4 two-sided cross plants
GROUP = np.zeros(256, np.int32)
GROUP[list((GLASS, SPAWNER, TORCH, WALL_TORCH, LANTERN, SILLY_PORTAL) + LEAF_IDS)] = 1
GROUP[FAMILY == WATER] = 2
GROUP[FAMILY == LAVA] = 3
GROUP[PLANT] = 4
SWAY = _mask(LEAF_IDS + (SILLY_TUFT, GLOWBLOOM, TALL_GRASS, FLOWER_RED, FLOWER_YELLOW, FERN, BLUE_ORCHID, SAPLING, WHEAT1, WHEAT2,
                         WHEAT3, SUGAR_CANE, DEAD_BUSH))
TICKY = _mask([WHEAT1, WHEAT2, SAPLING, SUGAR_CANE])
FLUIDS = {WATER: (WATER, [None] + list(range(50, 57)), 8, 5), LAVA: (LAVA, [None, 57, 58, 59], 4, 30)}
DELAY = np.ones(256, np.int32)
DELAY[FAMILY == WATER], DELAY[FAMILY == LAVA] = 5, 30
HARD = np.full(256, -1.0)
for _b, _d in BDEF.items():
    HARD[_b] = _d[2]


def supported(b, below):
    if b in SUPPORT:
        return below in SUPPORT[b]
    if b in SOLID_SUPPORT:
        return bool(OPAQUE[below])
    return True


def item_cat(i):
    """Creative inventory tab of an item."""
    if i in EGG_MOB:
        return 'Mobs'
    if i in TOOLS or i in WEAPONS or i in (BOW, ARROW, HOE, BUCKET, WATER_BUCKET, LAVA_BUCKET, SADDLE, PARAGLIDER, GRAPPLE,
                                           SLINGSHOT, FISHING_ROD):
        return 'Tools'
    if i in FOOD:
        return 'Food'
    if not isblk(i):
        return 'Items'
    if 206 <= i <= 221 and i not in (SILLY_PLANKS, SILLY_BRICKS, SILLIUM_BLOCK):
        return 'Nature'
    if PLANT[i] or i in LEAF_IDS or i in (LOG, BIRCH_LOG, SPRUCE_LOG, GRASS, DIRT, SAND, RED_SAND, GRAVEL, CLAY, SNOW,
                                          ICE, CACTUS, PUMPKIN, MELON, SNOWY_GRASS, WATER, LAVA, FARMLAND, SNOW_LAYER,
                                          COAL_ORE, IRON_ORE, GOLD_ORE, DIAMOND_ORE, EMERALD_ORE, STONE, DEEPSLATE,
                                          GRANITE, DIORITE, ANDESITE, BEDROCK, OBSIDIAN, MAGMA):
        return 'Nature'
    if EMIT[i] or i in (CHEST, BED, CRAFTING, BOOKSHELF, TNT, SPAWNER, COBWEB, SLIME, GLASS):
        return 'Deco'
    return 'Building'


CRE_TABS = ('All', 'Building', 'Nature', 'Deco', 'Tools', 'Food', 'Items', 'Mobs')

# ====================================================================== textures
YY, XX = np.mgrid[0:16, 0:16]


def _n(r, col, var, a=255.0):
    t = np.zeros((16, 16, 4), np.float32)
    t[..., :3] = np.array(col, np.float32) + r.uniform(-var, var, (16, 16, 1))
    t[..., 3] = a
    return t


def _blank():
    return np.zeros((16, 16, 4), np.float32)


def _vor(r, n):
    pts = r.uniform(0, 16, (n, 2))
    d = np.sqrt((YY[..., None] + .5 - pts[:, 0]) ** 2 + (XX[..., None] + .5 - pts[:, 1]) ** 2)
    s = np.sort(d, 2)
    return np.argmin(d, 2), (s[..., 1] - s[..., 0]) < 1.0


def _px(t, x, y, c):
    if 0 <= x < 16 and 0 <= y < 16:
        t[y, x, :3] = c
        t[y, x, 3] = 255


def _line(t, x0, y0, x1, y1, c, w=1):
    n = int(max(abs(x1 - x0), abs(y1 - y0))) * 2 + 1
    for i in range(n + 1):
        f = i / n
        x, y = int(round(x0 + (x1 - x0) * f)), int(round(y0 + (y1 - y0) * f))
        for ox in range(w):
            for oy in range(w):
                _px(t, x + ox, y + oy, c)


def _ell(t, cx, cy, rx, ry, c, r=None, var=0):
    m = ((XX + .5 - cx) / rx) ** 2 + ((YY + .5 - cy) / ry) ** 2 <= 1
    t[m, :3] = np.array(c, np.float32) + (r.uniform(-var, var, (m.sum(), 1)) if r is not None else 0)
    t[m, 3] = 255
    return m


def _outline(t, col=None):
    """Emboss shading + outline in a darkened version of the neighbouring colours."""
    a = t[..., 3] > 0
    p = np.pad(a, 1)
    up, dn, lf, rt = p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]
    tl, br = ~up | ~lf, ~dn | ~rt
    hi, sh = a & tl & ~br, a & br & ~tl
    t[hi, :3] = t[hi, :3] * 1.15 + 22
    t[sh, :3] *= .7
    nb = ~a & (up | dn | lf | rt)
    tp = np.pad(t, ((1, 1), (1, 1), (0, 0)))
    acc, cnt = np.zeros((16, 16, 3), np.float32), np.zeros((16, 16, 1), np.float32)
    for sl in (tp[:-2, 1:-1], tp[2:, 1:-1], tp[1:-1, :-2], tp[1:-1, 2:]):
        m = sl[..., 3:4] > 0
        acc += sl[..., :3] * m
        cnt += m
    oc = acc / np.maximum(cnt, 1) * .3
    t[nb, :3] = oc[nb] if col is None else col
    t[nb, 3] = 255
    return t


def _stone(r):
    t = _n(r, (125, 125, 125), 12)
    t[r.rand(16, 16) < .15, :3] -= 20
    return t


def _dirt(r):
    t = _n(r, (134, 96, 67), 14)
    t[r.rand(16, 16) < .1, :3] *= .75
    return t


def _topped(r, col, var):
    t = _dirt(r)
    g = _n(r, col, var)
    for x in range(16):
        d = 3 + r.randint(0, 3)
        t[:d, x] = g[:d, x]
    return t


def _cobble(r, moss=False):
    cell, edge = _vor(r, 10)
    t = _n(r, (0, 0, 0), 8)
    t[..., :3] += r.uniform(95, 150, 10)[cell][..., None]
    t[edge, :3] = 62
    if moss:
        m = (r.rand(10) < .45)[cell] & ~edge
        t[m, :3] = np.array((70, 115, 50), np.float32) + r.uniform(-15, 15, (m.sum(), 1))
    return t


def _planks(r, col=(162, 130, 78)):
    t = _n(r, col, 7)
    t[..., :3] *= (1 + .06 * np.sin(XX * 1.3 + YY * .2))[..., None]
    for row in (3, 7, 11, 15):
        t[row, :, :3] *= .7
    for b in range(4):
        t[b * 4:b * 4 + 3, r.randint(0, 16), :3] *= .75
    return t


def _log_side(r, col=(104, 82, 50)):
    t = _n(r, col, 6)
    t[..., :3] *= r.uniform(.8, 1.1, (1, 16, 1))
    return t


def _log_top(r, ring=(176, 142, 90), bark=(104, 82, 50)):
    d = np.maximum(abs(XX - 7.5), abs(YY - 7.5))
    t = _n(r, ring, 6)
    t[d.astype(int) % 2 == 0, :3] *= .86
    m = d > 6.5
    t[m, :3] = np.array(bark, np.float32) + r.uniform(-8, 8, (m.sum(), 1))
    return t


def _leaves(col, holes=True):
    def f(r):
        t = _n(r, col, 25)
        t[r.rand(16, 16) < .25, :3] *= .55
        h = r.rand(16, 16) < .2
        if holes:
            t[h, 3] = 0
        else:
            t[h, :3] *= .45
        return t
    return f


def _glass(r):
    t = _blank()
    t[0, :] = t[15, :] = t[:, 0] = t[:, 15] = (205, 230, 240, 255)
    for i in range(4):
        t[3 + i, 4 + i] = t[4 + i, 4 + i] = (255, 255, 255, 210)
    return t


def _ore(col):
    def f(r):
        t = _stone(r)
        for _ in range(5):
            x, y = r.randint(1, 13), r.randint(1, 13)
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 1)):
                if r.rand() < .85:
                    t[y + dy, x + dx, :3] = np.array(col) * r.uniform(.8, 1.1)
        return t
    return f


def _bricks(r):
    t = _n(r, (150, 72, 58), 12)
    for row in range(16):
        if row % 4 == 3:
            t[row, :, :3] = (185, 178, 168)
        else:
            t[row, 7 if (row // 4) % 2 else 15, :3] = (185, 178, 168)
    return t


def _tnt_side(r):
    t = _n(r, (205, 45, 35), 10)
    t[4:11, :, :3] = (235, 235, 225)
    L = {'T': ('###', '.#.', '.#.', '.#.', '.#.'), 'N': ('#.#', '###', '###', '###', '#.#')}
    for ch, x0 in (('T', 2), ('N', 7), ('T', 11)):
        for dy, row in enumerate(L[ch]):
            for dx, c in enumerate(row):
                if c == '#':
                    t[5 + dy, x0 + dx, :3] = 30
    return t


def _tnt_top(r):
    t = _n(r, (205, 45, 35), 10)
    t[6:10, 6:10, :3] = 55
    return t


def _glowstone(r):
    cell, edge = _vor(r, 9)
    t = _n(r, (250, 205, 110), 15)
    t[..., :3] *= r.uniform(.75, 1.05, 9)[cell][..., None]
    t[edge, :3] = (150, 105, 50)
    return t


def _craft_top(r):
    t = _planks(r)
    t[[1, 14], 1:15, :3] = (90, 65, 35)
    t[1:15, [1, 14], :3] = (90, 65, 35)
    t[7:9, 2:14, :3] *= .7
    t[2:14, 7:9, :3] *= .7
    return t


def _craft_side(r):
    t = _planks(r)
    t[:3, :, :3] = (110, 80, 45)
    t[5:12, 3, :3] = 120
    t[5:7, 2:5, :3] = 120
    t[6:13, 11, :3] = (90, 60, 30)
    t[5:7, 9:14, :3] = 140
    return t


def _bookshelf(r):
    t = _planks(r)
    cols = np.array([(150, 40, 40), (40, 60, 150), (40, 120, 50), (140, 110, 40), (90, 50, 120)], np.float32)
    for band in (1, 9):
        x = 1
        while x < 15:
            w = r.randint(1, 3)
            t[band + r.randint(0, 2):band + 6, x:min(15, x + w), :3] = cols[r.randint(5)] * r.uniform(.8, 1.1)
            x += w + (r.rand() < .3)
    return t


def _wool(col):
    def f(r):
        t = _n(r, col, 9)
        t[..., :3] *= (1 + .05 * np.sin(XX * 2 + YY * 1.5))[..., None]
        return t
    return f


def _birch_side(r):
    t = _n(r, (216, 214, 205), 6)
    for _ in range(7):
        y, x = r.randint(0, 16), r.randint(0, 13)
        t[y, x:x + r.randint(2, 5), :3] = (40, 40, 35)
    return t


def _sandstone_side(r):
    t = _n(r, (216, 202, 155), 5)
    t[:3, :, :3] *= 1.04
    t[12:, :, :3] *= .9
    t[[4, 9], :, :3] *= .93
    return t


def _ice(r):
    t = _n(r, (150, 185, 250), 6)
    for i in range(16):
        t[i, (i + 3) % 16, :3] = (220, 235, 255)
        t[i, (i + 9) % 16, :3] = (200, 220, 255)
    return t


def _ridged(col, step, k):
    def f(r):
        t = _n(r, col, 10)
        t[:, ::step, :3] *= k
        t[:, 1::step, :3] *= (1 + k) / 2
        return t
    return f


def _capped(col, center):
    def f(r):
        t = _n(r, col, 8)
        d = np.maximum(abs(XX - 7.5), abs(YY - 7.5))
        t[d > 6.5, :3] *= .75
        t[6:10, 6:10, :3] = center
        return t
    return f


def _stone_bricks(r):
    t = _stone(r)
    t[[7, 15], :, :3] = 80
    t[0:7, 7, :3] = 80
    t[8:15, 15, :3] = 80
    t[[0, 8], :, :3] += 20
    return t


def _metal(col):
    def f(r):
        t = _n(r, col, 6)
        t[[0, 15], :, :3] *= .75
        t[:, [0, 15], :3] *= .75
        for i in range(2, 14):
            t[i, 15 - i, :3] *= 1.15
        return t
    return f


def _tall_grass(r):
    t = _blank()
    for x in range(1, 15, 2):
        h, c = r.randint(5, 14), np.array((70, 140, 45)) * r.uniform(.8, 1.2)
        for y in range(16 - h, 16):
            t[y, x + (1 if y < 10 and r.rand() < .3 else 0)] = (*c, 255)
    return t


def _flower(petal):
    def f(r):
        t = _blank()
        t[8:16, 7] = t[11, 8:10] = t[12, 5:7] = (60, 130, 40, 255)
        t[((XX - 7.5) ** 2 + (YY - 5.5) ** 2) <= 9] = (*petal, 255)
        t[5:7, 7:9] = (90, 60, 30, 255)
        return t
    return f


def _dead_bush(r):
    t = _blank()
    for x1, y1 in ((2, 3), (13, 4), (4, 8), (12, 9), (8, 2)):
        _line(t, 8, 15, x1, y1, (125, 85, 45))
    return t


# ---- items
TIER_COL = [(165, 130, 80), (140, 140, 140), (230, 230, 230), (90, 235, 225), (220, 100, 230)]


def _tool(typ, tier):
    def f(r):
        t, c, hd = _blank(), TIER_COL[tier], (115, 85, 45)
        if typ == 3:
            _line(t, 4, 11, 13, 2, c, 2)
            _line(t, 2, 9, 6, 13, (70, 55, 35), 2)
            _line(t, 1, 14, 3, 12, hd, 2)
        else:
            _line(t, 2, 13, 10, 5, hd, 2)
            if typ == 0:
                _line(t, 5, 2, 13, 10, c, 2)
            elif typ == 1:
                t[2:8, 8:13] = (*c, 255)
                t[2, 8] = t[7, 8] = 0
            else:
                _ell(t, 11.5, 4.5, 3.2, 3.2, c)
        return _outline(t)
    return f


def _ingot(c):
    def f(r):
        t = _blank()
        t[6:11, 2:14] = (*c, 255)
        t[6, 3:13, :3] = np.minimum(255, np.array(c) * 1.2)
        t[10, 2:14, :3] = np.array(c) * .7
        return _outline(t)
    return f


def _diamond(r):
    t = _blank()
    m = abs(XX - 7.5) + abs(YY - 7.5) <= 6
    t[m] = (90, 230, 230, 255)
    t[m & (XX < 8) & (YY < 8)] = (190, 255, 250, 255)
    return _outline(t)


def _apple(c):
    def f(r):
        t = _blank()
        _ell(t, 8, 9.5, 5.2, 5, c, r, 12)
        t[7:9, 5:7, :3] = np.minimum(255, np.array(c) + 70)
        _line(t, 8, 2, 8, 4, (90, 60, 30))
        t[3, 9:11] = (60, 150, 40, 255)
        return _outline(t)
    return f


def _meat(c, bone=True, drum=False):
    def f(r):
        t = _blank()
        if drum:
            _ell(t, 6, 10, 4.5, 4, c, r, 10)
            _line(t, 9, 7, 13, 3, (235, 230, 220), 2)
        else:
            _ell(t, 7, 9, 5.5, 4, c, r, 10)
            if bone:
                _line(t, 11, 5, 14, 2, (235, 230, 220))
        return _outline(t)
    return f


def _coal(r):
    t = _blank()
    m = _ell(t, 7.5, 8, 5, 4.5, (40, 40, 40), r, 10)
    t[m & (r.rand(16, 16) < .15), :3] = 90
    return _outline(t)


def _flesh(r):
    t = _blank()
    m = _ell(t, 8, 8, 5.5, 4.5, (125, 140, 70), r, 15)
    t[m & (r.rand(16, 16) < .15), :3] = (80, 60, 40)
    return _outline(t)


def _gunpowder(r):
    t = _blank()
    m = ((XX + .5 - 8) / 5.5) ** 2 + ((YY + .5 - 10) / 3.5) ** 2 <= 1
    m &= r.rand(16, 16) < .7
    t[m] = (90, 90, 90, 255)
    t[m & (r.rand(16, 16) < .4), :3] = 140
    return t


def _egg(a, b):
    def f(r):
        t = _blank()
        m = _ell(t, 8, 8.5, 4.6, 6, a)
        for _ in range(6):
            x, y = r.randint(5, 11), r.randint(4, 13)
            if m[y, x]:
                t[y:y + 2, x:x + 2, :3] = b
        return _outline(t)
    return f


def _crack(stage):
    def f(r):
        rr, t = np.random.RandomState(7), _blank()
        pts = [[8, 8] for _ in range(5)]
        for _ in range(4 + stage * 7):
            for p in pts:
                p[0] = min(15, max(0, p[0] + rr.randint(-1, 2)))
                p[1] = min(15, max(0, p[1] + rr.randint(-1, 2)))
                t[p[1], p[0]] = (20, 20, 20, 235)
        return t
    return f


def _speckle(base, cols, var=8, p=.18):
    def f(r):
        t = _n(r, base, var)
        for c in cols:
            m = r.rand(16, 16) < p
            t[m, :3] = np.array(c, np.float32) + r.uniform(-var, var, (m.sum(), 1))
        return t
    return f


def _autumn(r, holes=True):
    t = _n(r, (215, 110, 35), 18)
    t[r.rand(16, 16) < .3, :3] = (190, 45, 30)
    t[r.rand(16, 16) < .2, :3] = (235, 180, 50)
    t[r.rand(16, 16) < .22, :3] *= .6
    h = r.rand(16, 16) < .2
    if holes:
        t[h, 3] = 0
    else:
        t[h, :3] *= .45
    return t


def _torch(r):
    t = _blank()
    t[8:16, 7:9] = (115, 82, 45, 255)
    t[8:16, 7] = (140, 100, 58, 255)
    t[6, 7:9] = (255, 245, 170, 255)
    t[7, 7:9] = (255, 180, 50, 255)
    return t


def _torch_top(r):
    t = _blank()
    t[7:9, 7:9] = (255, 225, 110, 255)
    return t


def _lantern(r):
    t = _blank()
    t[7:16, 5:11] = (55, 55, 68, 255)
    t[10:15, 6:10] = (255, 195, 85, 255)
    t[11:13, 7:9] = (255, 235, 160, 255)
    t[4:7, 7:9] = (70, 70, 85, 255)
    t[4, 6:10] = (70, 70, 85, 255)
    return t


def _lantern_top(r):
    t = _blank()
    t[5:11, 5:11] = (60, 60, 72, 255)
    t[7:9, 7:9] = (110, 110, 125, 255)
    return t


def _jack_face(r):
    t = _ridged((215, 125, 25), 4, .78)(r)
    glow = (255, 215, 70)
    for y, x0, x1 in ((4, 4, 5), (5, 3, 6), (4, 10, 11), (5, 9, 12)):
        t[y, x0:x1 + 1, :3] = glow
    t[9, 3:13, :3] = glow
    t[10, 4:12, :3] = glow
    t[11, 6:10, :3] = glow
    t[9, [5, 10], :3] = (215, 125, 25)
    return t


def _sea_lantern(r):
    t = _n(r, (190, 220, 215), 6)
    for y0 in (1, 9):
        for x0 in (1, 9):
            t[y0:y0 + 6, x0:x0 + 6, :3] = (230, 248, 240)
            t[y0 + 2:y0 + 4, x0 + 2:x0 + 4, :3] = (255, 255, 255)
    t[[0, 7, 8, 15], :, :3] = (150, 190, 185)
    t[:, [0, 7, 8, 15], :3] = (150, 190, 185)
    return t


def _magma(r):
    cell, edge = _vor(r, 9)
    t = _n(r, (75, 25, 15), 10)
    t[edge, :3] = (255, 120, 30)
    t[edge & (r.rand(16, 16) < .4), :3] = (255, 200, 80)
    return t


def _glowshroom(r):
    t = _blank()
    t[9:16, 7:9] = (175, 215, 225, 255)
    _ell(t, 8, 7.5, 5.5, 3, (50, 210, 230), r, 15)
    for x, y in ((5, 7), (9, 6), (11, 8), (7, 8)):
        t[y, x] = (210, 255, 255, 255)
    return t


def _crystal(r):
    t = _blank()
    for x0, x1, y1, c in ((8, 8, 1, (200, 120, 255)), (8, 4, 5, (170, 90, 240)), (8, 12, 4, (220, 150, 255)),
                          (7, 3, 9, (160, 80, 230)), (9, 13, 9, (190, 110, 250))):
        _line(t, x0, 15, x1, y1, c, 2)
    t[r.rand(16, 16) < .12, :3] += 40
    return t


def _chest_side(r):
    t = _planks(r, (150, 105, 50))
    t[2, :, :3] = t[15, :, :3] = (85, 58, 25)
    t[:, 1, :3] = t[:, 14, :3] = (85, 58, 25)
    t[6, :, :3] = (70, 45, 20)
    t[5:9, 7:9, :3] = (210, 210, 215)
    t[7, 7:9, :3] = (90, 90, 95)
    return t


def _chest_top(r):
    t = _planks(r, (150, 105, 50))
    t[[1, 14], 1:15, :3] = (85, 58, 25)
    t[1:15, [1, 14], :3] = (85, 58, 25)
    return t


def _spawner(r):
    t = _blank()
    for k in (0, 5, 10, 15):
        t[k, :] = (40, 40, 52, 255)
        t[:, k] = (40, 40, 52, 255)
    for k in (5, 10):
        t[k, :, :3] = (70, 70, 88)
    t[7:9, 7:9] = (255, 140, 40, 200)
    return t


def _bed_top(r):
    t = _n(r, (180, 30, 30), 8)
    t[:5, :, :3] = (235, 235, 235)
    t[0, :, :3] = t[4, :, :3] = (200, 200, 200)
    t[7, :, :3] = (150, 25, 25)
    t[:, [0, 15], :3] *= .8
    return t


def _bed_side(r):
    t = _blank()
    t[7:11] = _n(r, (180, 30, 30), 8)[7:11]
    t[11:13] = _planks(r, (150, 105, 60))[11:13]
    t[13:16, 0:3] = (120, 85, 45, 255)
    t[13:16, 13:16] = (120, 85, 45, 255)
    return t


def _cobweb(r):
    t = _blank()
    c = (235, 235, 240)
    for x1, y1 in ((0, 0), (15, 0), (0, 15), (15, 15), (8, 0), (0, 8), (15, 8), (8, 15)):
        _line(t, 8, 8, x1, y1, c)
    for rad in (3, 6):
        for a in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            _px(t, int(round(8 + rad * np.cos(a))), int(round(8 + rad * np.sin(a))), c)
    t[t[..., 3] > 0, 3] = 210
    return t


def _slime(r):
    t = _n(r, (115, 200, 95), 6)
    t[3:13, 3:13, :3] = (85, 170, 72)
    t[[3, 12], 3:13, :3] = (130, 215, 110)
    t[3:13, [3, 12], :3] = (130, 215, 110)
    return t


def _mossy_bricks(r):
    t = _stone_bricks(r)
    m = (r.rand(16, 16) < .3) & ((XX + YY + r.randint(0, 6)) % 7 < 3)
    t[m, :3] = np.array((80, 120, 55), np.float32) + r.uniform(-15, 15, (m.sum(), 1))
    return t


def _cracked_bricks(r):
    t = _stone_bricks(r)
    for x0, y0, x1, y1 in ((2, 1, 5, 6), (5, 6, 4, 11), (10, 3, 13, 9), (13, 9, 11, 14)):
        _line(t, x0, y0, x1, y1, (70, 70, 70))
    return t


def _deepslate(r):
    t = _n(r, (78, 78, 86), 7)
    for y in range(0, 16, 3):
        t[y, :, :3] *= .82
    t[r.rand(16, 16) < .1, :3] *= .75
    return t


def _deepslate_top(r):
    t = _n(r, (80, 80, 88), 6)
    t[[0, 8], :, :3] *= .75
    t[0:8, [0, 8], :3] *= .75
    t[8:16, [4, 12], :3] *= .75
    return t


def _mushroom(cap, flat=False):
    def f(r):
        t = _blank()
        t[9:16, 7:9] = (225, 220, 205, 255)
        if flat:
            _ell(t, 8, 9, 6, 2.2, cap, r, 8)
        else:
            _ell(t, 8, 7.5, 5, 3.2, cap, r, 8)
            for x, y in ((6, 6), (9, 5), (10, 8), (5, 8)):
                t[y, x] = (245, 245, 240, 255)
        return t
    return f


def _fern(r):
    t = _blank()
    for x1, y1 in ((2, 5), (13, 4), (4, 1), (11, 1), (8, 0)):
        pts = [(8 + (x1 - 8) * f, 15 + (y1 - 15) * f) for f in np.linspace(0, 1, 9)]
        for i, (x, y) in enumerate(pts):
            c = (60 + i * 6, 135 + i * 5, 50)
            _px(t, int(x), int(y), c)
            if i % 2 and i < 8:
                _px(t, int(x) + 1, int(y) - 1, c)
                _px(t, int(x) - 1, int(y) - 1, c)
    return t


def _sugar_cane(r):
    t = _blank()
    for x in (3, 8, 12):
        t[:, x] = (140, 195, 95, 255)
        t[:, x + 1] = (110, 170, 75, 255)
        for y in range(r.randint(0, 3), 16, 5):
            t[y, x:x + 2] = (95, 140, 60, 255)
    _line(t, 4, 6, 6, 3, (120, 180, 80))
    _line(t, 13, 9, 15, 6, (120, 180, 80))
    return t


def _sapling(r):
    t = _blank()
    t[9:16, 7:9] = (110, 80, 45, 255)
    m = _ell(t, 8, 6, 4.8, 4.2, (60, 135, 45), r, 20)
    t[m & (r.rand(16, 16) < .2), 3] = 0
    return t


def _farmland(r):
    t = _n(r, (92, 62, 38), 8)
    for y in (1, 5, 9, 13):
        t[y:y + 2, :, :3] *= .7
    return t


def _wheat(stage):
    def f(r):
        t = _blank()
        top = (11, 6, 2)[stage]
        col = ((70, 160, 50), (130, 170, 60), (200, 175, 75))[stage]
        for x in range(1, 16, 3):
            h = top + r.randint(0, 3)
            t[h:16, x] = (*col, 255)
            if stage == 2:
                t[h:h + 4, x] = (225, 195, 90, 255)
                t[h + 1:h + 3, min(15, x + 1)] = (210, 180, 80, 255)
        return t
    return f


# ---- new item sprites
def _seeds(r):
    t = _blank()
    for x, y in ((4, 5), (9, 3), (12, 8), (6, 10), (10, 12), (3, 13)):
        t[y:y + 2, x:x + 2] = (95, 150, 60, 255)
        t[y, x] = (160, 190, 90, 255)
    return t


def _wheat_item(r):
    t = _blank()
    for x1 in (3, 6, 8, 10, 13):
        _line(t, 8, 15, x1, 4, (200, 170, 70))
        t[2:6, x1] = (230, 200, 95, 255)
        _px(t, x1 - 1, 3, (215, 185, 80))
    t[10:12, 6:11] = (150, 110, 50, 255)
    return _outline(t)


def _bread(r):
    t = _blank()
    _ell(t, 8, 9.5, 6.5, 3.8, (195, 135, 65), r, 8)
    for x in (5, 8, 11):
        _line(t, x - 1, 8, x + 1, 7, (235, 190, 115))
    return _outline(t)


def _bone(r):
    t = _blank()
    _line(t, 4, 11, 11, 4, (235, 232, 220), 2)
    for x, y in ((2, 11), (4, 13), (11, 2), (13, 4)):
        t[y:y + 2, x:x + 2] = (240, 238, 228, 255)
    return _outline(t)


def _string(r):
    t = _blank()
    for i in range(14):
        _px(t, 1 + i, int(round(8 + 3 * math.sin(i * .8))), (235, 235, 240))
    return _outline(t)


def _feather(r):
    t = _blank()
    _line(t, 3, 13, 12, 3, (175, 175, 180))
    for i in range(3, 11):
        x, y = 3 + i * 9 // 10, 13 - i
        _px(t, x - 1, y - 1, (245, 245, 250))
        _px(t, x + 1, y + 1, (235, 235, 240))
        _px(t, x - 2, y - 1, (230, 230, 235))
    return _outline(t)


def _arrow(r):
    t = _blank()
    _line(t, 3, 12, 11, 4, (130, 95, 55))
    t[2:5, 11:14] = (190, 190, 200, 255)
    t[2, 11] = t[4, 13] = (0, 0, 0, 0)
    for x, y in ((2, 11), (3, 13), (1, 12), (4, 14), (2, 13)):
        _px(t, x, y, (240, 240, 240))
    return _outline(t)


def _bow(r):
    t = _blank()
    pts = [(2 + 12 * math.sin(a), 14 - 12 * math.cos(a)) for a in np.linspace(0, math.pi / 2, 16)]
    for x, y in pts:
        _px(t, int(round(x)), int(round(y)), (125, 88, 45))
        _px(t, int(round(x)) - 1, int(round(y)) + 1, (100, 70, 35))
    _line(t, 2, 2, 14, 14, (225, 225, 225))
    return _outline(t)


def _hoe(r):
    t = _blank()
    _line(t, 3, 13, 11, 5, (125, 90, 50), 2)
    t[3:5, 9:14] = (150, 150, 155, 255)
    return _outline(t)


def _bucket(fill=None):
    def f(r):
        t = _blank()
        for y in range(6, 15):
            w = 4 - (y - 6) // 4
            t[y, 8 - w - 1:8 + w + 1] = (175, 175, 185, 255)
        t[6, 3:13] = (215, 215, 225, 255)
        for x, y in ((4, 5), (5, 3), (7, 2), (9, 2), (11, 3), (12, 5)):
            _px(t, x, y, (120, 120, 130))
        if fill:
            t[7:9, 4:12] = (*fill, 255)
        return _outline(t)
    return f


def _emerald(r):
    t = _blank()
    m = (abs(XX - 7.5) * .8 + abs(YY - 7.5) * .55 <= 4.6)
    t[m] = (40, 200, 95, 255)
    t[m & (XX < 7) & (YY < 8)] = (130, 245, 170, 255)
    t[m & (XX > 9) & (YY > 8)] = (20, 140, 60, 255)
    return _outline(t)


def _fish(c):
    def f(r):
        t = _blank()
        _ell(t, 9, 8, 5, 3, c, r, 8)
        for i in range(4):
            t[8 - i:9 + i, 1 + i] = (*np.array(c) * .85, 255)
        t[7, 11] = (20, 20, 20, 255)
        return _outline(t)
    return f


NEW_TILE_FUNCS = [
    ('leaves_f', _leaves((58, 120, 38), False)), ('birch_leaves_f', _leaves((105, 150, 60), False)),
    ('spruce_leaves', _leaves((45, 85, 58))), ('spruce_leaves_f', _leaves((45, 85, 58), False)),
    ('autumn_leaves', _autumn), ('autumn_leaves_f', lambda r: _autumn(r, False)),
    ('torch', _torch), ('torch_top', _torch_top), ('lantern', _lantern), ('lantern_top', _lantern_top),
    ('jack_face', _jack_face), ('sea_lantern', _sea_lantern), ('magma', _magma), ('glowshroom', _glowshroom),
    ('crystal', _crystal), ('chest_side', _chest_side), ('chest_top', _chest_top), ('spawner', _spawner),
    ('bed_top', _bed_top), ('bed_side', _bed_side), ('cobweb', _cobweb), ('slime', _slime),
    ('spruce_side', lambda r: _log_side(r, (72, 52, 32))), ('spruce_top', lambda r: _log_top(r, (140, 105, 62), (72, 52, 32))),
    ('spruce_planks', lambda r: _planks(r, (118, 86, 52))), ('birch_planks', lambda r: _planks(r, (205, 185, 132))),
    ('granite', _speckle((160, 105, 85), [(195, 145, 125), (115, 72, 60)])),
    ('diorite', _speckle((205, 205, 205), [(120, 120, 120), (235, 235, 235)])),
    ('andesite', _speckle((135, 135, 136), [(160, 160, 162), (108, 108, 110)])),
    ('deepslate', _deepslate), ('deepslate_top', _deepslate_top), ('mossy_stone_bricks', _mossy_bricks),
    ('cracked_stone_bricks', _cracked_bricks), ('emerald_ore', _ore((60, 215, 105))),
    ('red_sand', lambda r: _n(r, (190, 102, 45), 10)), ('terracotta', lambda r: _n(r, (160, 88, 62), 6)),
    ('terracotta_red', lambda r: _n(r, (145, 62, 48), 6)), ('terracotta_yellow', lambda r: _n(r, (186, 132, 42), 6)),
    ('red_mushroom', _mushroom((200, 35, 30))), ('brown_mushroom', _mushroom((150, 110, 80), True)),
    ('fern', _fern), ('sugar_cane', _sugar_cane), ('blue_orchid', _flower((60, 150, 240))), ('sapling', _sapling),
    ('farmland', _farmland), ('wheat1', _wheat(0)), ('wheat2', _wheat(1)), ('wheat3', _wheat(2)),
    ('seeds', _seeds), ('wheat_item', _wheat_item), ('bread', _bread), ('bone', _bone),
    ('bone_meal', lambda r: _gunpowder(r) * [2.6, 2.6, 2.55, 1]), ('string', _string), ('feather', _feather),
    ('arrow', _arrow), ('bow', _bow), ('hoe', _hoe), ('bucket', _bucket()), ('water_bucket', _bucket((50, 90, 220))),
    ('lava_bucket', _bucket((240, 120, 20))), ('emerald', _emerald),
    ('raw_rabbit', _meat((235, 155, 145), drum=True)), ('cooked_rabbit', _meat((185, 115, 60), drum=True)),
    ('venison', _meat((165, 40, 45))), ('cooked_venison', _meat((112, 62, 36))),
    ('raw_fish', _fish((120, 165, 195))), ('cooked_fish', _fish((205, 145, 80)))]


TILE_FUNCS = [('crack%d' % i, _crack(i)) for i in range(5)] + [
    ('grass_top', lambda r: _n(r, (95, 155, 55), 18)), ('grass_side', lambda r: _topped(r, (95, 155, 55), 18)),
    ('dirt', _dirt), ('stone', _stone), ('cobble', _cobble), ('sand', lambda r: _n(r, (219, 207, 160), 8)),
    ('gravel', lambda r: _cobble(r) * [1.05, 1.0, .95, 1]), ('log_side', _log_side), ('log_top', _log_top),
    ('leaves', _leaves((58, 120, 38))), ('planks', _planks), ('glass', _glass),
    ('water', lambda r: _n(r, (45, 75, 215), 12, 175)),
    ('lava', lambda r: _n(r, (220, 90, 15), 25) + (r.rand(16, 16, 1) < .2) * [35, 100, 45, 0]),
    ('bedrock', lambda r: _n(r, (90, 90, 90), 45)), ('coal_ore', _ore((30, 30, 30))),
    ('iron_ore', _ore((216, 175, 147))), ('gold_ore', _ore((252, 238, 75))), ('diamond_ore', _ore((93, 236, 245))),
    ('snow', lambda r: _n(r, (240, 250, 252), 5)), ('snow_side', lambda r: _topped(r, (240, 250, 252), 5)),
    ('cactus_side', _ridged((20, 125, 35), 4, .7)), ('cactus_top', _capped((40, 140, 45), (60, 160, 60))),
    ('bricks', _bricks), ('tnt_side', _tnt_side), ('tnt_top', _tnt_top),
    ('tnt_bottom', lambda r: _n(r, (205, 45, 35), 10)),
    ('obsidian', lambda r: _n(r, (22, 16, 34), 8) + (r.rand(16, 16, 1) < .12) * [40, 30, 60, 0]),
    ('glowstone', _glowstone), ('craft_top', _craft_top), ('craft_side', _craft_side), ('bookshelf', _bookshelf),
    ('wool_white', _wool((230, 230, 230))), ('wool_red', _wool((175, 45, 40))), ('wool_blue', _wool((50, 60, 165))),
    ('wool_yellow', _wool((225, 200, 50))), ('wool_green', _wool((85, 125, 30))), ('wool_black', _wool((30, 30, 35))),
    ('birch_side', _birch_side), ('birch_top', lambda r: _log_top(r, (200, 180, 130), (216, 214, 205))),
    ('birch_leaves', _leaves((105, 150, 60))), ('sandstone_side', _sandstone_side),
    ('sandstone_top', lambda r: _n(r, (222, 208, 162), 4)), ('mossy', lambda r: _cobble(r, True)),
    ('ice', _ice), ('clay', lambda r: _n(r, (158, 164, 178), 6)),
    ('pumpkin_side', _ridged((215, 125, 25), 4, .78)), ('pumpkin_top', _capped((200, 115, 25), (90, 110, 40))),
    ('melon_side', _ridged((110, 165, 35), 5, .7)), ('melon_top', _capped((115, 160, 40), (100, 150, 40))),
    ('stone_bricks', _stone_bricks), ('gold_block', _metal((245, 205, 60))), ('iron_block', _metal((220, 220, 220))),
    ('diamond_block', _metal((100, 225, 220))), ('tall_grass', _tall_grass),
    ('flower_red', _flower((210, 30, 30))), ('flower_yellow', _flower((245, 220, 40))), ('dead_bush', _dead_bush),
    ('stick', lambda r: _outline(_line_t(r))), ('coal', _coal), ('iron_ingot', _ingot((225, 225, 225))),
    ('gold_ingot', _ingot((250, 205, 50))), ('diamond', _diamond), ('apple', _apple((205, 25, 35))),
    ('golden_apple', _apple((240, 200, 50))), ('pork', _meat((240, 145, 145))),
    ('cooked_pork', _meat((170, 100, 55))), ('beef', _meat((200, 50, 50))), ('steak', _meat((115, 65, 35))),
    ('chicken', _meat((240, 200, 180), drum=True)), ('cooked_chicken', _meat((190, 130, 70), drum=True)),
    ('mutton', _meat((215, 70, 70), False)), ('cooked_mutton', _meat((150, 85, 50), False)),
    ('rotten_flesh', _flesh), ('gunpowder', _gunpowder)]


def _line_t(r):
    t = _blank()
    _line(t, 3, 12, 12, 3, (125, 92, 50))
    _line(t, 4, 12, 12, 4, (90, 65, 35))
    return t


TILE_FUNCS += [('tool%d' % i, _tool(i % 4, i // 4)) for i in range(16)]
EGG_COLS = [((240, 160, 160), (215, 115, 115)), ((70, 50, 30), (170, 170, 170)), ((230, 230, 230), (240, 180, 170)),
            ((205, 205, 205), (220, 30, 30)), ((0, 170, 170), (110, 150, 90)), ((20, 180, 20), (10, 10, 10)),
            ((150, 115, 80), (100, 75, 50)), ((220, 120, 40), (245, 240, 230)), ((140, 95, 55), (230, 220, 200)),
            ((220, 215, 200), (120, 110, 100)), ((30, 30, 40), (240, 240, 240)), ((240, 240, 230), (60, 140, 60)),
            ((80, 140, 200), (240, 170, 60)), ((200, 200, 200), (80, 80, 80)), ((50, 40, 35), (190, 20, 20)),
            ((110, 140, 200), (230, 120, 60)), ((250, 170, 220), (90, 60, 160)), ((90, 160, 60), (230, 210, 90)),
            ((130, 90, 50), (60, 40, 20)), ((150, 150, 155), (90, 90, 95)), ((236, 110, 190), (120, 240, 200)),
            ((150, 220, 250), (240, 160, 230)), ((120, 60, 160), (255, 220, 120)), ((240, 170, 230), (120, 200, 250)),
            ((60, 130, 70), (200, 180, 90)), ((90, 60, 35), (50, 30, 20)), ((120, 90, 60), (60, 140, 60)),
            ((240, 200, 40), (30, 30, 30)), ((60, 40, 30), (150, 60, 40)), ((60, 140, 200), (120, 220, 120)),
            ((210, 200, 160), (120, 100, 70)), ((240, 245, 250), (120, 160, 220)), ((220, 230, 255), (150, 160, 200)),
            ((240, 110, 220), (255, 215, 80))]
TILE_FUNCS += NEW_TILE_FUNCS
TILE_FUNCS += [('egg%d' % i, _egg(*c)) for i, c in enumerate(EGG_COLS) if i < 15]

ITEM_TILE = {STICK: 'stick', COAL: 'coal', IRON_INGOT: 'iron_ingot', GOLD_INGOT: 'gold_ingot', DIAMOND: 'diamond',
             APPLE: 'apple', PORK: 'pork', COOKED_PORK: 'cooked_pork', BEEF: 'beef', STEAK: 'steak',
             CHICKEN: 'chicken', COOKED_CHICKEN: 'cooked_chicken', MUTTON: 'mutton', COOKED_MUTTON: 'cooked_mutton',
             ROTTEN_FLESH: 'rotten_flesh', GUNPOWDER: 'gunpowder', GOLDEN_APPLE: 'golden_apple'}
ITEM_TILE.update({120 + i: 'tool%d' % i for i in range(20)})
ITEM_TILE.update({SEEDS: 'seeds', WHEAT: 'wheat_item', BREAD: 'bread', BONE: 'bone', BONE_MEAL: 'bone_meal',
                  STRING: 'string', FEATHER: 'feather', ARROW: 'arrow', BOW: 'bow', HOE: 'hoe', BUCKET: 'bucket',
                  WATER_BUCKET: 'water_bucket', LAVA_BUCKET: 'lava_bucket', EMERALD: 'emerald',
                  RAW_RABBIT: 'raw_rabbit', COOKED_RABBIT: 'cooked_rabbit', VENISON: 'venison',
                  COOKED_VENISON: 'cooked_venison', RAW_FISH: 'raw_fish', COOKED_FISH: 'cooked_fish', SILLIUM_INGOT: 'sillium_ingot', SADDLE: 'saddle',
                  PARAGLIDER: 'paraglider', GRAPPLE: 'grapple', SLINGSHOT: 'slingshot', JELLY_BALL: 'jelly_ball',
                  PRISM_SHARD: 'prism_shard', SILLY_BERRY: 'silly_berry', IRON_SPEAR: 'iron_spear',
                  BATTLE_AXE: 'battle_axe', DAGGER: 'dagger', SILLIUM_SPEAR: 'sillium_spear', SILLIUM_BLADE: 'sillium_blade', ROYAL_SCEPTER: 'scepter', FISHING_ROD: 'fishing_rod', HONEY: 'honey'})
ITEM_TILE.update({e: 'egg%d' % i for i, e in enumerate(EGG_IDS)})
ITEM_TILE.update({_id: 'wpn%d' % (WEAPON_KIND[_id][0] * 4 + WEAPON_KIND[_id][1]) for _id in WEAPON_IDS})

# ====================================================================== texture revamp (v3)
DITH = np.tile(np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) / 16., (4, 4))


def _vn(r, nx=4, ny=None, oct=2):
    """Seamless (tileable) value noise in [0, 1]."""
    ny = nx if ny is None else ny
    out, amp, tot = np.zeros((16, 16), np.float32), 1., 0.
    for _ in range(oct):
        g = r.rand(ny, nx).astype(np.float32)
        fy, fx = np.arange(16) * ny / 16., np.arange(16) * nx / 16.
        y0, x0 = np.floor(fy).astype(int), np.floor(fx).astype(int)
        ty, tx = fy - y0, fx - x0
        ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
        a = g[y0 % ny][:, x0 % nx] * (1 - tx) + g[y0 % ny][:, (x0 + 1) % nx] * tx
        b = g[(y0 + 1) % ny][:, x0 % nx] * (1 - tx) + g[(y0 + 1) % ny][:, (x0 + 1) % nx] * tx
        out += amp * (a * (1 - ty[:, None]) + b * ty[:, None])
        tot += amp
        amp *= .5
        nx, ny = min(16, nx * 2), min(16, ny * 2)
    out /= tot
    return (out - out.min()) / max(1e-6, out.max() - out.min())


def _shades(col, ks=(.58, .72, .86, 1., 1.12)):
    return [tuple(min(255, c * k) for c in col) for k in ks]


def _pal(v, cols, dither=.6):
    n = len(cols)
    idx = np.clip(np.floor(v * n + (DITH - .5) * dither), 0, n - 1).astype(int)
    t = np.zeros((16, 16, 4), np.float32)
    t[..., :3] = np.array(cols, np.float32)[idx]
    t[..., 3] = 255
    return t


def _vort(r, n):
    """Tileable voronoi: cell id, distance to edge."""
    pts = r.uniform(0, 16, (n, 2))
    offs = np.array([(dy, dx) for dy in (-16, 0, 16) for dx in (-16, 0, 16)], np.float32)
    P = (pts[None, :, :] + offs[:, None, :]).reshape(-1, 2)
    ids = np.tile(np.arange(n), 9)
    d = np.sqrt((YY[..., None] + .5 - P[:, 0]) ** 2 + (XX[..., None] + .5 - P[:, 1]) ** 2)
    o = np.argsort(d, 2)
    cell = ids[o[..., 0]]
    edge = np.take_along_axis(d, o[..., 1:2], 2)[..., 0] - np.take_along_axis(d, o[..., :1], 2)[..., 0]
    return cell, edge


def _bevel(t, cell, hi=1.22, lo=.66):
    up, lf = np.roll(cell, 1, 0) != cell, np.roll(cell, 1, 1) != cell
    dn, rt = np.roll(cell, -1, 0) != cell, np.roll(cell, -1, 1) != cell
    t[(up | lf) & ~(dn | rt), :3] *= hi
    t[(dn | rt), :3] *= lo
    return t


def _stones(r, n, cols, mortar=None, hi=1.2, lo=.62):
    cell, edge = _vort(r, n)
    v = np.clip(r.rand(n)[cell] * .55 + _vn(r, 4) * .45, 0, 1)
    t = _bevel(_pal(v, cols), cell, hi, lo)
    if mortar is not None:
        t[edge < .45, :3] = mortar
    return t


def t_stone(r):
    v = _vn(r, 4, 8, 3) * .7 + _vn(r, 8) * .3
    return _pal(v, [(98, 98, 100), (112, 112, 114), (126, 126, 128), (138, 138, 140), (150, 150, 152)])


def t_dirt(r):
    t = _pal(_vn(r, 4, oct=3), [(96, 66, 44), (112, 78, 52), (128, 90, 60), (142, 102, 70), (156, 114, 80)])
    for _ in range(6):
        y, x = r.randint(0, 16, 2)
        t[y, x, :3] = (88, 62, 44)
        t[y, (x + 1) % 16, :3] = (170, 130, 95)
    return t


GRASS_P = [(72, 118, 40), (86, 134, 46), (98, 150, 52), (112, 164, 60), (128, 178, 70)]


def t_grass_top(r):
    return _pal(_vn(r, 4, oct=3) * .75 + r.rand(16, 16) * .25, GRASS_P, .9)


def t_grass_side(r, pal=GRASS_P):
    t = t_dirt(r)
    g = _pal(_vn(r, 8) * .6 + r.rand(16, 16) * .4, pal, .9)
    for x in range(16):
        d = 2 + r.randint(0, 3) + (1 if r.rand() < .25 else 0)
        t[:d, x] = g[:d, x]
        t[d, x, :3] *= .8
    return t


def t_sand(r, base=(219, 207, 160)):
    t = _pal(_vn(r, 4) * .5 + r.rand(16, 16) * .5, _shades(base, (.84, .9, .95, 1., 1.04)), 1.)
    t[r.rand(16, 16) < .05, :3] *= .85
    return t


def t_gravel(r):
    return _stones(r, 18, [(100, 96, 94), (118, 114, 112), (134, 130, 128), (150, 146, 142), (166, 160, 156)],
                   None, 1.25, .6)


def t_cobble(r):
    return _stones(r, 8, [(96, 96, 96), (112, 112, 112), (128, 128, 128), (144, 144, 144), (160, 160, 160)],
                   (80, 80, 80))


def t_mossy(r):
    t = t_cobble(r)
    v = _vn(r, 4)
    m = (v > .55) & (r.rand(16, 16) < .85)
    t[m, :3] = np.array(_pal(_vn(r, 8), [(64, 98, 44), (78, 114, 52), (92, 130, 60)])[m, :3])
    return t


def t_planks(base):
    def f(r):
        P = _shades(base, (.68, .8, .9, 1., 1.08))
        grain = _vn(r, 2, 8, 2)
        t = _pal(grain * .8 + r.rand(16, 16) * .2, P, .8)
        for row in range(4):
            y0 = row * 4
            t[y0 + 3, :, :3] = np.array(P[0]) * .85
            t[y0, :, :3] = np.minimum(255, np.array(P[4]) * 1.03)
            sx = (row * 7 + r.randint(0, 4)) % 16
            t[y0:y0 + 3, sx, :3] = np.array(P[0]) * .9
        return t
    return f


def t_log_side(base):
    def f(r):
        v = _vn(r, 8, 2, 2) * .8 + r.rand(16, 16) * .2
        t = _pal(v, _shades(base, (.62, .76, .88, 1., 1.1)), .5)
        for x in range(0, 16, 4):
            xx = (x + r.randint(0, 2)) % 16
            t[:, xx, :3] *= .78
        return t
    return f


def t_log_top(ring, bark):
    def f(r):
        d = np.maximum(abs(XX - 7.5), abs(YY - 7.5)) + _vn(r, 4) * .8
        P = _shades(ring, (.82, .9, 1., 1.08))
        t = _pal(((d.astype(int) % 3) / 2.) * .6 + _vn(r, 8) * .4, P, .5)
        m = np.maximum(abs(XX - 7.5), abs(YY - 7.5)) > 6.5
        t[m] = t_log_side(bark)(r)[m]
        return t
    return f


def t_leaves(base, holes=True):
    def f(r):
        v = _vn(r, 8, oct=2)
        t = _pal(v * .7 + r.rand(16, 16) * .3, _shades(base, (.55, .7, .84, 1., 1.14)), 1.)
        h = (_vn(r, 8) < .28) & (r.rand(16, 16) < .85)
        if holes:
            t[h, 3] = 0
        else:
            t[h, :3] *= .45
        return t
    return f


def t_autumn(holes=True):
    def f(r):
        v = _vn(r, 8, oct=2)
        t = _pal(v * .75 + r.rand(16, 16) * .25, [(150, 40, 25), (190, 70, 30), (215, 110, 35), (230, 150, 45),
                                                  (240, 190, 70)], 1.)
        h = (_vn(r, 8) < .28) & (r.rand(16, 16) < .85)
        if holes:
            t[h, 3] = 0
        else:
            t[h, :3] *= .45
        return t
    return f


def t_ore(col):
    def f(r):
        t = t_stone(r)
        hi = tuple(min(255, c * 1.25 + 20) for c in col)
        lo = tuple(c * .62 for c in col)
        for _ in range(4):
            y, x = r.randint(1, 14), r.randint(1, 14)
            for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1), (r.randint(-1, 2), r.randint(-1, 2))):
                t[(y + dy) % 16, (x + dx) % 16, :3] = col
            t[y, x, :3] = hi
            t[(y + 1) % 16, (x + 2) % 16, :3] = lo
            t[(y + 2) % 16, (x + 1) % 16, :3] = lo
        return t
    return f


def t_bricks(r):
    P = [(122, 56, 44), (138, 64, 50), (152, 72, 56), (166, 82, 64)]
    t = np.zeros((16, 16, 4), np.float32)
    t[..., 3] = 255
    mortar = (176, 170, 160)
    for row in range(4):
        off = 4 if row % 2 else 0
        for b in range(3):
            x0 = (off + b * 8) % 16
            col = np.array(P[r.randint(0, 4)], np.float32)
            for dx in range(7):
                for dy in range(3):
                    t[row * 4 + dy, (x0 + dx) % 16, :3] = col * (1.08 if dy == 0 else (.9 if dy == 2 else 1.)) * r.uniform(.94, 1.04)
        t[row * 4 + 3, :, :3] = mortar
        for b in range(2):
            t[row * 4:row * 4 + 3, (off + 7 + b * 8) % 16, :3] = mortar
    t[r.rand(16, 16) < .05, :3] *= .9
    return t


def t_stone_bricks(r, moss=False, crack=False):
    P = [(104, 104, 106), (116, 116, 118), (128, 128, 130), (140, 140, 142)]
    t = _pal(_vn(r, 4, oct=2), P, .8)
    for y in (7, 15):
        t[y, :, :3] = (78, 78, 80)
        t[(y + 1) % 16, :, :3] *= 1.12
    for x, ys in ((7, range(0, 7)), (15, range(8, 15))):
        for y in ys:
            t[y, x, :3] = (78, 78, 80)
            t[y, (x + 1) % 16, :3] *= 1.08
    if moss:
        m = (_vn(r, 4) > .55) & (r.rand(16, 16) < .8)
        t[m, :3] = _pal(_vn(r, 8), [(64, 98, 44), (78, 114, 52), (92, 130, 60)])[m, :3]
    if crack:
        for x0, y0, x1, y1 in ((2, 1, 5, 6), (5, 6, 4, 11), (10, 3, 13, 9), (13, 9, 11, 14)):
            _line(t, x0, y0, x1, y1, (66, 66, 68))
    return t


def t_wool(base):
    def f(r):
        v = _vn(r, 4) * .6 + ((XX // 2 + YY) % 2) * .14 + r.rand(16, 16) * .26
        return _pal(v, _shades(base, (.8, .88, .95, 1., 1.06)), .7)
    return f


def t_sandstone_side(r):
    P = _shades((216, 202, 155), (.82, .9, .96, 1., 1.04))
    t = _pal(_vn(r, 8, 2) * .6 + r.rand(16, 16) * .4, P, .8)
    t[:3, :, :3] = np.array(P[4])
    t[3, :, :3] = np.array(P[1])
    for y in (7, 10):
        t[y, :, :3] *= .9
    t[12:, :, :3] = np.array(P[2])
    t[12, :, :3] = np.array(P[0])
    return t


def t_snow(r):
    return _pal(_vn(r, 4) * .6 + r.rand(16, 16) * .4, [(222, 232, 238), (232, 240, 244), (242, 248, 250),
                                                         (250, 252, 254)], .9)


SNOW_P = [(222, 232, 238), (232, 240, 244), (242, 248, 250), (250, 252, 254)]


def t_ice(r):
    t = _pal(_vn(r, 4), [(126, 166, 236), (142, 180, 244), (160, 194, 250), (178, 208, 252)], .5)
    for i in range(16):
        t[i, (i + 3) % 16, :3] = (214, 230, 255)
        t[(i + 1) % 16, (i + 10) % 16, :3] = (200, 222, 255)
    return t


def t_glass(r):
    t = _blank()
    t[0, :] = t[15, :] = t[:, 0] = t[:, 15] = (196, 224, 236, 255)
    t[1, 1:15] = t[1:15, 1] = (232, 246, 252, 255)
    for i in range(4):
        t[3 + i, 3 + i] = t[4 + i, 3 + i] = (255, 255, 255, 200)
    t[11, 11] = t[12, 12] = (255, 255, 255, 200)
    return t


def t_bedrock(r):
    return _stones(r, 12, [(40, 40, 40), (70, 70, 70), (96, 96, 96), (124, 124, 124), (150, 150, 150)], None, 1.3, .5)


def t_obsidian(r):
    t = _pal(_vn(r, 4, oct=3), [(14, 10, 22), (22, 16, 34), (32, 24, 48), (46, 34, 66)], .7)
    t[(_vn(r, 8) > .82) & (r.rand(16, 16) < .5), :3] = (90, 66, 130)
    return t


def t_glowstone(r):
    return _stones(r, 9, [(172, 120, 60), (210, 160, 82), (238, 196, 110), (252, 222, 150), (255, 240, 190)],
                   (130, 90, 44), 1.15, .7)


def t_clay(r):
    return _pal(_vn(r, 4) * .7 + r.rand(16, 16) * .3, [(146, 152, 166), (154, 160, 174), (162, 168, 182), (170, 176, 190)], .8)


def t_speckle(base, a, b):
    def f(r):
        t = _pal(_vn(r, 4, oct=3), _shades(base, (.88, .94, 1., 1.05)), .7)
        n1, n2 = _vn(r, 8), _vn(r, 8)
        t[(n1 > .72) & (r.rand(16, 16) < .8), :3] = a
        t[(n2 > .76) & (r.rand(16, 16) < .8), :3] = b
        return t
    return f


def t_deepslate(r):
    v = _vn(r, 2, 8, 2) * .7 + r.rand(16, 16) * .3
    t = _pal(v, [(58, 58, 64), (68, 68, 75), (78, 78, 86), (90, 90, 98)], .7)
    for y in range(1, 16, 4):
        t[y, :, :3] *= .8
    return t


def t_deepslate_top(r):
    t = _pal(_vn(r, 4), [(62, 62, 68), (72, 72, 80), (82, 82, 90)], .7)
    for (y0, y1, x0, x1) in ((0, 8, 0, 8), (0, 8, 8, 16), (8, 16, 4, 12), (8, 16, 12, 20)):
        t[y0, x0:min(16, x1), :3] *= .7
        t[y0:y1, x0 % 16, :3] *= .7
    return t


def t_terracotta(base):
    def f(r):
        return _pal(_vn(r, 4) * .6 + r.rand(16, 16) * .4, _shades(base, (.9, .95, 1., 1.04)), .8)
    return f


def t_metal(base):
    def f(r):
        P = _shades(base, (.7, .84, .94, 1., 1.12))
        t = _pal(_vn(r, 2, 8) * .5 + .4, P, .4)
        t[[0, 15], :, :3], t[:, [0, 15], :3] = np.array(P[0]), np.array(P[0])
        t[1, 1:15, :3] = np.array(P[4])
        t[1:15, 1, :3] = np.array(P[4])
        for i in range(3, 13):
            t[i, 15 - i, :3] = np.minimum(255, np.array(P[4]) * 1.08)
        return t
    return f


def t_birch_side(r):
    t = _pal(_vn(r, 8, 2) * .6 + r.rand(16, 16) * .4, [(206, 204, 196), (218, 216, 208), (228, 226, 220), (238, 236, 230)], .6)
    for _ in range(7):
        y, x = r.randint(0, 16), r.randint(0, 13)
        w = r.randint(2, 5)
        t[y, x:x + w, :3] = (42, 42, 38)
        if r.rand() < .5:
            t[(y + 1) % 16, x + 1:x + w - 1, :3] = (70, 70, 64)
    return t


def t_cactus_side(r):
    t = _pal(_vn(r, 2, 8), [(14, 96, 26), (20, 112, 34), (28, 128, 42), (38, 142, 52)], .5)
    for x in (0, 4, 8, 12):
        t[:, x, :3] *= .7
        t[:, x + 2, :3] = np.minimum(255, t[:, x + 2, :3] * 1.15)
    for y in range(1, 16, 4):
        t[y, (y * 3) % 16, :3] = (230, 230, 200)
    return t


def t_pumpkin_side(r):
    t = _pal(_vn(r, 2, 8), [(176, 92, 16), (196, 108, 22), (214, 124, 28), (228, 142, 40)], .5)
    for x in (0, 5, 10):
        t[:, x, :3] *= .74
        t[:, x + 2, :3] = np.minimum(255, t[:, x + 2, :3] * 1.1)
    return t


def t_crafting_top(r):
    t = t_planks((162, 130, 78))(r)
    t[[1, 14], 1:15, :3] = (92, 66, 36)
    t[1:15, [1, 14], :3] = (92, 66, 36)
    t[7:9, 2:14, :3] *= .72
    t[2:14, 7:9, :3] *= .72
    return t


def t_crafting_side(r):
    t = t_planks((162, 130, 78))(r)
    t[:3, :, :3] = (112, 82, 46)
    t[3, :, :3] = (84, 60, 32)
    t[5:12, 3, :3] = (150, 150, 155)
    t[5:7, 2:5, :3] = (180, 180, 185)
    t[6:13, 11, :3] = (96, 66, 34)
    t[5:7, 9:14, :3] = (150, 150, 155)
    return t


def t_farmland(r):
    t = _pal(_vn(r, 4), [(70, 46, 28), (82, 54, 34), (94, 62, 40), (106, 72, 46)], .7)
    for y in (2, 6, 10, 14):
        t[y, :, :3] *= .68
        t[(y + 1) % 16, :, :3] *= 1.12
    return t


TEX_OVERRIDE = {
    'grass_top': t_grass_top, 'grass_side': t_grass_side, 'dirt': t_dirt, 'stone': t_stone, 'cobble': t_cobble,
    'sand': t_sand, 'gravel': t_gravel, 'log_side': t_log_side((104, 80, 48)),
    'log_top': t_log_top((180, 146, 92), (104, 80, 48)), 'leaves': t_leaves((62, 124, 40)),
    'leaves_f': t_leaves((62, 124, 40), False), 'planks': t_planks((166, 132, 80)), 'glass': t_glass,
    'bedrock': t_bedrock, 'coal_ore': t_ore((34, 34, 36)), 'iron_ore': t_ore((214, 172, 142)),
    'gold_ore': t_ore((250, 222, 60)), 'diamond_ore': t_ore((90, 232, 236)), 'emerald_ore': t_ore((50, 210, 100)),
    'snow': t_snow, 'snow_side': lambda r: t_grass_side(r, SNOW_P), 'cactus_side': t_cactus_side,
    'bricks': t_bricks, 'obsidian': t_obsidian, 'glowstone': t_glowstone, 'craft_top': t_crafting_top,
    'craft_side': t_crafting_side, 'wool_white': t_wool((232, 232, 232)), 'wool_red': t_wool((176, 46, 40)),
    'wool_blue': t_wool((52, 64, 168)), 'wool_yellow': t_wool((226, 200, 52)), 'wool_green': t_wool((86, 126, 32)),
    'wool_black': t_wool((34, 34, 40)), 'birch_side': t_birch_side,
    'birch_top': t_log_top((204, 184, 132), (214, 212, 204)), 'birch_leaves': t_leaves((110, 154, 64)),
    'birch_leaves_f': t_leaves((110, 154, 64), False), 'sandstone_side': t_sandstone_side,
    'sandstone_top': lambda r: t_sand(r, (222, 208, 164)), 'mossy': t_mossy, 'ice': t_ice, 'clay': t_clay,
    'pumpkin_side': t_pumpkin_side, 'stone_bricks': t_stone_bricks,
    'mossy_stone_bricks': lambda r: t_stone_bricks(r, moss=True),
    'cracked_stone_bricks': lambda r: t_stone_bricks(r, crack=True), 'gold_block': t_metal((246, 206, 64)),
    'iron_block': t_metal((222, 222, 224)), 'diamond_block': t_metal((100, 226, 222)),
    'spruce_side': t_log_side((74, 54, 34)), 'spruce_top': t_log_top((142, 108, 64), (74, 54, 34)),
    'spruce_leaves': t_leaves((46, 88, 60)), 'spruce_leaves_f': t_leaves((46, 88, 60), False),
    'spruce_planks': t_planks((120, 88, 54)), 'birch_planks': t_planks((208, 188, 136)),
    'autumn_leaves': t_autumn(), 'autumn_leaves_f': t_autumn(False),
    'granite': t_speckle((164, 108, 88), (194, 146, 126), (116, 74, 62)),
    'diorite': t_speckle((206, 206, 206), (126, 126, 128), (236, 236, 236)),
    'andesite': t_speckle((136, 136, 138), (162, 162, 164), (108, 108, 110)),
    'deepslate': t_deepslate, 'deepslate_top': t_deepslate_top, 'red_sand': lambda r: t_sand(r, (192, 104, 46)),
    'terracotta': t_terracotta((162, 90, 64)), 'terracotta_red': t_terracotta((146, 62, 48)),
    'terracotta_yellow': t_terracotta((188, 134, 44)), 'farmland': t_farmland,
    'chest_side': lambda r: _chest_side(r), 'bookshelf': lambda r: _bookshelf(r),
}


def t_bed(head):
    def f(r):
        t = _pal(_vn(r, 4) * .6 + r.rand(16, 16) * .4, [(132, 22, 22), (152, 28, 28), (170, 34, 34), (186, 42, 42)], .7)
        t[:, [0, 15], :3] *= .78
        for y in (4, 9, 13):
            t[y, 1:15, :3] *= .86
        if head:
            p = _pal(_vn(r, 4), [(206, 206, 210), (222, 222, 226), (236, 236, 240), (246, 246, 250)], .6)
            t[1:7, 2:14] = p[1:7, 2:14]
            t[7, 2:14, :3] = (205, 205, 210)
            t[0, :, :3] = (110, 18, 18)
        else:
            t[15, :, :3] = (110, 18, 18)
        return t
    return f


def t_bed_side(r):
    t = _blank()
    t[7:11] = _pal(_vn(r, 4), [(140, 24, 24), (160, 30, 30), (176, 38, 38)], .7)[7:11]
    t[11:13] = t_planks((150, 106, 60))(r)[11:13]
    t[13:16, 0:3] = (112, 80, 42, 255)
    t[13:16, 13:16] = (112, 80, 42, 255)
    return t


def t_rain(r):
    t = _blank()
    for x in range(1, 16, 4):
        y, ln = r.randint(0, 16), r.randint(4, 8)
        for k in range(ln):
            t[(y + k) % 16, x % 16] = (200, 212, 238, 40 + 14 * k)
    return t


def t_snowflake(r):
    t = _blank()
    for _ in range(9):
        y, x = r.randint(0, 15), r.randint(0, 15)
        t[y, x] = (250, 252, 255, 255)
        if r.rand() < .5:
            t[y + 1, x] = t[y, x + 1] = (235, 240, 250, 200)
    return t


TEX_OVERRIDE.update({'bed_top': t_bed(False), 'bed_side': t_bed_side})


# ---- v4: pebbles, portal, Sillyland
def t_pebble(r):
    t = _blank()
    for cx, cy, rx, ry, c in ((6.5, 7.5, 1.6, 1.2, (128, 126, 122)), (9.5, 9, 1.4, 1.1, (104, 102, 100)),
                              (8.5, 6, 1.1, .9, (150, 146, 140))):
        _ell(t, cx, cy, rx, ry, c, r, 8)
    t[13:16, 5:11] = (118, 116, 112, 255)
    t[13, 5:11, :3] = (146, 142, 138)
    return t


def t_portal(r):
    a = np.arctan2(YY - 7.5, XX - 7.5)
    d = np.hypot(YY - 7.5, XX - 7.5)
    v = (np.sin(a * 3 + d * 1.3) * .5 + .5) * .7 + _vn(r, 4) * .3
    t = _pal(v, [(90, 30, 140), (150, 50, 190), (210, 90, 220), (250, 160, 240), (255, 220, 250)], .9)
    t[(v < .28) & (r.rand(16, 16) < .7), 3] = 0
    return t


SG_P = [(176, 70, 150), (200, 86, 170), (222, 104, 188), (238, 128, 204), (250, 156, 220)]


def t_silly_grass_top(r):
    return _pal(_vn(r, 4, oct=3) * .75 + r.rand(16, 16) * .25, SG_P, .9)


def t_silly_soil(r):
    t = _pal(_vn(r, 4, oct=3), [(84, 52, 96), (98, 62, 110), (112, 72, 124), (126, 84, 138)], .8)
    t[r.rand(16, 16) < .05, :3] = (200, 160, 230)
    return t


def t_silly_grass_side(r):
    t = t_silly_soil(r)
    g = _pal(_vn(r, 8) * .6 + r.rand(16, 16) * .4, SG_P, .9)
    for x in range(16):
        d = 2 + r.randint(0, 4)
        t[:d, x] = g[:d, x]
        t[d, x, :3] *= .8
    return t


def t_silly_stone(r):
    return _pal(_vn(r, 4, 8, 3) * .7 + _vn(r, 8) * .3, [(54, 110, 118), (62, 126, 134), (72, 142, 150), (84, 158, 164),
                                                         (98, 172, 176)])


def t_silly_cobble(r):
    return _stones(r, 8, [(58, 116, 124), (70, 134, 142), (84, 150, 158), (98, 166, 172), (114, 182, 186)], (40, 82, 90))


def t_silly_log_side(r):
    v = ((XX + YY * 2) % 8 < 4).astype(np.float32) * .55 + _vn(r, 8, 2) * .45
    return _pal(v, [(120, 60, 140), (150, 80, 170), (230, 200, 240), (250, 230, 250)], .5)


def t_silly_leaves(holes=True):
    def f(r):
        v = _vn(r, 8, oct=2)
        t = _pal(v * .7 + r.rand(16, 16) * .3, [(40, 150, 150), (60, 180, 170), (90, 210, 190), (140, 230, 210),
                                                (200, 250, 230)], 1.)
        h = (_vn(r, 8) < .28) & (r.rand(16, 16) < .85)
        if holes:
            t[h, 3] = 0
        else:
            t[h, :3] *= .45
        return t
    return f


def t_shroom_stem(r):
    t = _pal(_vn(r, 2, 8) * .7 + r.rand(16, 16) * .3, [(214, 206, 190), (226, 218, 204), (236, 230, 218), (246, 242, 232)], .6)
    t[r.rand(16, 16) < .04, :3] = (190, 170, 200)
    return t


def t_shroom_cap(r):
    t = _pal(_vn(r, 4) * .7 + r.rand(16, 16) * .3, [(40, 80, 190), (52, 100, 214), (66, 122, 232), (84, 146, 246)], .8)
    cell, _ = _vort(r, 7)
    k = r.rand(7)[cell]
    t[k > .78, :3] = (230, 240, 255)
    return t


def t_jelly(r):
    t = _pal(_vn(r, 4), [(220, 90, 170), (236, 110, 186), (248, 136, 204)], .6)
    t[3:13, 3:13, :3] = np.array((255, 170, 220)) * .96
    t[[3, 12], 3:13, :3] = (255, 200, 236)
    t[3:13, [3, 12], :3] = (255, 200, 236)
    t[5:7, 5:7, :3] = 255
    return t


def t_silly_crystal(r):
    cell, edge = _vort(r, 6)
    t = _pal(np.clip(r.rand(6)[cell] * .7 + _vn(r, 4) * .3, 0, 1),
             [(90, 200, 230), (140, 220, 245), (200, 170, 245), (240, 200, 250), (255, 240, 255)], .4)
    return _bevel(t, cell, 1.15, .7)


def t_sillium_ore(r):
    t = t_silly_stone(r)
    for _ in range(4):
        y, x = r.randint(1, 14), r.randint(1, 14)
        for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
            t[(y + dy) % 16, (x + dx) % 16, :3] = (240, 90, 220)
        t[y, x, :3] = (255, 200, 250)
        t[(y + 2) % 16, (x + 1) % 16, :3] = (150, 40, 140)
    return t


def t_silly_bricks(r):
    P = [(150, 120, 200), (166, 134, 214), (180, 148, 226), (194, 164, 236)]
    t = _pal(_vn(r, 4), P, .7)
    for row in range(4):
        t[row * 4 + 3, :, :3] = (110, 84, 150)
        off = 4 if row % 2 else 0
        for b in range(2):
            t[row * 4:row * 4 + 3, (off + 7 + b * 8) % 16, :3] = (110, 84, 150)
        t[row * 4, :, :3] *= 1.08
    return t


def t_silly_tuft(r):
    t = _blank()
    for x in range(1, 15, 2):
        h = r.randint(6, 13)
        c = np.array(SG_P[r.randint(0, 5)])
        for y in range(16 - h, 16):
            xx = x + int(round(math.sin(y * .6 + x) * 1.2))
            if 0 <= xx < 16:
                t[y, xx] = (*c, 255)
    return t


def t_glowbloom(r):
    t = _blank()
    t[8:16, 7:9] = (60, 160, 150, 255)
    t[11, 9:11] = (60, 160, 150, 255)
    for a in range(6):
        ang = a * math.pi / 3
        _ell(t, 8 + math.cos(ang) * 2.6, 5 + math.sin(ang) * 2.6, 1.6, 1.6, (120, 240, 255))
    t[4:7, 7:9] = (255, 250, 160, 255)
    return t


def t_spear(head):
    def f(r):
        t = _blank()
        _line(t, 2, 14, 11, 5, (125, 90, 50))
        _line(t, 11, 5, 14, 2, head, 2)
        t[3:6, 11] = (*head, 255)
        return _outline(t)
    return f


def t_battle_axe(r):
    t = _blank()
    _line(t, 3, 13, 11, 5, (115, 85, 45), 2)
    _ell(t, 11, 5, 3.6, 3.6, (210, 210, 215))
    t[2:9, 13:15] = 0
    _ell(t, 7.5, 3.5, 1.6, 1.6, (180, 180, 186))
    return _outline(t)


def t_dagger(c):
    def f(r):
        t = _blank()
        _line(t, 6, 10, 12, 4, c, 2)
        _line(t, 4, 9, 7, 12, (70, 55, 35))
        _line(t, 3, 13, 5, 11, (115, 85, 45), 2)
        return _outline(t)
    return f


def t_saddle(r):
    t = _blank()
    _ell(t, 8, 8, 6, 3.5, (120, 70, 35), r, 8)
    t[5:7, 6:10, :3] = (150, 95, 50)
    t[10:14, 4] = (90, 90, 95, 255)
    t[10:14, 11] = (90, 90, 95, 255)
    return _outline(t)


def t_paraglider(r):
    t = _blank()
    for x in range(1, 15):
        y = int(round(4 - math.sin((x - 1) / 13 * math.pi) * 3)) + 3
        c = ((220, 60, 60), (240, 200, 60), (60, 140, 220))[(x // 3) % 3]
        t[y - 1:y + 1, x] = (*c, 255)
    for x0 in (2, 8, 13):
        _line(t, x0, 6, 8, 13, (200, 200, 200))
    t[13:15, 7:10] = (110, 80, 45, 255)
    return _outline(t)


def t_grapple(r):
    t = _blank()
    _line(t, 3, 13, 9, 7, (150, 150, 155))
    for x1, y1 in ((13, 3), (9, 2), (14, 8)):
        _line(t, 10, 6, x1, y1, (190, 190, 196), 1)
    for i in range(4):
        t[13 - i, 2 + i // 2] = (220, 210, 180, 255)
    return _outline(t)


def t_slingshot(r):
    t = _blank()
    _line(t, 8, 15, 8, 9, (125, 90, 50), 2)
    _line(t, 8, 9, 4, 3, (125, 90, 50), 2)
    _line(t, 8, 9, 12, 3, (125, 90, 50), 2)
    _line(t, 4, 3, 12, 3, (200, 80, 80))
    return _outline(t)


def t_orb(c):
    def f(r):
        t = _blank()
        _ell(t, 8, 8.5, 4.5, 4.5, c, r, 6)
        t[6:8, 6:8, :3] = 255
        return _outline(t)
    return f


def t_shard(r):
    t = _blank()
    pts = ((8, 1), (12, 7), (9, 14), (5, 8))
    for i in range(4):
        _line(t, *pts[i], *pts[(i + 1) % 4], (150, 230, 250))
    for y in range(2, 14):
        for x in range(5, 12):
            if abs(x - 8.5) < (7 - abs(y - 7.5)) * .55:
                t[y, x] = (180 + (x - 5) * 8, 200, 250, 255)
    return _outline(t)


def t_berry(r):
    t = _blank()
    for cx, cy in ((6, 9), (10, 9), (8, 6), (8, 11)):
        _ell(t, cx, cy, 2.3, 2.3, (150, 60, 200), r, 15)
        t[int(cy) - 1, int(cx) - 1, :3] = (230, 180, 255)
    t[2:4, 8] = (70, 160, 90, 255)
    return _outline(t)


TEX_OVERRIDE.update({})
V4_TILES = [('pebble', t_pebble), ('silly_portal', t_portal), ('silly_grass_top', t_silly_grass_top),
            ('silly_grass_side', t_silly_grass_side), ('silly_soil', t_silly_soil), ('silly_stone', t_silly_stone),
            ('silly_cobble', t_silly_cobble), ('silly_log_side', t_silly_log_side),
            ('silly_log_top', t_log_top((210, 170, 230), (130, 70, 150))), ('silly_leaves', t_silly_leaves()),
            ('silly_leaves_f', t_silly_leaves(False)), ('silly_planks', t_planks((176, 132, 200))),
            ('shroom_stem', t_shroom_stem), ('shroom_cap', t_shroom_cap), ('jelly', t_jelly),
            ('silly_crystal', t_silly_crystal), ('sillium_ore', t_sillium_ore),
            ('sillium_block', t_metal((206, 96, 214))), ('silly_bricks', t_silly_bricks), ('silly_tuft', t_silly_tuft),
            ('glowbloom', t_glowbloom), ('sillium_ingot', _ingot((214, 100, 220))), ('saddle', t_saddle),
            ('paraglider', t_paraglider), ('grapple', t_grapple), ('slingshot', t_slingshot),
            ('jelly_ball', t_orb((236, 110, 190))), ('prism_shard', t_shard), ('silly_berry', t_berry),
            ('iron_spear', t_spear((220, 220, 225))), ('battle_axe', t_battle_axe), ('dagger', t_dagger((215, 215, 220))),
            ('sillium_spear', t_spear((220, 110, 230))), ('sillium_blade', t_dagger((230, 130, 240)))]


# ---- v5 textures
def t_slab_side(base_fn, pal):
    def f(r):
        t = base_fn(r)
        g = _pal(_vn(r, 8) * .6 + r.rand(16, 16) * .4, pal, .9)
        for x in range(16):
            d = 2 + r.randint(0, 3)
            t[8:8 + d, x] = g[8:8 + d, x]
            t[8 + d, x, :3] *= .8
        t[:8, :, 3] = 0
        return t
    return f


def t_bark(base, ring=False):
    def f(r):
        v = _vn(r, 8, 2, 2) * .75 + r.rand(16, 16) * .25
        t = _pal(v, _shades(base, (.62, .76, .9, 1., 1.1)), .5)
        if ring:
            for y in range(1, 16, 4):
                t[y, :, :3] *= .75
        return t
    return f


def t_blossom(holes=True):
    def f(r):
        v = _vn(r, 8, oct=2)
        t = _pal(v * .7 + r.rand(16, 16) * .3, [(214, 120, 160), (232, 150, 184), (244, 178, 204), (252, 206, 224),
                                                (255, 230, 240)], 1.)
        h = (_vn(r, 8) < .26) & (r.rand(16, 16) < .85)
        if holes:
            t[h, 3] = 0
        else:
            t[h, :3] *= .5
        return t
    return f


def t_palm_leaves(holes=True):
    def f(r):
        t = _pal(_vn(r, 4) * .5 + r.rand(16, 16) * .5, [(40, 120, 30), (56, 146, 38), (74, 170, 48), (100, 192, 62)], .8)
        m = ((XX + YY) % 4 == 0) | ((XX - YY) % 5 == 0)
        if holes:
            t[~m & (r.rand(16, 16) < .45), 3] = 0
        return t
    return f


def t_altar_side(r):
    t = t_silly_bricks(r)
    for y in (5, 6, 9, 10):
        t[y, 5:11, :3] = (255, 140, 240)
    t[7:9, 7:9, :3] = (255, 230, 120)
    return t


def t_altar_top(r):
    t = _pal(_vn(r, 4), [(200, 70, 190), (230, 100, 210), (250, 140, 230)], .7)
    for k in range(5):
        x = 2 + k * 3
        t[4:10, x, :3] = (255, 215, 80)
        t[3, x, :3] = (255, 250, 200)
    t[10:12, 2:15, :3] = (255, 200, 60)
    return t


def t_hay_side(r):
    t = _pal(_vn(r, 2, 8) * .6 + r.rand(16, 16) * .4, [(170, 130, 30), (196, 156, 40), (218, 180, 56), (236, 204, 80)], .6)
    t[[4, 11], :, :3] = (110, 70, 20)
    return t


def t_hay_top(r):
    t = _pal(_vn(r, 4) * .5 + r.rand(16, 16) * .5, [(170, 130, 30), (196, 156, 40), (218, 180, 56), (236, 204, 80)], .8)
    t[[0, 15], :, :3] = t[:, [0, 15], :3] = (150, 110, 30)
    return t


def t_hive_side(r):
    t = t_planks((190, 150, 80))(r)
    t[6:11, 4:12, :3] = (60, 40, 20)
    t[7:10, 5:11, :3] = (240, 190, 60)
    return t


def t_hive_top(r):
    t = _blank()
    t[...] = (230, 180, 60, 255)
    for y in range(16):
        for x in range(16):
            if ((x + (y // 3) * 2) % 4 == 0) or y % 3 == 0:
                t[y, x, :3] = (190, 130, 30)
    return t


def t_path(r):
    return _pal(_vn(r, 4) * .6 + r.rand(16, 16) * .4, [(140, 110, 70), (156, 124, 80), (170, 138, 92), (184, 152, 104)], .8)


def t_candy(r):
    t = _blank()
    t[..., 3] = 255
    m = ((XX + YY) // 3) % 2 == 0
    t[m, :3] = (235, 60, 80)
    t[~m, :3] = (250, 245, 245)
    t[..., :3] *= (.92 + _vn(r, 4) * .12)[..., None]
    return t


def t_cloud(r):
    return _pal(_vn(r, 4, oct=3), [(225, 230, 240), (236, 240, 248), (246, 248, 252), (255, 255, 255)], .7)


def t_bell(r):
    t = _blank()
    for y in range(4, 15):
        w = 2 + (y - 4) // 3
        t[y, 8 - w:8 + w] = (230, 190, 60, 255)
        t[y, 8 - w] = (255, 230, 120, 255)
    t[2:4, 7:9] = (120, 90, 40, 255)
    return t


def t_mace(c):
    def f(r):
        t = _blank()
        _line(t, 2, 14, 9, 7, (115, 85, 45), 2)
        _ell(t, 11, 5, 3.2, 3.2, c)
        for x, y in ((11, 0), (11, 10), (6, 5), (15, 5), (14, 2), (8, 2)):
            _px(t, x, y, tuple(min(255, v * 1.15) for v in c))
        return _outline(t)
    return f


def t_battle(c):
    def f(r):
        t = _blank()
        _line(t, 3, 13, 11, 5, (115, 85, 45), 2)
        _ell(t, 11, 5, 3.6, 3.6, c)
        t[2:9, 13:15] = 0
        _ell(t, 7.5, 3.5, 1.6, 1.6, tuple(v * .85 for v in c))
        return _outline(t)
    return f


def t_scepter(r):
    t = _blank()
    _line(t, 3, 13, 10, 6, (240, 200, 70), 2)
    _ell(t, 11.5, 4.5, 2.8, 2.8, (240, 120, 230))
    t[3:5, 10:12] = (255, 230, 255, 255)
    for x, y in ((9, 1), (12, 1), (15, 3)):
        _px(t, x, y, (255, 220, 90))
    return _outline(t)


def t_rod(r):
    t = _blank()
    _line(t, 2, 14, 12, 3, (125, 90, 50))
    _line(t, 12, 3, 13, 12, (225, 225, 225))
    t[12:14, 12:14] = (200, 40, 40, 255)
    return _outline(t)


def t_honey(r):
    t = _blank()
    _ell(t, 8, 10, 4, 4.2, (240, 170, 40), r, 10)
    t[4:7, 6:10] = (210, 230, 240, 255)
    t[8:10, 6:8, :3] = (255, 220, 120)
    return _outline(t)


V5_TILES = [('grass_slab_side', t_slab_side(t_dirt, GRASS_P)), ('silly_grass_slab_side', t_slab_side(t_silly_soil, SG_P)),
            ('cherry_side', t_bark((92, 52, 58))), ('cherry_top', t_log_top((220, 170, 160), (92, 52, 58))),
            ('cherry_leaves', t_blossom()), ('cherry_leaves_f', t_blossom(False)),
            ('palm_side', t_bark((150, 120, 80), True)), ('palm_top', t_log_top((200, 170, 120), (150, 120, 80))),
            ('palm_leaves', t_palm_leaves()), ('palm_leaves_f', t_palm_leaves(False)),
            ('altar_side', t_altar_side), ('altar_top', t_altar_top),
            ('calcite', t_speckle((222, 222, 214), (200, 200, 192), (240, 240, 236))),
            ('amethyst', t_silly_crystal), ('hay_side', t_hay_side), ('hay_top', t_hay_top), ('hive_side', t_hive_side),
            ('hive_top', t_hive_top), ('path_top', t_path), ('candy', t_candy), ('cloud', t_cloud), ('bell', t_bell),
            ('scepter', t_scepter), ('fishing_rod', t_rod), ('honey', t_honey)]
_TC = [(165, 130, 80), (140, 140, 140), (230, 230, 230), (90, 235, 225), (220, 100, 230)]
for _t in range(5):
    V5_TILES += [('wpn%d' % (_t * 4), t_spear(_TC[_t])), ('wpn%d' % (_t * 4 + 1), t_mace(_TC[_t])),
                 ('wpn%d' % (_t * 4 + 2), t_dagger(_TC[_t])), ('wpn%d' % (_t * 4 + 3), t_battle(_TC[_t]))]


# ====================================================================== v6 art pass (cohesive hand-drawn style)
def _stroke(t, x, y, dx, dy, n, col):
    for k in range(n):
        xx, yy = (x + dx * k) % 16, (y + dy * k) % 16
        t[yy, xx, :3] = col
        t[yy, xx, 3] = 255


def _hl(col, k):
    return tuple(max(0, min(255, c * k)) for c in col)


def a_grass_top(r):
    t = _pal(_vn(r, 4, oct=2), [(74, 124, 42), (84, 138, 48), (94, 150, 54), (104, 162, 60)], .5)
    for _ in range(34):
        x, y = r.randint(0, 16, 2)
        _stroke(t, x, y, r.choice((-1, 1)), -1, 2, (66, 112, 36))
    for _ in range(22):
        x, y = r.randint(0, 16, 2)
        _stroke(t, x, y, r.choice((-1, 1)), -1, 2, (122, 182, 72))
    return t


def a_dirt(r):
    t = _pal(_vn(r, 4, oct=3), [(104, 72, 48), (118, 82, 56), (130, 92, 62), (142, 102, 70)], .45)
    cell, _ = _vort(r, 9)
    t[(r.rand(9)[cell] < .25), :3] *= .88
    for _ in range(6):
        y, x = r.randint(0, 15), r.randint(0, 15)
        t[y, x:x + 2, :3] = (166, 134, 100)
        t[(y + 1) % 16, x:x + 2, :3] = (84, 58, 40)
    return t


def a_grass_side(r, pal=((74, 124, 42), (88, 140, 50), (104, 160, 60)), base=None):
    t = (base or a_dirt)(r)
    for x in range(16):
        d = 3 + (1 if r.rand() < .45 else 0) + (1 if r.rand() < .2 else 0)
        for y in range(d):
            t[y, x, :3] = pal[2] if y == 0 else (pal[1] if y < d - 1 else pal[0])
        t[d, x, :3] = _hl(t[d, x, :3], .72)
    return t


def a_stone(r):
    t = _pal(_vn(r, 3, oct=3), [(112, 112, 114), (122, 122, 124), (132, 132, 134), (142, 142, 144)], .4)
    for _ in range(3):
        x, y = r.randint(0, 16, 2)
        for _ in range(r.randint(3, 6)):
            t[y % 16, x % 16, :3] = (90, 90, 92)
            t[(y + 1) % 16, (x + 1) % 16, :3] = (156, 156, 158)
            x, y = x + r.choice((-1, 0, 1)), y + 1
    return t


def a_cobble(r):
    cell, edge = _vort(r, 8)
    shade = r.uniform(.85, 1.1, 8)[cell]
    t = _pal(np.clip(_vn(r, 8) * .5 + .25, 0, 1), [(112, 112, 112), (124, 124, 124), (136, 136, 136)], .5)
    t[..., :3] *= shade[..., None]
    t = _bevel(t, cell, 1.28, .62)
    t[edge < .45, :3] = (64, 64, 66)
    return t


def a_sand(r, base=(220, 206, 158)):
    t = _pal(_vn(r, 4) * .6 + r.rand(16, 16) * .4, _shades(base, (.9, .95, 1., 1.04)), .9)
    for y0 in (3, 9, 14):
        for x in range(16):
            y = (y0 + int(round(math.sin(x * .7 + y0) * .8))) % 16
            t[y, x, :3] = _hl(base, 1.07)
            t[(y + 1) % 16, x, :3] = _hl(base, .9)
    return t


def a_gravel(r):
    cell, edge = _vort(r, 20)
    hues = np.array([(132, 126, 122), (116, 116, 120), (148, 140, 132), (104, 100, 98), (160, 154, 148)], np.float32)
    t = np.zeros((16, 16, 4), np.float32)
    t[..., :3] = hues[r.randint(0, 5, 20)][cell]
    t[..., 3] = 255
    t = _bevel(t, cell, 1.25, .6)
    t[edge < .35, :3] = (78, 74, 72)
    return t


def a_planks(base):
    def f(r):
        P = _shades(base, (.66, .8, .92, 1., 1.08))
        t = _pal(np.full((16, 16), .55) + r.rand(16, 16) * .2, P, .5)
        for row in range(4):
            ph = r.uniform(0, 6)
            for x in range(16):
                for y in range(row * 4, row * 4 + 3):
                    if math.sin(x * .55 + ph + y * 1.7) > .82:
                        t[y, x, :3] = P[1]
            t[row * 4 + 3, :, :3] = P[0]
            t[row * 4, :, :3] = P[4]
            sx = (row * 7 + r.randint(0, 3)) % 16
            t[row * 4:row * 4 + 3, sx, :3] = P[0]
            t[row * 4 + 1, (sx + 2) % 16, :3] = (70, 60, 50)
        return t
    return f


def a_bark(base):
    def f(r):
        P = _shades(base, (.6, .76, .9, 1., 1.12))
        t = _pal(_vn(r, 8, 2) * .6 + r.rand(16, 16) * .15 + .15, P, .5)
        x = r.randint(0, 3)
        while x < 16 + x % 3:
            w = r.randint(2, 5)
            for y in range(16):
                wob = int(round(math.sin(y * .5 + x) * .6))
                t[y, (x + wob) % 16, :3] = P[0]
                if r.rand() < .7:
                    t[y, (x + wob + 1) % 16, :3] = P[4]
            x += w
        return t
    return f


def a_log_top(ring, bark):
    def f(r):
        P = _shades(ring, (.78, .88, 1., 1.08))
        d = np.maximum(np.abs(XX - 7.5), np.abs(YY - 7.5))
        t = _pal(np.clip(((d + _vn(r, 4) * .6).astype(int) % 2) * .5 + .3, 0, 1), P, .3)
        t[(d < 1.6), :3] = _hl(ring, .7)
        t[d > 6.5] = a_bark(bark)(r)[d > 6.5]
        return t
    return f


def a_leaves(base, holes=True):
    def f(r):
        P = _shades(base, (.55, .7, .85, 1., 1.15))
        t = np.zeros((16, 16, 4), np.float32)
        t[..., :3] = P[0]
        t[..., 3] = 255
        for _ in range(26):
            x, y = r.randint(0, 16, 2)
            c = P[r.randint(1, 4)]
            for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
                t[(y + dy) % 16, (x + dx) % 16, :3] = c
            t[(y - 1) % 16, (x - 1) % 16, :3] = P[4]
        gap = (t[..., 0] == P[0][0]) & (t[..., 1] == P[0][1]) & (r.rand(16, 16) < .75)
        if holes:
            t[gap, 3] = 0
        return t
    return f


def a_ore(col, base_fn=None):
    def f(r):
        t = (base_fn or a_stone)(r)
        hi, lo = _hl(col, 1.35), _hl(col, .55)
        for _ in range(4):
            x, y = r.randint(1, 13), r.randint(1, 13)
            shape = {(0, 0), (1, 0), (0, 1), (1, 1), [(2, 0), (0, 2), (2, 1), (1, 2), (-1, 0)][r.randint(0, 5)]}
            for dx, dy in shape:
                t[(y + dy) % 16, (x + dx) % 16, :3] = col
            for dx, dy in shape:
                if (dx + 1, dy + 1) not in shape:
                    t[(y + dy + 1) % 16, (x + dx + 1) % 16, :3] = lo
            t[y, x, :3] = hi
            t[(y + 1) % 16, (x + 1) % 16, :3] = col
        return t
    return f


def a_bricks(r):
    P = [(130, 58, 46), (146, 66, 52), (160, 76, 60), (172, 88, 70)]
    t = np.zeros((16, 16, 4), np.float32)
    t[..., :3], t[..., 3] = (190, 184, 172), 255
    for row in range(4):
        off = 4 if row % 2 else 0
        for b in range(3):
            x0, c = (off + b * 8) % 16, np.array(P[r.randint(0, 4)], np.float32)
            for dx in range(7):
                for dy in range(3):
                    k = 1.12 if dy == 0 else (.82 if dy == 2 else 1.)
                    t[row * 4 + dy, (x0 + dx) % 16, :3] = c * k * (1.08 if dx == 0 else (.9 if dx == 6 else 1.))
    return t


def a_stone_bricks(r, moss=False, crack=False):
    t = _pal(_vn(r, 4), [(116, 116, 118), (126, 126, 128), (136, 136, 138)], .5)
    for (y0, x0, x1) in ((0, 0, 8), (0, 8, 16), (8, 4, 12), (8, 12, 20)):
        for x in range(x0, x1):
            t[y0, x % 16, :3] = (158, 158, 160)
            t[y0 + 6, x % 16, :3] = (92, 92, 94)
            t[y0 + 7, x % 16, :3] = (70, 70, 72)
        for y in range(y0, y0 + 7):
            t[y, x0 % 16, :3] = (150, 150, 152)
            t[y, (x1 - 1) % 16, :3] = (70, 70, 72)
    if moss:
        m = (_vn(r, 4) > .55) & (r.rand(16, 16) < .8)
        t[m, :3] = _pal(_vn(r, 8), [(70, 106, 46), (84, 122, 54), (98, 138, 62)])[m, :3]
    if crack:
        for x0, y0, x1, y1 in ((2, 1, 5, 6), (10, 9, 13, 14)):
            _line(t, x0, y0, x1, y1, (64, 64, 66))
    return t


def a_glass(r):
    t = _blank()
    t[0, :] = t[:, 0] = (222, 240, 248, 255)
    t[15, :] = t[:, 15] = (150, 176, 190, 255)
    for i in range(5):
        t[2 + i, 6 - i] = (255, 255, 255, 220)
    for i in range(3):
        t[10 + i, 13 - i] = (240, 250, 255, 190)
    return t


def a_wool(base):
    def f(r):
        P = _shades(base, (.82, .9, .97, 1.04))
        t = _pal(_vn(r, 4) * .5 + .25, P, .6)
        for _ in range(40):
            x, y = r.randint(0, 16, 2)
            _stroke(t, x, y, 1, 1, 2, P[r.choice((0, 3))])
        return t
    return f


def a_snow(r):
    t = _pal(_vn(r, 4, oct=2), [(220, 230, 240), (232, 240, 247), (244, 248, 252)], .6)
    t[(r.rand(16, 16) < .05), :3] = (255, 255, 255)
    t[(r.rand(16, 16) < .04), :3] = (200, 216, 236)
    return t


def a_obsidian(r):
    cell, edge = _vort(r, 7)
    t = np.zeros((16, 16, 4), np.float32)
    t[..., :3] = np.array([(20, 14, 32), (30, 20, 46), (40, 28, 60)], np.float32)[r.randint(0, 3, 7)][cell]
    t[..., 3] = 255
    t = _bevel(t, cell, 1.6, .7)
    t[edge < .3, :3] = (12, 8, 20)
    return t


def a_flower(petal, center):
    def f(r):
        t = _blank()
        for y in range(8, 16):
            t[y, 7] = (64, 132, 44, 255)
            t[y, 8] = (48, 110, 36, 255)
        t[11, 9:11] = (70, 146, 50, 255)
        t[12, 5:7] = (70, 146, 50, 255)
        for dx, dy in ((0, -2), (2, 0), (0, 2), (-2, 0), (1, -1), (1, 1), (-1, 1), (-1, -1)):
            cx, cy = 7 + dx, 5 + dy
            t[cy:cy + 2, cx:cx + 2] = (*petal, 255)
        t[4, 6:8] = (*_hl(petal, 1.25), 255)
        t[5:7, 7:9] = (*center, 255)
        return t
    return f


def a_tall_grass(r):
    t = _blank()
    for x in range(0, 16, 2):
        h = r.randint(6, 14)
        for k, y in enumerate(range(16 - h, 16)):
            c = (70 + k * 3, 130 + k * 2, 44) if k > 2 else (110, 170, 64)
            xx = x + (1 if (k < 3 and r.rand() < .5) else 0)
            t[y, min(15, xx)] = (*c, 255)
    return t


ART_V6 = {
    'grass_top': a_grass_top, 'grass_side': a_grass_side, 'dirt': a_dirt, 'stone': a_stone, 'cobble': a_cobble,
    'sand': a_sand, 'gravel': a_gravel, 'planks': a_planks((168, 134, 82)), 'log_side': a_bark((106, 80, 50)),
    'log_top': a_log_top((186, 150, 96), (106, 80, 50)), 'leaves': a_leaves((60, 122, 40)),
    'leaves_f': a_leaves((60, 122, 40), False), 'birch_leaves': a_leaves((108, 152, 62)),
    'birch_leaves_f': a_leaves((108, 152, 62), False), 'spruce_leaves': a_leaves((46, 90, 60)),
    'spruce_leaves_f': a_leaves((46, 90, 60), False), 'spruce_side': a_bark((76, 56, 36)),
    'spruce_top': a_log_top((146, 110, 66), (76, 56, 36)), 'spruce_planks': a_planks((122, 90, 56)),
    'birch_planks': a_planks((210, 190, 138)), 'cherry_side': a_bark((96, 54, 60)),
    'coal_ore': a_ore((36, 36, 40)), 'iron_ore': a_ore((216, 176, 146)), 'gold_ore': a_ore((252, 214, 60)),
    'diamond_ore': a_ore((92, 230, 236)), 'emerald_ore': a_ore((50, 206, 100)),
    'sillium_ore': a_ore((236, 96, 220), t_silly_stone), 'bricks': a_bricks, 'stone_bricks': a_stone_bricks,
    'mossy_stone_bricks': lambda r: a_stone_bricks(r, moss=True),
    'cracked_stone_bricks': lambda r: a_stone_bricks(r, crack=True), 'glass': a_glass,
    'wool_white': a_wool((232, 232, 232)), 'wool_red': a_wool((176, 46, 40)), 'wool_blue': a_wool((52, 64, 168)),
    'wool_yellow': a_wool((226, 200, 52)), 'wool_green': a_wool((86, 126, 32)), 'wool_black': a_wool((40, 40, 46)),
    'snow': a_snow, 'snow_side': lambda r: a_grass_side(r, ((216, 226, 236), (232, 240, 247), (246, 250, 253))),
    'obsidian': a_obsidian, 'red_sand': lambda r: a_sand(r, (194, 106, 48)),
    'sandstone_top': lambda r: a_sand(r, (222, 208, 164)), 'flower_red': a_flower((214, 36, 36), (90, 50, 20)),
    'flower_yellow': a_flower((246, 214, 44), (200, 140, 20)), 'blue_orchid': a_flower((70, 150, 240), (230, 230, 240)),
    'tall_grass': a_tall_grass, 'path_top': lambda r: a_sand(r, (150, 118, 76)),
    'grass_slab_side': lambda r: _half_side(a_grass_side(r)),
}


def _half_side(full):
    t = full.copy()
    t[8:] = full[:8]
    t[:8, :, 3] = 0
    return t

TILE_FUNCS = [(n, TEX_OVERRIDE.get(n, f)) for n, f in TILE_FUNCS]
TILE_FUNCS += [('bed_head_top', t_bed(True)), ('rain', t_rain), ('snowflake', t_snowflake)]
TILE_FUNCS += [('egg%d' % i, _egg(*c)) for i, c in enumerate(EGG_COLS) if i >= 15]
TILE_FUNCS += V4_TILES + [('tool%d' % i, _tool(i % 4, 4)) for i in range(16, 20)]
TILE_FUNCS += V5_TILES
TILE_FUNCS = [(n, ART_V6.get(n, f)) for n, f in TILE_FUNCS]

TILE = {}
TEXIDX = np.zeros((256, 3), np.int32)
ICON_TILE = {}


def build_atlas():
    atlas, tiles = np.zeros((16 * AR, 256, 4), np.uint8), {}
    for i, (name, fn) in enumerate(TILE_FUNCS):
        t = np.clip(fn(np.random.RandomState(zlib.crc32(name.encode()) & 0xffffffff)), 0, 255).astype(np.uint8)
        r, c = divmod(i, 16)
        atlas[r * 16:r * 16 + 16, c * 16:c * 16 + 16] = t
        TILE[name], tiles[name] = i, t
    for b, d in BDEF.items():
        tl = (d[1],) * 3 if isinstance(d[1], str) else d[1]
        TEXIDX[b] = [TILE[n] for n in tl]
        ICON_TILE[b] = TEXIDX[b, 1]
    for i, n in ITEM_TILE.items():
        ICON_TILE[i] = TILE[n]
    return atlas, tiles


def index_tiles():
    """Tile indices / per-block texture table (no image work, so worker processes can use it)."""
    for i, (name, fn) in enumerate(TILE_FUNCS):
        TILE[name] = i
    for b, d in BDEF.items():
        tl = (d[1],) * 3 if isinstance(d[1], str) else d[1]
        TEXIDX[b] = [TILE[n] for n in tl]
        ICON_TILE[b] = TEXIDX[b, 1]
    for i, n in ITEM_TILE.items():
        ICON_TILE[i] = TILE[n]


index_tiles()
TEXIDX_FANCY = TEXIDX.copy()
TEXIDX_FAST = TEXIDX.copy()
for _b in LEAF_IDS:
    TEXIDX_FAST[_b] = TILE[BDEF[_b][1] + '_f']


def np_tex(img, repeat=False):
    img = np.ascontiguousarray(img[::-1])
    t = Texture()
    t.setup2dTexture(img.shape[1], img.shape[0], Texture.TUnsignedByte, Texture.FRgba8)
    t.setRamImageAs(img.tobytes(), 'RGBA')
    t.setMagfilter(SamplerState.FTNearest)
    t.setMinfilter(SamplerState.FTNearest)
    wm = SamplerState.WMRepeat if repeat else SamplerState.WMClamp
    t.setWrapU(wm)
    t.setWrapV(wm)
    return t


def _iso_maps():
    P = np.stack([np.mgrid[0:32, 0:32][1], np.mgrid[0:32, 0:32][0]], -1).astype(np.float32) + .5
    out = []
    for (o, e1, e2), shade, fk in ((((1, 8), (15, -7), (15, 7)), 1.0, 0),
                                   (((1, 8), (15, 7), (0, 16)), .78, 1),
                                   (((16, 15), (15, -7), (0, 16)), .6, 1)):
        inv = np.linalg.inv(np.array([[e1[0], e2[0]], [e1[1], e2[1]]], np.float32))
        q = (P - o) @ inv.T
        m = (q[..., 0] >= 0) & (q[..., 0] < 1) & (q[..., 1] >= 0) & (q[..., 1] < 1)
        out.append((m, np.clip((q[..., 0] * 16).astype(int), 0, 15), np.clip((q[..., 1] * 16).astype(int), 0, 15), shade, fk))
    return out


def build_icons(tiles):
    """32x32 GUI icon texture for every placeable block / item."""
    maps, icons, names = _iso_maps(), {}, {v: k for k, v in TILE.items()}
    for it in CREATIVE_ITEMS:
        if isblk(it) and (CUBE[it] or it in (CHEST, BED) or it in SLABS):
            img = np.zeros((32, 32, 4), np.float32)
            for m, cu, cv, shade, fk in maps:
                tl = tiles[names[TEXIDX[it, fk]]].astype(np.float32)
                img[m] = tl[cv[m], cu[m]] * [shade, shade, shade, 1]
        else:
            img = np.repeat(np.repeat(tiles[names[ICON_TILE[it]]], 2, 0), 2, 1)
        icons[it] = np_tex(np.clip(img, 0, 255).astype(np.uint8))
    return icons


def _mask_img(rows, fill, edge=(30, 10, 10), half=False, empty=False):
    m = np.array([[c == '#' for c in row] for row in rows])
    img = np.zeros(m.shape + (4,), np.uint8)
    p = np.pad(m, 1)
    border = m & ~(p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    inner = m & ~border
    img[border] = (*edge, 255)
    img[inner] = (45, 25, 25, 255) if empty else (*fill, 255)
    if half:
        img[inner & (np.arange(m.shape[1]) >= m.shape[1] // 2)] = (45, 25, 25, 255)
    if not empty:
        img[2, 2] = (255, 220, 220, 255)
    return img


HEART = ['..##.##..', '.#######.', '#########', '#########', '.#######.', '..#####..', '...###...', '....#....', '.........']
FOODM = ['.....###.', '....#####', '...######', '...######', '...#####.', '..###....', '.#.......', '#........', '.........']


def gui_textures():
    g = {}
    g['heart'] = np_tex(_mask_img(HEART, (215, 20, 20)))
    g['heart_half'] = np_tex(_mask_img(HEART, (215, 20, 20), half=True))
    g['heart_empty'] = np_tex(_mask_img(HEART, (215, 20, 20), empty=True))
    g['food'] = np_tex(_mask_img(FOODM, (190, 110, 50), (60, 30, 10)))
    g['food_half'] = np_tex(_mask_img(FOODM, (190, 110, 50), (60, 30, 10), half=True))
    g['food_empty'] = np_tex(_mask_img(FOODM, (190, 110, 50), (60, 30, 10), empty=True))
    b = np.zeros((9, 9, 4), np.uint8)
    d = np.hypot(np.mgrid[0:9, 0:9][0] - 4, np.mgrid[0:9, 0:9][1] - 4)
    b[(d <= 4) & (d > 3)] = (60, 110, 220, 255)
    b[d <= 3] = (140, 190, 255, 160)
    b[2, 3] = (255, 255, 255, 255)
    g['bubble'] = np_tex(b)
    s = np.full((22, 22, 4), (55, 55, 55, 190), np.uint8)
    s[[0, -1], :] = s[:, [0, -1]] = (20, 20, 20, 255)
    s[1, 1:-1] = s[1:-1, 1] = (85, 85, 85, 230)
    g['slot'] = np_tex(s)
    s = np.zeros((24, 24, 4), np.uint8)
    s[[0, 1, -1, -2], :] = s[:, [0, 1, -1, -2]] = (240, 240, 240, 255)
    g['sel'] = np_tex(s)
    sun = np.zeros((16, 16, 4), np.uint8)
    sun[2:14, 2:14] = (255, 245, 170, 255)
    sun[4:12, 4:12] = (255, 255, 230, 255)
    g['sun'] = np_tex(sun)
    moon = np.zeros((16, 16, 4), np.uint8)
    moon[3:13, 3:13] = (215, 220, 235, 255)
    moon[5:7, 6:8] = moon[9:11, 9:12] = (170, 175, 190, 255)
    g['moon'] = np_tex(moon)
    return g

# ====================================================================== mesh helpers
_af = GeomVertexArrayFormat()
_af.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
_af.addColumn(InternalName.getColor(), 4, Geom.NTFloat32, Geom.CColor)
_af.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
FMT = GeomVertexFormat.registerFormat(_af)

FACES = [((1, 0, 0), np.array([(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)], np.float32), .8, 1),
         ((-1, 0, 0), np.array([(0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)], np.float32), .8, 1),
         ((0, 1, 0), np.array([(1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)], np.float32), .65, 1),
         ((0, -1, 0), np.array([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], np.float32), .65, 1),
         ((0, 0, 1), np.array([(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], np.float32), 1.0, 0),
         ((0, 0, -1), np.array([(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)], np.float32), .5, 2)]
CROSS = np.array([[(.15, .15, 0), (.85, .85, 0), (.85, .85, 1), (.15, .15, 1)],
                  [(.15, .85, 0), (.85, .15, 0), (.85, .15, 1), (.15, .85, 1)]], np.float32)
UVC = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], np.float32)
EPS = 1 / 2048.
AR = 32                       # atlas: 16 tiles wide, 32 tiles tall
TS = TSU = 1 / 16. - 2 * EPS
TSV = 1. / AR - 2 * EPS


def tile_uv(t):
    t = int(t)
    u, v = (t % 16) / 16., 1 - (t // 16 + 1) / AR
    return u + EPS, v + EPS, u + 1 / 16. - EPS, v + 1. / AR - EPS


def quads(pos, corners, tex, light, alpha=1.0):
    n = len(pos)
    v = pos[:, None, :].astype(np.float32) + corners[None]
    c = np.empty((n, 4, 4), np.float32)
    c[..., :3] = np.asarray(light, np.float32).reshape(-1, 1, 1)
    c[..., 3] = alpha
    tex = np.asarray(tex)
    uv = np.empty((n, 4, 2), np.float32)
    uv[..., 0] = ((tex % 16) / 16.)[:, None] + UVC[None, :, 0] * TSU + EPS
    uv[..., 1] = (1 - (tex // 16 + 1) / AR)[:, None] + UVC[None, :, 1] * TSV + EPS
    return v, c, uv


def make_geom(verts, cols, uvs):
    verts, cols, uvs = verts.reshape(-1, 3), cols.reshape(-1, 4), uvs.reshape(-1, 2)
    n = len(verts)
    data = np.empty((n, 9), np.float32)
    data[:, :3], data[:, 3:7], data[:, 7:] = verts, cols, uvs
    vd = GeomVertexData('m', FMT, Geom.UHStatic)
    vd.uncleanSetNumRows(n)
    vd.modifyArrayHandle(0).copyDataFrom(data)
    idx = (np.arange(n // 4, dtype=np.uint32)[:, None] * 4 + np.array([0, 1, 2, 0, 2, 3], np.uint32)).ravel()
    tr = GeomTriangles(Geom.UHStatic)
    tr.setIndexType(Geom.NTUint32)
    ia = tr.modifyVertices()
    ia.uncleanSetNumRows(len(idx))
    ia.modifyHandle().copyDataFrom(idx)
    g = Geom(vd)
    g.addPrimitive(tr)
    return g


def geom_np(verts, cols, uvs, name='g'):
    gn = GeomNode(name)
    gn.addGeom(make_geom(verts, cols, uvs))
    return NodePath(gn)


def cube_np(tex3, s=1.0, off=(0, 0, 0)):
    """Textured cube; tex3 = (top, side, bottom) tile indices."""
    vs, cs, us = [], [], []
    for d, corn, shade, fk in FACES:
        v, c, u = quads(np.zeros((1, 3), np.float32), corn * s + np.array(off, np.float32), [tex3[fk]], [shade])
        vs.append(v), cs.append(c), us.append(u)
    return geom_np(np.concatenate(vs), np.concatenate(cs), np.concatenate(us))


def box_np(parent, a, b, col):
    """Untextured coloured box from corner a to corner b."""
    a, b = np.array(a, np.float32), np.array(b, np.float32)
    vs, cs = [], []
    for d, corn, shade, fk in FACES:
        vs.append(a + corn * (b - a))
        cs.append(np.array([[col[0] * shade, col[1] * shade, col[2] * shade, 1]] * 4, np.float32))
    n = geom_np(np.array(vs), np.array(cs), np.zeros((24, 2), np.float32))
    n.reparentTo(parent)
    return n


# ====================================================================== noise
G2X = np.array([1, -1, 1, -1, 1, -1, 0, 0], np.float64)
G2Y = np.array([1, 1, -1, -1, 0, 0, 1, -1], np.float64)


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


class Noise:
    def __init__(self, seed):
        p = np.random.RandomState(seed & 0xffffffff).permutation(256).astype(np.int64)
        self.p = np.concatenate([p, p])

    def n2(self, x, y):
        xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        u, v, p = _fade(xf), _fade(yf), self.p
        a, b = p[xi] + yi, p[xi + 1] + yi

        def g(h, x, y):
            h = h & 7
            return G2X[h] * x + G2Y[h] * y
        n00, n01 = g(p[a], xf, yf), g(p[a + 1], xf, yf - 1)
        n10, n11 = g(p[b], xf - 1, yf), g(p[b + 1], xf - 1, yf - 1)
        x0, x1 = n00 + u * (n10 - n00), n01 + u * (n11 - n01)
        return x0 + v * (x1 - x0)

    def n3(self, x, y, z):
        xi, yi, zi = (np.floor(q).astype(np.int64) for q in (x, y, z))
        xf, yf, zf = x - xi, y - yi, z - zi
        xi, yi, zi = xi & 255, yi & 255, zi & 255
        u, v, w, p = _fade(xf), _fade(yf), _fade(zf), self.p
        A, B = p[xi] + yi, p[xi + 1] + yi
        AA, AB, BA, BB = p[A] + zi, p[A + 1] + zi, p[B] + zi, p[B + 1] + zi

        def g(h, x, y, z):
            h = h & 15
            uu = np.where(h < 8, x, y)
            vv = np.where(h < 4, y, np.where((h == 12) | (h == 14), x, z))
            return np.where(h & 1, -uu, uu) + np.where(h & 2, -vv, vv)

        def L(a, b, t):
            return a + t * (b - a)
        return L(L(L(g(p[AA], xf, yf, zf), g(p[BA], xf - 1, yf, zf), u),
                   L(g(p[AB], xf, yf - 1, zf), g(p[BB], xf - 1, yf - 1, zf), u), v),
                 L(L(g(p[AA + 1], xf, yf, zf - 1), g(p[BA + 1], xf - 1, yf, zf - 1), u),
                   L(g(p[AB + 1], xf, yf - 1, zf - 1), g(p[BB + 1], xf - 1, yf - 1, zf - 1), u), v), w)

    def fbm2(self, x, y, octaves):
        s, amp, f, tot = 0, 1., 1., 0
        for _ in range(octaves):
            s = s + amp * self.n2(x * f, y * f)
            tot += amp
            amp *= .5
            f *= 2
        return s / tot


# ====================================================================== terrain
PLAINS_B, DESERT_B, SNOW_B, FOREST_B, BADLANDS_B, TAIGA_B, AUTUMN_B = range(7)
BIOME_NAMES = ('Plains', 'Desert', 'Snowy Tundra', 'Forest', 'Badlands', 'Taiga', 'Autumn Woods')
BAND = np.array([TERRACOTTA, TERRACOTTA_RED, TERRACOTTA, TERRACOTTA_YELLOW, TERRACOTTA, TERRACOTTA,
                 TERRACOTTA_RED, TERRACOTTA, TERRACOTTA_YELLOW, TERRACOTTA_RED, TERRACOTTA, TERRACOTTA], np.uint8)
NOT_LEAF_TARGET = _mask([AIR, TALL_GRASS, FERN, FLOWER_RED, FLOWER_YELLOW, BLUE_ORCHID, DEAD_BUSH])


def tree_shape(kind, th, rv):
    """Relative (dx, dy, dz, block) list. 0 oak, 1 birch, 2 spruce, 3 autumn, 4 big oak, 5 cherry, 6 palm, 7 dead."""
    out = []
    if kind == 4:
        th += 3
        out += [(0, 0, z, LOG) for z in range(th)]
        for cx, cy, cz, r in ((0, 0, th, 3.2), (2, 1, th - 2, 2.3), (-2, -1, th - 1, 2.3), (1, -2, th - 3, 2.)):
            R = int(math.ceil(r))
            for dx in range(-R, R + 1):
                for dy in range(-R, R + 1):
                    for dz in range(-R + 1, R):
                        if dx * dx + dy * dy + dz * dz * 1.6 <= r * r and (dx + dy * 3 + dz + int(rv * 50)) % 7:
                            out.append((cx + dx, cy + dy, cz + dz, LEAVES))
            if (cx, cy) != (0, 0):
                out += [(int(cx * f), int(cy * f), cz - 1, LOG) for f in (.5, 1.)]
        return out
    if kind == 5:
        th = 4 + (th > 5)
        lean = 1 if rv > .5 else -1
        trunk = [(lean * (z > th // 2), 0, z) for z in range(th)]
        out += [(x, y, z, CHERRY_LOG) for x, y, z in trunk]
        tx = lean
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                for dz in (0, 1):
                    e = (dx / 4.2) ** 2 + (dy / 4.2) ** 2 + (dz / 1.5) ** 2
                    if e <= 1:
                        out.append((tx + dx, dy, th + dz, CHERRY_LEAVES))
                if 3.4 < math.hypot(dx, dy) <= 4 and (dx * 5 + dy * 3) % 3 == 0:
                    out.append((tx + dx, dy, th - 1, CHERRY_LEAVES))
        return out
    if kind == 6:
        th += 2
        bend = 1 if rv > .5 else -1
        pos = [(int(bend * z * z / 22.), 0, z) for z in range(th)]
        out += [(x, y, z, PALM_LOG) for x, y, z in pos]
        tx, ty, tz = pos[-1]
        out.append((tx, ty, tz + 1, PALM_LEAVES))
        for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            for k in range(1, 4):
                out.append((tx + ddx * k, ty + ddy * k, tz + 1 - (k == 3), PALM_LEAVES))
        return out
    if kind == 7:
        th = 3 + int(rv * 3)
        out += [(0, 0, z, LOG) for z in range(th)]
        for ddx, ddy in ((1, 0), (-1, 1), (0, -1))[:2 + int(rv * 2)]:
            out += [(ddx * k, ddy * k, th - 2 + k, LOG) for k in range(1, 3)]
        return out
    if kind == 2:
        th += 2
        for lz in range(2, th + 2):
            d = th + 1 - lz
            rad = 0 if d == 0 else (1 if d % 2 == 1 else min(3, 1 + d // 3))
            for dx in range(-rad, rad + 1):
                for dy in range(-rad, rad + 1):
                    if abs(dx) + abs(dy) <= rad + (rad > 1):
                        out.append((dx, dy, lz, SPRUCE_LEAVES))
        out += [(0, 0, z, SPRUCE_LOG) for z in range(th)]
        return out
    log, lf = ((LOG, LEAVES), (BIRCH_LOG, BIRCH_LEAVES), None, (LOG, AUTUMN_LEAVES))[kind]
    top = th - 1
    for lz in range(top - 2, top + 2):
        rad = 2 if lz < top else 1
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                if abs(dx) == rad and abs(dy) == rad and (lz >= top or (dx * 7 + dy * 13 + lz + int(rv * 100)) % 3 == 0):
                    continue
                out.append((dx, dy, lz, lf))
    out += [(0, 0, z, log) for z in range(top + 1)]
    return out


class TerrainGen:
    RS = 64                      # structure region size

    def __init__(self, seed):
        self.seed = seed
        self.nh, self.nd, self.nm, self.nt, self.nw, self.nc, self.ns = (Noise(seed + i) for i in range(7))
        self.lock = threading.Lock()
        self.struct_cache, self.bcache = {}, {}

    def columns(self, X, Y):
        cont = self.nh.fbm2(X / 320., Y / 320., 3)
        det = self.nd.fbm2(X / 80., Y / 80., 4)
        mnt = self.nm.fbm2(X / 220., Y / 220., 3)
        temp = self.nt.fbm2(X / 450., Y / 450., 2)
        hum = self.nw.fbm2(X / 350., Y / 350., 2)
        h = SEA + 5 + cont * 24 + det * 9 + np.maximum(0, mnt - .08) * 110
        bad = np.clip((temp - .2) / .08, 0, 1) * np.clip((hum - .05) / .08, 0, 1)
        h = h + bad * np.floor(np.clip(det * 22 + 9, 0, 15) / 3) * 3 * (h > SEA + 2)
        h = np.clip(h, 6, H - 12).astype(np.int64)
        biome = np.full(np.shape(X), PLAINS_B, np.int64)
        biome[hum > .05] = FOREST_B
        biome[(temp > .06) & (temp <= .2) & (hum > .12)] = AUTUMN_B
        biome[(temp >= -.17) & (temp < -.04) & (hum > -.1)] = TAIGA_B
        biome[temp < -.17] = SNOW_B
        biome[(temp > .2) & (hum < .05)] = DESERT_B
        biome[(temp > .2) & (hum >= .05)] = BADLANDS_B
        return h, biome, det

    def biome_at(self, x, y):
        key = (int(x) >> 2, int(y) >> 2)
        r = self.bcache.get(key)
        if r is None:
            h, b, _ = self.columns(np.array([float(x)]), np.array([float(y)]))
            r = (int(b[0]), int(h[0]))
            if len(self.bcache) > 50000:
                self.bcache.clear()
            self.bcache[key] = r
        return r

    def hash01(self, X, Y, salt):
        s = (self.seed * 7919 + salt * 104729) & 0x7fffffff
        h = (X.astype(np.int64) * 374761393 + Y.astype(np.int64) * 668265263 + s) & 0xffffffff
        h = ((h ^ (h >> 13)) * 1274126177) & 0xffffffff
        h ^= h >> 16
        return (h & 0xffffff) / 16777216.0

    def find_spawn(self):
        gx, gy = np.mgrid[-96:96:2, -96:96:2]
        h, b, _ = self.columns(gx.astype(float), gy.astype(float))
        d = np.where((h > SEA + 1) & (h < SEA + 20), gx ** 2 + gy ** 2, 10 ** 12)
        i = np.unravel_index(np.argmin(d), d.shape)
        return int(gx[i]) + .5, int(gy[i]) + .5

    def chunk(self, cx, cy):
        x0, y0, M = cx * CS, cy * CS, 3
        gx, gy = np.mgrid[x0 - M:x0 + 16 + M, y0 - M:y0 + 16 + M]
        HH, BB, DD = self.columns(gx.astype(float), gy.astype(float))
        S = slice(M, M + 16)
        h, bio, det = HH[S, S], BB[S, S], DD[S, S]
        rng = np.random.RandomState((self.seed * 31 + cx * 73856093 ^ cy * 19349663) & 0xffffffff)
        Z = np.arange(H)[None, None, :]
        hh = h[:, :, None]
        desert, snow, bad = bio == DESERT_B, bio == SNOW_B, bio == BADLANDS_B
        top = np.full((16, 16), GRASS, np.uint8)
        fill = np.full((16, 16), DIRT, np.uint8)
        top[desert] = fill[desert] = SAND
        top[snow] = SNOWY_GRASS
        top[bad] = RED_SAND
        beach = h <= SEA + 1
        top[beach] = fill[beach] = SAND
        top[beach & bad] = fill[beach & bad] = RED_SAND
        under = h < SEA - 1
        top[under & (det > .15)] = GRAVEL
        top[under & (det < -.25)] = CLAY
        mount = (h > SEA + 26) & ~bad
        top[mount] = fill[mount] = STONE
        top[(h > SEA + 38) & ~bad] = SNOW
        blk = np.zeros((CS, CS, H), np.uint8)
        blk[Z <= hh] = STONE
        dz = (10 + self.ns.n2((gx[S, S]) / 40., (gy[S, S]) / 40.) * 6).astype(np.int64)
        blk[(Z < dz[:, :, None]) & (blk == STONE)] = DEEPSLATE
        cg = (gx[S, S][::2, ::2, None] / 16., gy[S, S][::2, ::2, None] / 16., np.arange(0, H, 2)[None, None, :] / 10.)
        v1 = np.repeat(np.repeat(np.repeat(self.ns.n3(*cg), 2, 0), 2, 1), 2, 2)
        v2 = np.repeat(np.repeat(np.repeat(self.ns.n3(cg[0] + 50, cg[1] + 50, cg[2] + 50), 2, 0), 2, 1), 2, 2)
        st = blk == STONE
        blk[st & (v1 > .5)] = GRANITE
        blk[st & (v1 < -.5)] = DIORITE
        blk[st & (v2 > .52) & (np.abs(v1) <= .5)] = ANDESITE
        blk = np.where((Z > hh - 4) & (Z < hh), fill[:, :, None], blk)
        blk = np.where(Z == hh, top[:, :, None], blk)
        blk[(Z > hh - 7) & (Z <= hh - 4) & desert[:, :, None]] = SANDSTONE
        bandm = (Z > hh - 18) & (Z < hh) & bad[:, :, None] & ~beach[:, :, None]
        blk[bandm] = np.broadcast_to(BAND[np.arange(H) % 12][None, None, :], blk.shape)[bandm]
        blk[(Z > hh) & (Z <= SEA)] = WATER
        blk[(Z == SEA) & (hh < SEA) & snow[:, :, None]] = ICE
        blk[:, :, 0] = BEDROCK
        blk[:, :, 1][rng.rand(16, 16) < .5] = BEDROCK
        blk[:, :, 2][rng.rand(16, 16) < .2] = BEDROCK
        # caves: spaghetti tunnels + big caverns, lava at the bottom
        X3, Y3, Z3 = gx[S, S, None].astype(float), gy[S, S, None].astype(float), Z.astype(float)
        a = self.nc.n3(X3 / 32., Y3 / 32., Z3 / 20.)
        b = self.nc.n3(X3 / 32. + 100, Y3 / 32. + 50, Z3 / 20. + 30)
        cave = (a * a + b * b) < .006
        cave |= (self.nh.n3(X3 / 70., Y3 / 70., Z3 / 35.) > .36) & (Z3 < 30)
        cave &= (Z > 2) & (Z <= hh) & ~((hh <= SEA + 2) & (Z >= SEA - 6)) & (blk != WATER)
        blk[cave & (Z <= 8)] = LAVA
        blk[cave & (Z > 8)] = AIR
        # ores and pockets
        for ore, n, zmin, zmax, size in ((COAL_ORE, 14, 3, 80, 8), (IRON_ORE, 9, 3, 56, 6), (GOLD_ORE, 3, 3, 30, 5),
                                         (DIAMOND_ORE, 2, 3, 15, 4), (EMERALD_ORE, 2, SEA + 20, H - 12, 3),
                                         (GRAVEL, 3, 3, 70, 14), (DIRT, 3, 3, 70, 14)):
            for _ in range(n):
                x, y, z = rng.randint(0, 16), rng.randint(0, 16), rng.randint(zmin, zmax)
                for _ in range(size):
                    if blk[x, y, z] in (STONE, DEEPSLATE, GRANITE, DIORITE, ANDESITE):
                        blk[x, y, z] = ore
                    x = min(15, max(0, x + rng.randint(-1, 2)))
                    y = min(15, max(0, y + rng.randint(-1, 2)))
                    z = min(H - 1, max(1, z + rng.randint(-1, 2)))
        # cave decoration
        air = blk == AIR
        zero = np.zeros((16, 16, 1), bool)
        floor = air & np.concatenate([zero, OPAQUE[blk[:, :, :-1]]], 2) & (Z < hh - 4)
        ceil = air & np.concatenate([OPAQUE[blk[:, :, 1:]], zero], 2) & (Z < hh - 4)
        R = rng.rand(16, 16, H)
        blk[floor & (R < .014) & (Z < 36)] = GLOWSHROOM
        blk[floor & (R >= .014) & (R < .022)] = BROWN_MUSHROOM
        blk[floor & (R >= .022) & (R < .027)] = RED_MUSHROOM
        blk[floor & (R >= .027) & (R < .037) & (Z < 24)] = CRYSTAL
        blk[ceil & ~floor & (R > .995)] = COBWEB
        # half-slab steps where the ground rises by exactly one block
        I, J = np.indices((16, 16))
        hc = np.minimum(h, H - 4)
        nmax = np.maximum.reduce([HH[M + 1:M + 17, S], HH[M - 1:M + 15, S], HH[S, M + 1:M + 17], HH[S, M - 1:M + 15]])
        tb, ab = blk[I, J, hc], blk[I, J, hc + 1]
        step = (nmax == h + 1) & (ab == AIR) & (h > SEA)
        for top_b, slab_b in ((GRASS, GRASS_SLAB), (SAND, SAND_SLAB), (STONE, STONE_SLAB)):
            m = step & (tb == top_b)
            blk[I[m], J[m], hc[m] + 1] = slab_b
        # surface plants
        tb, ab = blk[I, J, hc], blk[I, J, hc + 1]
        gxs, gys = gx[S, S], gy[S, S]
        pr, pr2, pr3 = self.hash01(gxs, gys, 5), self.hash01(gxs, gys, 6), self.hash01(gxs, gys, 7)
        ok = ab == AIR
        dens = np.select([bio == PLAINS_B, bio == FOREST_B, bio == AUTUMN_B, bio == TAIGA_B, bio == SNOW_B],
                         [.14, .1, .1, .13, .03], 0.)
        plant = np.full((16, 16), TALL_GRASS, np.uint8)
        plant[((bio == TAIGA_B) & (pr2 < .6)) | (((bio == FOREST_B) | (bio == AUTUMN_B)) & (pr2 < .25))] = FERN
        plant[pr2 > .9] = FLOWER_RED
        plant[pr2 > .95] = FLOWER_YELLOW
        plant[(pr2 > .985) & (bio != SNOW_B)] = BLUE_ORCHID
        forestish = (bio == FOREST_B) | (bio == TAIGA_B) | (bio == AUTUMN_B)
        plant[forestish & (pr2 > .85) & (pr2 < .875)] = BROWN_MUSHROOM
        plant[forestish & (pr2 >= .875) & (pr2 < .9)] = RED_MUSHROOM
        m = ok & ((tb == GRASS) | (tb == SNOWY_GRASS)) & (pr < dens)
        blk[I[m], J[m], hc[m] + 1] = plant[m]
        sandy = (tb == SAND) | (tb == RED_SAND)
        m = ok & sandy & (desert | bad) & (pr < .008)
        blk[I[m], J[m], hc[m] + 1] = DEAD_BUSH
        m = ok & (tb == GRASS) & (pr > .997)
        blk[I[m], J[m], hc[m] + 1] = np.where(bio[m] == FOREST_B, MELON, PUMPKIN)
        for i, j in zip(*np.nonzero(ok & sandy & (desert | bad) & (pr > .008) & (pr < .013))):
            for k in range(1 + int(pr[i, j] * 1000) % 3):
                if blk[i, j, hc[i, j] + 1 + k] == AIR:
                    blk[i, j, hc[i, j] + 1 + k] = CACTUS
        Wm = HH < SEA
        adj = Wm[M + 1:M + 17, S] | Wm[M - 1:M + 15, S] | Wm[S, M + 1:M + 17] | Wm[S, M - 1:M + 15]
        for i, j in zip(*np.nonzero(ok & ((tb == GRASS) | sandy) & adj & (h >= SEA) & (pr3 < .14))):
            for k in range(1 + int(pr3[i, j] * 1000) % 3):
                blk[i, j, hc[i, j] + 1 + k] = SUGAR_CANE
        # trees (a 3 block margin so canopies cross chunk borders)
        r1, r2, r3 = self.hash01(gx, gy, 1), self.hash01(gx, gy, 2), self.hash01(gx, gy, 3)
        tdens = np.select([BB == FOREST_B, BB == AUTUMN_B, BB == TAIGA_B, BB == PLAINS_B, BB == SNOW_B],
                          [.045, .04, .05, .006, .012], 0.)
        trees = (r1 < tdens) & (HH > SEA + 1) & (HH <= SEA + 28)
        rects = self.surface_rects(cx, cy)
        cherry = self.hash01(gx // 40, gy // 40, 31) < .14
        palms = (r1 < .03) & (HH > SEA) & (HH <= SEA + 3) & ~np.isin(BB, (SNOW_B, TAIGA_B))
        dead = (r1 < .004) & (HH > SEA + 1) & np.isin(BB, (DESERT_B, BADLANDS_B))
        for i, j in zip(*np.nonzero(trees | palms | dead)):
            tx, ty = x0 - M + i, y0 - M + j
            if any(r[0] - 4 <= tx <= r[2] + 4 and r[1] - 4 <= ty <= r[3] + 4 for r in rects):
                continue
            bb, rr = BB[i, j], r2[i, j]
            if palms[i, j] and not trees[i, j]:
                kind = 6
            elif dead[i, j] and not trees[i, j]:
                kind = 7
            elif bb in (TAIGA_B, SNOW_B):
                kind = 2
            elif cherry[i, j] and bb in (PLAINS_B, FOREST_B):
                kind = 5
            elif bb == FOREST_B:
                kind = 1 if rr < .3 else (4 if rr < .42 else 0)
            elif bb == AUTUMN_B:
                kind = 1 if rr < .25 else 3
            else:
                kind = 4 if rr < .1 else 0
            self.put_shape(blk, i - M, j - M, int(HH[i, j]) + 1, tree_shape(kind, 4 + int(r3[i, j] * 3), r2[i, j]))
        self.decorate_rocks(blk, h, bio, rng, gxs, gys)
        self.apply_structures(blk, cx, cy)
        return blk

    @staticmethod
    def put_shape(blk, x, y, z, shape):
        for dx, dy, dz, b in shape:
            xx, yy, zz = x + dx, y + dy, z + dz
            if 0 <= xx < 16 and 0 <= yy < 16 and 0 < zz < H:
                if b in LEAF_IDS:
                    if NOT_LEAF_TARGET[blk[xx, yy, zz]]:
                        blk[xx, yy, zz] = b
                elif blk[xx, yy, zz] != BEDROCK:
                    blk[xx, yy, zz] = b

    def surface_rects(self, cx, cy):
        x0, y0, RS = cx * CS, cy * CS, self.RS
        out = []
        for rx in range((x0 - 40) // RS, (x0 + 56) // RS + 1):
            for ry in range((y0 - 40) // RS, (y0 + 56) // RS + 1):
                for st in self.region_structures(rx, ry):
                    if st[0] not in ('dungeon', 'mineshaft', 'sky'):
                        xs, ys = st[1][0], st[1][1]
                        out.append((xs.min(), ys.min(), xs.max(), ys.max()))
        return out

    def apply_structures(self, blk, cx, cy):
        x0, y0, RS = cx * CS, cy * CS, self.RS
        for rx in range((x0 - 40) // RS, (x0 + 56) // RS + 1):
            for ry in range((y0 - 40) // RS, (y0 + 56) // RS + 1):
                for st in self.region_structures(rx, ry):
                    xs, ys, zs, vs = st[1]
                    m = (xs >= x0) & (xs < x0 + 16) & (ys >= y0) & (ys < y0 + 16)
                    if m.any():
                        blk[xs[m] - x0, ys[m] - y0, zs[m]] = vs[m]

# ====================================================================== structures
class SB:
    """Sparse structure builder in world coordinates."""

    def __init__(self):
        self.b = {}

    def set(self, x, y, z, v):
        if 0 < z < H - 1:
            self.b[(x, y, z)] = v

    def fill(self, x0, y0, z0, x1, y1, z1, v):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    self.set(x, y, z, v)

    def arrays(self):
        k = np.array(list(self.b.keys()), np.int64)
        return k[:, 0], k[:, 1], k[:, 2], np.array(list(self.b.values()), np.uint8)


SURFACE_TABLE = {DESERT_B: (('pyramid', .12), ('well', .2), ('camp', .24)),
                 SNOW_B: (('igloo', .16), ('tower', .21), ('camp', .25)),
                 PLAINS_B: (('cabin', .07), ('farm', .13), ('tower', .16), ('well', .19), ('ruins', .23), ('camp', .27)),
                 FOREST_B: (('cabin', .08), ('camp', .13), ('ruins', .17), ('tower', .2)),
                 AUTUMN_B: (('cabin', .08), ('camp', .13), ('ruins', .17), ('farm', .2)),
                 TAIGA_B: (('cabin', .1), ('camp', .15), ('ruins', .18), ('tower', .21)),
                 BADLANDS_B: (('ruins', .12), ('tower', .18))}
SURFACE_KINDS = ('cabin', 'tower', 'pyramid', 'well', 'igloo', 'ruins', 'sky', 'camp', 'farm')


def _region_structures(self, rx, ry):
    with self.lock:
        r = self.struct_cache.get((rx, ry))
    if r is not None:
        return r
    out, RS = [], self.RS
    rng = random.Random((self.seed * 1000003) ^ (rx * 73856093) ^ (ry * 19349663))
    ox, oy = rx * RS + rng.randint(12, RS - 12), ry * RS + rng.randint(12, RS - 12)
    biome, h = self.biome_at(ox, oy)
    roll, kind = rng.random(), None
    silly = biome == SILLY_B
    if not silly and SEA < h <= SEA + 3 and roll < .22:
        kind = 'lighthouse'
    elif h > SEA + 1:
        for k, p in SURFACE_TABLE[biome]:
            if roll < p:
                kind = k
                break
    if kind:                                         # only on fairly flat, low ground
        rr = 9 if kind == 'pyramid' else 6
        hm = self.footprint(ox - rr, oy - rr, ox + rr, oy + rr)[2]
        if hm.max() - hm.min() > (5 if kind == 'pyramid' else (4 if kind == 'lighthouse' else 3)) or \
                hm.max() > SEA + 24 or (hm.min() <= SEA and kind != 'lighthouse'):
            kind = None
    if kind is None and roll > .95 and h < 62 and not silly:
        kind = 'sky'
    rng2 = random.Random((self.seed * 7368787) ^ (rx * 2654435761) ^ (ry * 40503) ^ 0x5eed)
    if not silly and biome in (PLAINS_B, DESERT_B, TAIGA_B, SNOW_B) and rng2.random() < .1:
        hm = self.footprint(ox - 16, oy - 16, ox + 16, oy + 16)[2]
        if hm.max() - hm.min() <= 7 and hm.min() > SEA and hm.max() <= SEA + 24:
            kind = 'village'
    if silly and rng2.random() < .06:
        kind = 'jelly_throne'
    jobs = [kind] if kind else []
    if rng.random() < .3 and not silly:
        jobs.append('dungeon')
    if rng.random() < .12 and not silly:
        jobs.append('mineshaft')
    extra = ([] if silly else (['geode'] if rng2.random() < .16 else []) + (['cave_outpost'] if rng2.random() < .1 else []))
    for i, k in enumerate(jobs + extra):
        sb = SB()
        if i >= len(jobs):
            ax, ay = rx * RS + rng2.randint(12, RS - 12), ry * RS + rng2.randint(12, RS - 12)
        else:
            ax, ay = (ox, oy) if i == 0 else (rx * RS + rng.randint(12, RS - 12), ry * RS + rng.randint(12, RS - 12))
        center = getattr(self, 'build_' + k)(sb, ax, ay, biome, rng)
        if center and sb.b:
            out.append((k, sb.arrays(), center))
    with self.lock:
        if len(self.struct_cache) > 500:
            self.struct_cache.clear()
        self.struct_cache[(rx, ry)] = out
    return out


def _footprint(self, x0, y0, x1, y1):
    gx, gy = np.mgrid[x0:x1 + 1, y0:y1 + 1]
    hm, _, _ = self.columns(gx.astype(float), gy.astype(float))
    return gx, gy, hm


def _found(self, sb, x0, y0, x1, y1, z0, mat, clear):
    """Fill from terrain up to the floor and clear the space above it."""
    gx, gy, hm = self.footprint(x0, y0, x1, y1)
    for x, y, th in zip(gx.ravel(), gy.ravel(), hm.ravel()):
        for z in range(min(int(th) + 1, z0), z0):
            sb.set(int(x), int(y), z, mat)
        for z in range(z0, z0 + clear):
            sb.set(int(x), int(y), z, AIR)
    return hm


def _base_z(self, x0, y0, x1, y1):
    return int(np.median(self.footprint(x0, y0, x1, y1)[2])) + 1


def _build_cabin(self, sb, ox, oy, biome, rng):
    hx, hy = rng.choice((2, 3, 3, 4)), rng.choice((3, 4, 4, 5))
    x0, y0, x1, y1 = ox - hx, oy - hy, ox + hx, oy + hy
    z0 = self.base_z(x0, y0, x1, y1)
    wood = {TAIGA_B: SPRUCE_PLANKS, SNOW_B: SPRUCE_PLANKS, AUTUMN_B: BIRCH_PLANKS}.get(biome, PLANKS)
    log = {SPRUCE_PLANKS: SPRUCE_LOG, BIRCH_PLANKS: BIRCH_LOG}.get(wood, LOG)
    style = rng.randint(0, 2)
    wall = (wood, wood, BRICKS)[style]
    base = (wood, COBBLE, STONE_BRICKS)[style]
    roof = rng.choice((SPRUCE_PLANKS, PLANKS, BRICKS, STONE_BRICKS, BIRCH_PLANKS) if wood != SPRUCE_PLANKS else
                      (PLANKS, COBBLE, STONE_BRICKS))
    tall = 4 if rng.random() < .7 else 5
    self.found(sb, x0 - 2, y0 - 3, x1 + 2, y1 + 2, z0, DIRT, 13)
    sb.fill(x0 - 1, y0 - 2, z0 - 1, x1 + 1, y1 + 1, z0 - 1, COBBLE)
    sb.fill(x0, y0, z0 - 1, x1, y1, z0 - 1, wood)
    sb.fill(x0, y0, z0, x1, y1, z0 + tall - 1, wall)
    sb.fill(x0, y0, z0, x1, y1, z0, base)
    sb.fill(x0 + 1, y0 + 1, z0, x1 - 1, y1 - 1, z0 + tall - 1, AIR)
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        sb.fill(x, y, z0 - 1, x, y, z0 + tall - 1, log)
    for y in range(y0 + 2, y1 - 1, 3):
        for x in (x0, x1):
            sb.fill(x, y, z0 + 1, x, y, z0 + 2, GLASS)
    sb.fill(ox, y1, z0 + 1, ox, y1, z0 + 2, GLASS)
    sb.fill(ox, y0, z0, ox, y0, z0 + 1, AIR)
    for k in range(hx + 2):
        sb.fill(x0 - 1 + k, y0 - 1, z0 + tall + k, x1 + 1 - k, y1 + 1, z0 + tall + k, roof)
    spots = [(x0 + 1, y1 - 1), (x1 - 1, y1 - 1), (x1 - 1, y0 + 2), (x0 + 1, y0 + 3), (x1 - 1, oy)]
    rng.shuffle(spots)
    for (x, y), b in zip(spots, (CHEST, CRAFTING, BOOKSHELF, rng.choice((BOOKSHELF, PUMPKIN, MELON, CRAFTING)))):
        sb.set(x, y, z0, b)
    sb.set(x0 + 1, y0 + 1, z0, BED)
    sb.set(x0 + 1, y0 + 2, z0, BED_HEAD)
    sb.set(x0 + 1, oy, z0 + 2, WALL_TORCH)
    sb.set(x1 - 1, oy - 1, z0 + 2, WALL_TORCH)
    sb.set(ox, oy, z0 + tall - 1, LANTERN)
    if rng.random() < .6:                                   # porch lanterns under the overhang
        sb.set(x0, y0 - 1, z0 + tall - 1, LANTERN)
        sb.set(x1, y0 - 1, z0 + tall - 1, LANTERN)
    if rng.random() < .45:                                  # chimney with a glowing hearth
        cx, cy = x1 - 1, y1 - 1
        sb.set(cx, cy, z0, MAGMA)
        sb.fill(cx, cy, z0 + 1, cx, cy, z0 + tall + hx + 2, BRICKS)
    for k in range(1, 4):
        sb.set(ox, y0 - k, z0 - 1, GRAVEL)
    for _ in range(4):
        fx, fy = rng.randint(x0 - 2, x1 + 2), y0 - 2
        sb.set(fx, fy, z0, rng.choice((FLOWER_RED, FLOWER_YELLOW, BLUE_ORCHID)))
        sb.set(fx, fy, z0 - 1, GRASS)
    return (ox, oy, z0)


def _build_camp(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 5, oy - 5, ox + 5, oy + 5)
    ground = SAND if biome == DESERT_B else (SNOWY_GRASS if biome == SNOW_B else GRASS)
    self.found(sb, ox - 7, oy - 7, ox + 7, oy + 7, z0, DIRT, 7)
    for dx in range(-7, 8):
        for dy in range(-7, 8):
            sb.set(ox + dx, oy + dy, z0 - 1, ground)
    sb.fill(ox - 1, oy - 1, z0 - 1, ox + 1, oy + 1, z0 - 1, COBBLE)
    sb.set(ox, oy, z0 - 1, MAGMA)
    for dx, dy in ((3, 0), (-3, 0), (0, 3)):
        sb.set(ox + dx, oy + dy, z0, rng.choice((LOG, SPRUCE_LOG)))
    for tx, ty in ((ox - 4, oy - 4), (ox + 4, oy - 4)):
        wool = rng.choice((WOOL_RED, WOOL_BLUE, WOOL_GREEN, WOOL_YELLOW, WOOL_WHITE))
        for y in range(ty - 2, ty + 2):
            for k, w in ((0, 2), (1, 1), (2, 0)):
                sb.set(tx - w, y, z0 + k, wool)
                sb.set(tx + w, y, z0 + k, wool)
    sb.set(ox - 4, oy - 5, z0, CHEST)
    sb.set(ox + 3, oy, z0 + 1, LANTERN)
    sb.set(ox + 4, oy - 5, z0, CRAFTING)
    return (ox, oy, z0)


def _build_farm(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 5, oy - 5, ox + 5, oy + 5)
    self.found(sb, ox - 6, oy - 6, ox + 6, oy + 6, z0, DIRT, 7)
    for dx in range(-5, 6):
        for dy in range(-5, 6):
            edge = abs(dx) == 5 or abs(dy) == 5
            sb.set(ox + dx, oy + dy, z0 - 1, LOG if edge else (WATER if dy == 0 else FARMLAND))
            if not edge and dy != 0:
                sb.set(ox + dx, oy + dy, z0, rng.choice((WHEAT1, WHEAT2, WHEAT3, WHEAT3)))
    for dx, dy in ((-5, -5), (5, -5), (-5, 5), (5, 5)):
        sb.set(ox + dx, oy + dy, z0, COBBLE)
        sb.set(ox + dx, oy + dy, z0 + 1, LANTERN)
    sx, sy = ox + 2, oy + 2                               # scarecrow
    sb.set(sx, sy, z0, LOG)
    sb.set(sx, sy, z0 + 1, LOG)
    sb.set(sx, sy, z0 + 2, JACK_O_LANTERN if rng.random() < .5 else PUMPKIN)
    sb.set(sx - 1, sy, z0 + 1, WOOL_RED)
    sb.set(sx + 1, sy, z0 + 1, WOOL_RED)
    sb.set(ox - 6, oy, z0, CHEST)
    return (ox, oy, z0)


def _build_tower(self, sb, ox, oy, biome, rng):
    x0, y0, x1, y1 = ox - 2, oy - 2, ox + 2, oy + 2
    z0 = self.base_z(x0, y0, x1, y1)
    ht = 11 + rng.randint(0, 3)
    mats = [STONE_BRICKS] * 5 + [MOSSY_STONE_BRICKS] * 2 + [CRACKED_STONE_BRICKS] * 2
    self.found(sb, x0 - 1, y0 - 1, x1 + 1, y1 + 1, z0, COBBLE, ht + 3)
    sb.fill(x0, y0, z0 - 1, x1, y1, z0 - 1, STONE_BRICKS)
    for z in range(z0, z0 + ht):
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                if x in (x0, x1) or y in (y0, y1):
                    if z > z0 + 6 and rng.random() < .1:
                        continue
                    sb.set(x, y, z, rng.choice(mats))
    sb.fill(ox, y0, z0, ox, y0, z0 + 1, AIR)
    for x, y in ((x0, oy), (x1, oy), (ox, y1)):
        sb.set(x, y, z0 + 5, AIR)
    ring = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    zp = z0 + ht - 1
    sb.fill(x0 + 1, y0 + 1, zp, x1 - 1, y1 - 1, zp, STONE_BRICKS)
    for k in range(ht - 1):
        dx, dy = ring[k % 8]
        sb.set(ox + dx, oy + dy, z0 + k, rng.choice(mats))
    for k in (ht - 2, ht - 3):
        dx, dy = ring[k % 8]
        sb.set(ox + dx, oy + dy, zp, AIR)
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            if (x in (x0, x1) or y in (y0, y1)) and (x + y) % 2 == 0:
                sb.set(x, y, zp + 1, STONE_BRICKS)
    free = [(dx, dy) for dx, dy in ring if (dx, dy) not in (ring[(ht - 2) % 8], ring[(ht - 3) % 8])]
    cx, cy = free[0]
    sb.set(ox + cx, oy + cy, zp + 1, CHEST)
    cx, cy = free[3]
    sb.set(ox + cx, oy + cy, zp + 1, LANTERN)
    sb.set(x0, oy, z0 + 3, AIR)
    return (ox, oy, z0)


def _build_pyramid(self, sb, ox, oy, biome, rng):
    gx, gy, hm = self.footprint(ox - 9, oy - 9, ox + 9, oy + 9)
    z0 = int(hm.min()) + 1
    self.found(sb, ox - 9, oy - 9, ox + 9, oy + 9, z0, SANDSTONE, 12)
    for k in range(10):
        sb.fill(ox - 9 + k, oy - 9 + k, z0 + k, ox + 9 - k, oy + 9 - k, z0 + k, SANDSTONE)
    for k in range(0, 9, 3):
        sb.fill(ox - 9 + k, oy - 9 + k, z0 + k, ox + 9 - k, oy - 9 + k, z0 + k, TERRACOTTA_YELLOW)
    sb.fill(ox - 3, oy - 3, z0 + 1, ox + 3, oy + 3, z0 + 4, AIR)
    sb.fill(ox, oy - 9, z0 + 1, ox, oy - 4, z0 + 2, AIR)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            sb.set(ox + dx, oy + dy, z0, WOOL_BLUE if (dx, dy) == (0, 0) else
                   (TERRACOTTA_RED if abs(dx) == abs(dy) else TERRACOTTA_YELLOW))
    for dx, dy in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
        sb.set(ox + dx, oy + dy, z0 + 1, LANTERN)
    sb.fill(ox - 2, oy - 2, z0 - 5, ox + 2, oy + 2, z0 - 1, SANDSTONE)
    sb.fill(ox - 1, oy - 1, z0 - 4, ox + 1, oy + 1, z0 - 2, AIR)
    sb.set(ox, oy, z0 - 1, WOOL_BLUE)
    sb.set(ox - 1, oy - 1, z0 - 4, CHEST)
    sb.set(ox + 1, oy + 1, z0 - 4, CHEST)
    sb.set(ox + 1, oy - 1, z0 - 4, GLOWSTONE)
    sb.set(ox, oy, z0 - 5, TNT)
    return (ox, oy, z0)


def _build_well(self, sb, ox, oy, biome, rng):
    x0, y0, x1, y1 = ox - 2, oy - 2, ox + 1, oy + 1
    z0 = self.base_z(x0, y0, x1, y1)
    mat = SANDSTONE if biome == DESERT_B else COBBLE
    self.found(sb, x0 - 1, y0 - 1, x1 + 1, y1 + 1, z0, mat, 6)
    sb.fill(x0, y0, z0 - 4, x1, y1, z0, mat)
    sb.fill(x0 + 1, y0 + 1, z0 - 3, x1 - 1, y1 - 1, z0 - 1, WATER)
    sb.fill(x0 + 1, y0 + 1, z0, x1 - 1, y1 - 1, z0, AIR)
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        sb.fill(x, y, z0 + 1, x, y, z0 + 2, mat)
    sb.fill(x0, y0, z0 + 3, x1, y1, z0 + 3, mat)
    sb.set(ox, oy, z0 + 2, LANTERN)
    return (ox, oy, z0)


def _build_igloo(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 3, oy - 3, ox + 3, oy + 3)
    self.found(sb, ox - 6, oy - 7, ox + 6, oy + 6, z0, SNOW, 12)
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            sb.set(ox + dx, oy + dy, z0 - 1, SNOW)
            for dz in range(0, 5):
                d = math.sqrt(dx * dx + dy * dy + (dz * 1.2) ** 2)
                if 2.6 < d <= 3.7:
                    sb.set(ox + dx, oy + dy, z0 + dz, SNOW)
    for y in (oy - 3, oy - 4):
        sb.fill(ox, y, z0, ox, y, z0 + 1, AIR)
        sb.fill(ox - 1, y, z0, ox - 1, y, z0 + 1, SNOW)
        sb.fill(ox + 1, y, z0, ox + 1, y, z0 + 1, SNOW)
        sb.set(ox, y, z0 + 2, SNOW)
    sb.set(ox - 1, oy, z0, BED)
    sb.set(ox - 1, oy + 1, z0, BED_HEAD)
    sb.set(ox + 1, oy + 1, z0, CRAFTING)
    sb.set(ox + 1, oy - 1, z0, LANTERN)
    sb.set(ox - 1, oy - 1, z0, CHEST)
    sb.set(ox, oy + 2, z0 - 1, ICE)
    return (ox, oy, z0)


def _build_ruins(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 7, oy - 7, ox + 7, oy + 7)
    self.found(sb, ox - 8, oy - 8, ox + 8, oy + 8, z0, STONE_BRICKS, 8)
    for dx in range(-8, 9):
        for dy in range(-8, 9):
            if dx * dx + dy * dy <= 64:
                r = rng.random()
                sb.set(ox + dx, oy + dy, z0 - 1, GRASS if r < .45 else (MOSSY if r < .65 else
                       (MOSSY_STONE_BRICKS if r < .82 else (CRACKED_STONE_BRICKS if r < .92 else STONE_BRICKS))))
    for i in range(8):
        a = i * math.pi / 4
        px, py = ox + int(round(math.cos(a) * 6)), oy + int(round(math.sin(a) * 6))
        ht = rng.randint(1, 5)
        for z in range(z0, z0 + ht):
            sb.set(px, py, z, rng.choice((STONE_BRICKS, MOSSY_STONE_BRICKS, CRACKED_STONE_BRICKS)))
        if ht >= 4 and rng.random() < .6:
            sb.set(px, py, z0 + ht, LANTERN)
    sb.fill(ox - 1, oy - 1, z0, ox + 1, oy + 1, z0, OBSIDIAN)
    sb.set(ox, oy, z0 + 1, CHEST)
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        sb.set(ox + dx, oy + dy, z0 + 1, CRYSTAL)
    sb.set(ox, oy, z0 - 1, GLOWSTONE)
    return (ox, oy, z0)


def _build_sky(self, sb, ox, oy, biome, rng):
    zi, R = 72 + rng.randint(0, 5), 6 + rng.randint(0, 2)
    tops = {}
    for dx in range(-R, R + 1):
        for dy in range(-R, R + 1):
            d = math.hypot(dx, dy)
            if d > R - rng.random() * 1.2:
                continue
            depth = int((R - d) * 1.5) + 1 + rng.randint(0, 1)
            top = zi + (1 if d < R / 2 else 0)
            tops[(dx, dy)] = top
            for z in range(top - depth, top + 1):
                if z == top:
                    b = GRASS
                elif z > top - 3:
                    b = DIRT
                else:
                    r = rng.random()
                    b = GOLD_ORE if r < .03 else (DIAMOND_ORE if r < .045 else (IRON_ORE if r < .1 else STONE))
                sb.set(ox + dx, oy + dy, z, b)
            if depth > 3 and rng.random() < .08:
                sb.set(ox + dx, oy + dy, top - depth, GLOWSTONE)
            elif d < R - 1.5 and rng.random() < .12:
                sb.set(ox + dx, oy + dy, top + 1, rng.choice((TALL_GRASS, TALL_GRASS, FLOWER_RED, FLOWER_YELLOW, BLUE_ORCHID)))
    for dx, dy, dz, b in tree_shape(3 if rng.random() < .4 else 0, 5, rng.random()):
        sb.set(ox + dx, oy + dy, zi + 2 + dz, b)
    for dx, dy in ((-3, -2), (-2, -2), (-3, -1), (-2, -1)):
        if (dx, dy) in tops:
            sb.set(ox + dx, oy + dy, tops[(dx, dy)], WATER)
            sb.set(ox + dx, oy + dy, tops[(dx, dy)] + 1, AIR)
    sb.set(ox + 2, oy + 2, zi + 2, CHEST)
    sb.set(ox + 3, oy + 2, zi + 2, LANTERN)
    return (ox, oy, zi + 1)


def _build_dungeon(self, sb, ox, oy, biome, rng):
    gx, gy, hm = self.footprint(ox - 4, oy - 3, ox + 4, oy + 3)
    zmax = int(hm.min()) - 9
    if zmax < 12:
        return None
    z0 = rng.randint(12, min(zmax, 40))
    for x in range(ox - 4, ox + 5):
        for y in range(oy - 3, oy + 4):
            for z in range(z0 - 1, z0 + 5):
                sb.set(x, y, z, MOSSY if rng.random() < (.6 if z == z0 - 1 else .35) else COBBLE)
    sb.fill(ox - 3, oy - 2, z0, ox + 3, oy + 2, z0 + 3, AIR)
    sb.set(ox, oy, z0, SPAWNER)
    sb.set(ox - 3, oy + 2, z0, CHEST)
    if rng.random() < .6:
        sb.set(ox + 3, oy - 2, z0, CHEST)
    for x, y in ((ox - 3, oy - 2), (ox + 3, oy + 2), (ox - 3, oy + 2), (ox + 3, oy - 2)):
        if rng.random() < .5:
            sb.set(x, y, z0 + 3, COBWEB)
    return (ox, oy, z0)


def _build_mineshaft(self, sb, ox, oy, biome, rng):
    pts = [(ox + d, oy) for d in range(-20, 21, 5)] + [(ox, oy + d) for d in range(-20, 21, 5)]
    hm, _, _ = self.columns(np.array([p[0] for p in pts], float), np.array([p[1] for p in pts], float))
    zmax = int(hm.min()) - 7
    if zmax < 14:
        return None
    z0 = rng.randint(14, min(zmax, 34))
    for axis in (0, 1):
        for d in range(-20, 21):
            for w in (-1, 0, 1):
                x, y = (ox + d, oy + w) if axis == 0 else (ox + w, oy + d)
                sb.fill(x, y, z0, x, y, z0 + 2, AIR)
                if rng.random() < .04:
                    sb.set(x, y, z0 + rng.randint(0, 2), COBWEB)
            if d % 4 == 0 and abs(d) > 1:
                for w in (-1, 1):
                    x, y = (ox + d, oy + w) if axis == 0 else (ox + w, oy + d)
                    sb.fill(x, y, z0, x, y, z0 + 1, PLANKS)
                for w in (-1, 0, 1):
                    x, y = (ox + d, oy + w) if axis == 0 else (ox + w, oy + d)
                    sb.set(x, y, z0 + 2, PLANKS)
                if d % 8 == 0:
                    sb.set(*((ox + d, oy) if axis == 0 else (ox, oy + d)), z0 + 1, LANTERN)
            elif rng.random() < .015:
                x, y = (ox + d, oy + 1) if axis == 0 else (ox + 1, oy + d)
                sb.set(x, y, z0, CHEST)
    return (ox, oy, z0)


for _nm, _f in (('region_structures', _region_structures), ('footprint', _footprint), ('found', _found),
               ('base_z', _base_z), ('build_cabin', _build_cabin), ('build_tower', _build_tower),
               ('build_pyramid', _build_pyramid), ('build_well', _build_well), ('build_igloo', _build_igloo),
               ('build_ruins', _build_ruins), ('build_sky', _build_sky), ('build_dungeon', _build_dungeon),
               ('build_mineshaft', _build_mineshaft), ('build_camp', _build_camp), ('build_farm', _build_farm)):
    setattr(TerrainGen, _nm, _f)


def _structure_near(self, x, y, kinds=SURFACE_KINDS, rad=3):
    rx0, ry0 = int(x) // self.RS, int(y) // self.RS
    best = None
    for rx in range(rx0 - rad, rx0 + rad + 1):
        for ry in range(ry0 - rad, ry0 + rad + 1):
            for k, arr, c in self.region_structures(rx, ry):
                d = math.hypot(c[0] - x, c[1] - y)
                if k in kinds and (best is None or d < best[0]):
                    best = (d, k, c)
    return best


TerrainGen.structure_near = _structure_near

# ====================================================================== v4 world features
SILLY_B, SILLY_SEA = 7, 38
BIOME_NAMES = BIOME_NAMES + ('Sillyland',)
ROCK_GROUND = _mask([GRASS, SAND, GRAVEL, DIRT, RED_SAND, SNOWY_GRASS, STONE])


def _decorate_rocks(self, blk, h, bio, rng, gxs, gys):
    """Pebbles, boulders, stone spires, arches and slab ledges (kept inside the chunk)."""
    I, J = np.indices((16, 16))
    hc = np.minimum(h, H - 12)
    tb, ab = blk[I, J, hc], blk[I, J, hc + 1]
    pr = self.hash01(gxs, gys, 11)
    m = (ab == AIR) & ROCK_GROUND[tb] & (pr < .022) & (h > SEA)
    blk[I[m], J[m], hc[m] + 1] = PEBBLE
    m = (ab == AIR) & (tb == STONE) & (pr > .985) & (h > SEA + 18)
    blk[I[m], J[m], hc[m] + 1] = STONE_SLAB

    def put(x, y, z, b):
        if 0 <= x < 16 and 0 <= y < 16 and 0 < z < H - 1 and (blk[x, y, z] == AIR or PLANT[blk[x, y, z]] or
                                                             blk[x, y, z] == PEBBLE):
            blk[x, y, z] = b
    b0 = int(bio[8, 8])
    mats = {BADLANDS_B: (TERRACOTTA, TERRACOTTA_RED, RED_SAND), DESERT_B: (SANDSTONE, SANDSTONE, SAND),
            SNOW_B: (STONE, ANDESITE, SNOW)}.get(b0, (STONE, ANDESITE, MOSSY))
    if rng.rand() < .2:                                   # boulder
        cx, cy = rng.randint(3, 13), rng.randint(3, 13)
        if h[cx, cy] > SEA:
            rad, z0 = rng.uniform(1.3, 2.4), h[cx, cy] + .4
            R = int(math.ceil(rad))
            for dx in range(-R, R + 1):
                for dy in range(-R, R + 1):
                    for dz in range(-R, R + 1):
                        if dx * dx + dy * dy + (dz * 1.25) ** 2 <= rad * rad:
                            put(cx + dx, cy + dy, int(z0 + dz), mats[rng.randint(0, 3)] if dz < R else mats[2])
    if rng.rand() < .07:                                  # spire
        cx, cy = rng.randint(3, 13), rng.randint(3, 13)
        if h[cx, cy] > SEA:
            ht, z0 = rng.randint(4, 10), h[cx, cy] + 1
            for k in range(ht):
                r_ = 1 if k < ht * .6 else 0
                for dx in range(-r_, r_ + 1):
                    for dy in range(-r_, r_ + 1):
                        if abs(dx) + abs(dy) <= r_:
                            put(cx + dx, cy + dy, z0 + k, mats[rng.randint(0, 2)])
            put(cx, cy, z0 + ht, STONE_SLAB)
    if rng.rand() < .035:                                 # natural arch
        ax, ay = rng.randint(2, 8), rng.randint(3, 12)
        if h[ax, ay] > SEA and h[min(15, ax + 6), ay] > SEA:
            top = max(h[ax, ay], h[ax + 6, ay]) + 5
            for x in (ax, ax + 6):
                for z in range(h[x, ay] + 1, top + 1):
                    put(x, ay, z, mats[rng.randint(0, 2)])
                    put(x, ay + 1, z, mats[rng.randint(0, 2)])
            for x in range(ax, ax + 7):
                for y in (ay, ay + 1):
                    put(x, y, top + (0 if 1 <= x - ax <= 5 else 0), mats[0])
                    if x - ax in (1, 5):
                        put(x, y, top - 1, STONE_SLAB if mats[0] == STONE else mats[0])


TerrainGen.decorate_rocks = _decorate_rocks


def _lighthouse(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 3, oy - 3, ox + 3, oy + 3)
    self.found(sb, ox - 4, oy - 4, ox + 4, oy + 4, z0, STONE_BRICKS, 22)
    ht = 15
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            d = math.hypot(dx, dy)
            if d <= 3.6:
                sb.set(ox + dx, oy + dy, z0 - 1, STONE_BRICKS)
            for k in range(ht):
                if 1.7 < d <= 2.8:
                    sb.set(ox + dx, oy + dy, z0 + k, WOOL_WHITE if (k // 3) % 2 == 0 else WOOL_RED)
                elif d <= 1.7:
                    sb.set(ox + dx, oy + dy, z0 + k, AIR)
            if d <= 3.6:
                sb.set(ox + dx, oy + dy, z0 + ht, STONE_BRICKS)
            if 1.2 < d <= 2.2:
                sb.fill(ox + dx, oy + dy, z0 + ht + 1, ox + dx, oy + dy, z0 + ht + 3, GLASS)
            if d <= 2.4:
                sb.set(ox + dx, oy + dy, z0 + ht + 4, STONE_BRICKS)
            if 3.0 < d <= 3.6 and (dx + dy) % 2 == 0:
                sb.set(ox + dx, oy + dy, z0 + ht + 1, COBBLE_SLAB)
    sb.fill(ox, oy, z0 + ht + 1, ox, oy, z0 + ht + 2, GLOWSTONE)
    sb.set(ox, oy, z0 + ht + 3, LANTERN)
    ring = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
    for k in range(ht - 1):
        dx, dy = ring[k % 8]
        sb.set(ox + dx, oy + dy, z0 + k, STONE_BRICKS)
    for k in (ht - 2, ht - 3):
        dx, dy = ring[k % 8]
        sb.set(ox + dx, oy + dy, z0 + ht, AIR)
    sb.fill(ox, oy - 2, z0, ox, oy - 2, z0 + 1, AIR)
    sb.fill(ox - 1, oy - 2, z0, ox - 1, oy - 2, z0 + 1, AIR)
    sb.set(ox + 1, oy + 1, z0 + ht + 1, CHEST)
    return (ox, oy, z0)


def _ruined_portal(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 4, oy - 3, ox + 4, oy + 3)
    self.found(sb, ox - 5, oy - 4, ox + 5, oy + 4, z0, COBBLE, 8)
    for dx in range(-5, 6):
        for dy in range(-4, 5):
            r = rng.random()
            sb.set(ox + dx, oy + dy, z0 - 1, MAGMA if r < .12 else (COBBLE if r < .5 else (MOSSY if r < .65 else GRASS)))
    missing = set(rng.sample([(a, k) for a in range(5) for k in range(5) if (a in (0, 4)) != (k in (0, 4))], 3))
    for a in range(5):
        for k in range(5):
            corner, edge = a in (0, 4) and k in (0, 4), a in (0, 4) or k in (0, 4)
            if corner:
                b = SAND
            elif edge:
                b = (MOSSY if rng.random() < .5 else AIR) if (a, k) in missing else COBBLE
            else:
                b = AIR
            sb.set(ox - 2 + a, oy, z0 + k, b)
    sb.fill(ox + 3, oy + 2, z0 - 2, ox + 4, oy + 3, z0 - 1, COBBLE)
    sb.set(ox + 3, oy + 2, z0 - 1, LAVA)
    sb.set(ox + 4, oy + 2, z0 - 1, LAVA)
    sb.set(ox - 3, oy + 2, z0, CHEST)
    sb.set(ox - 4, oy + 2, z0, COBBLE)
    sb.set(ox - 4, oy + 2, z0 + 1, LANTERN)
    return (ox, oy, z0)


def _silly_temple(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 5, oy - 5, ox + 5, oy + 5)
    self.found(sb, ox - 6, oy - 6, ox + 6, oy + 6, z0, SILLY_BRICKS, 12)
    for k in range(5):
        r = 5 - k
        sb.fill(ox - r, oy - r, z0 - 1 + k * 2, ox + r, oy + r, z0 + k * 2, SILLY_BRICKS)
    sb.fill(ox - 3, oy - 3, z0, ox + 3, oy + 3, z0 + 4, AIR)
    sb.fill(ox, oy - 5, z0, ox, oy - 4, z0 + 1, AIR)
    for dx, dy in ((-3, -3), (3, -3), (-3, 3), (3, 3)):
        sb.fill(ox + dx, oy + dy, z0, ox + dx, oy + dy, z0 + 2, SILLY_CRYSTAL)
    sb.set(ox, oy, z0, CHEST)
    sb.set(ox, oy + 2, z0, SILLIUM_BLOCK if rng.random() < .25 else SILLY_CRYSTAL)
    for dx, dy in ((-6, -6), (6, -6), (-6, 6), (6, 6)):
        sb.fill(ox + dx, oy + dy, z0 - 1, ox + dx, oy + dy, z0 + 4, SILLY_BRICKS)
        sb.set(ox + dx, oy + dy, z0 + 5, SILLY_CRYSTAL)
    return (ox, oy, z0)


def _shroom_house(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 3, oy - 3, ox + 3, oy + 3)
    self.found(sb, ox - 6, oy - 6, ox + 6, oy + 6, z0, SILLY_SOIL, 13)
    ht = 6
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            edge = abs(dx) == 2 or abs(dy) == 2
            sb.set(ox + dx, oy + dy, z0 - 1, SILLY_PLANKS)
            for k in range(ht):
                sb.set(ox + dx, oy + dy, z0 + k, SHROOM_STEM if edge else AIR)
    for dx in range(-6, 7):
        for dy in range(-6, 7):
            for dz in range(0, 5):
                d = math.sqrt(dx * dx + dy * dy + (dz * 1.6) ** 2)
                if 4.6 < d <= 6.2:
                    sb.set(ox + dx, oy + dy, z0 + ht - 1 + dz, SHROOM_CAP)
                elif d <= 4.6 and dz < 3 and abs(dx) < 2 and abs(dy) < 2:
                    sb.set(ox + dx, oy + dy, z0 + ht - 1 + dz, AIR)
    sb.fill(ox, oy - 2, z0, ox, oy - 2, z0 + 1, AIR)
    sb.set(ox + 1, oy + 1, z0, CHEST)
    sb.set(ox - 1, oy + 1, z0, CRAFTING)
    sb.set(ox - 1, oy - 1, z0, BED)
    sb.set(ox - 1, oy, z0, BED_HEAD)
    sb.set(ox + 1, oy - 1, z0 + 3, LANTERN)
    for _ in range(5):
        sb.set(ox + rng.randint(-5, 5), oy - 4 - rng.randint(0, 1), z0, GLOWBLOOM)
    return (ox, oy, z0)


for _nm, _f in (('build_lighthouse', _lighthouse), ('build_ruined_portal', _ruined_portal),
                ('build_silly_temple', _silly_temple), ('build_shroom_house', _shroom_house)):
    setattr(TerrainGen, _nm, _f)
SURFACE_TABLE[SILLY_B] = (('silly_temple', .13), ('shroom_house', .26))
for _b, _p in ((PLAINS_B, .3), (FOREST_B, .23), (AUTUMN_B, .23), (TAIGA_B, .24), (DESERT_B, .28), (SNOW_B, .28),
               (BADLANDS_B, .22)):
    SURFACE_TABLE[_b] = SURFACE_TABLE[_b] + (('ruined_portal', _p),)
SURFACE_KINDS = SURFACE_KINDS + ('lighthouse', 'ruined_portal', 'silly_temple', 'shroom_house')


def silly_tree(kind, rv):
    """0 swirlwood tree, 1 giant mushroom, 2 jelly blob, 3 crystal spire."""
    out = []
    if kind == 0:
        th = 4 + int(rv * 4)
        out += [(0, 0, z, SILLY_LOG) for z in range(th)]
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                for dz in range(-2, 3):
                    if dx * dx + dy * dy + dz * dz * 1.6 <= 7.5:
                        out.append((dx, dy, th + dz, SILLY_LEAVES))
    elif kind == 1:
        th = 5 + int(rv * 4)
        out += [(0, 0, z, SHROOM_STEM) for z in range(th)]
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                d = math.hypot(dx, dy)
                if d <= 3.4:
                    out.append((dx, dy, th + (1 if d < 2 else 0), SHROOM_CAP))
                    if d > 2.6:
                        out.append((dx, dy, th - 1, SHROOM_CAP))
    elif kind == 2:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for dz in range(0, 3):
                    if dx * dx + dy * dy + (dz - .6) ** 2 * 1.3 <= 3.2:
                        out.append((dx, dy, dz, JELLY))
    elif kind == 3:
        th = 3 + int(rv * 6)
        out += [(0, 0, z, SILLY_CRYSTAL) for z in range(th)]
        out += [(1, 0, 0, SILLY_CRYSTAL), (0, 1, 1, SILLY_CRYSTAL), (-1, 0, 0, SILLY_CRYSTAL)]
    else:                                                   # candy cane
        th = 4 + int(rv * 3)
        out += [(0, 0, z, CANDY_BLOCK) for z in range(th)]
        out += [(1, 0, th, CANDY_BLOCK), (2, 0, th, CANDY_BLOCK), (2, 0, th - 1, CANDY_BLOCK)]
    return out


class SillyGen(TerrainGen):
    """Sillyland: puffy pink hills, floating islands, giant mushrooms, jelly, crystals."""

    def columns(self, X, Y):
        a = self.nh.fbm2(X / 140., Y / 140., 3)
        b = self.nd.fbm2(X / 40., Y / 40., 3)
        puff = np.abs(self.nm.fbm2(X / 90., Y / 90., 2))
        h = np.clip(44 + a * 16 + b * 6 + puff * 20, 6, H - 34).astype(np.int64)
        return h, np.full(np.shape(X), SILLY_B, np.int64), b

    def find_spawn(self):
        return 0.5, 0.5

    def chunk(self, cx, cy):
        x0, y0, M = cx * CS, cy * CS, 3
        gx, gy = np.mgrid[x0 - M:x0 + 16 + M, y0 - M:y0 + 16 + M]
        HH, _, DD = self.columns(gx.astype(float), gy.astype(float))
        S = slice(M, M + 16)
        h = HH[S, S]
        rng = np.random.RandomState((self.seed * 37 + cx * 73856093 ^ cy * 19349663 ^ 0x5111) & 0xffffffff)
        Z = np.arange(H)[None, None, :]
        hh = h[:, :, None]
        blk = np.zeros((CS, CS, H), np.uint8)
        blk[Z <= hh] = SILLY_STONE
        blk[(Z > hh - 4) & (Z < hh)] = SILLY_SOIL
        blk[Z == hh] = SILLY_GRASS
        blk[(Z == hh) & (hh <= SILLY_SEA)] = SILLY_SOIL
        blk[(Z > hh) & (Z <= SILLY_SEA)] = WATER
        blk[:, :, 0] = BEDROCK
        X3, Y3, Z3 = gx[S, S, None].astype(float), gy[S, S, None].astype(float), Z.astype(float)
        c = self.nc.n3(X3 / 26., Y3 / 26., Z3 / 14.)
        cave = (np.abs(c) < .05) & (Z > 3) & (Z < hh - 3)
        blk[cave & (Z <= 6)] = JELLY
        blk[cave & (Z > 6)] = AIR
        zs = slice(60, 86)
        isl = self.ns.n3(X3 / 22., Y3 / 22., Z3[:, :, zs] / 9.) - np.abs(Z3[:, :, zs] - 72) / 26.
        island = isl > .3
        sub = blk[:, :, zs]
        sub[island] = SILLY_STONE
        top = island & ~np.concatenate([island[:, :, 1:], np.zeros((16, 16, 1), bool)], 2)
        sub[top] = SILLY_GRASS
        below_top = np.concatenate([top[:, :, 1:], np.zeros((16, 16, 1), bool)], 2) & island
        sub[below_top] = SILLY_SOIL
        for ore, n, zmin, zmax, size in ((SILLIUM_ORE, 4, 4, 40, 4), (SILLY_CRYSTAL, 3, 4, 50, 6)):
            for _ in range(n):
                x, y, z = rng.randint(0, 16), rng.randint(0, 16), rng.randint(zmin, zmax)
                for _ in range(size):
                    if blk[x, y, z] == SILLY_STONE:
                        blk[x, y, z] = ore
                    x = min(15, max(0, x + rng.randint(-1, 2)))
                    y = min(15, max(0, y + rng.randint(-1, 2)))
                    z = min(H - 1, max(1, z + rng.randint(-1, 2)))
        grass = blk == SILLY_GRASS
        air_above = np.concatenate([blk[:, :, 1:] == AIR, np.zeros((16, 16, 1), bool)], 2)
        R = rng.rand(16, 16, H)
        spot = np.roll(grass & air_above, 1, axis=2)
        blk[spot & (R < .11)] = SILLY_TUFT
        blk[spot & (R >= .11) & (R < .135)] = GLOWBLOOM
        r1, r2, r3 = self.hash01(gx, gy, 21), self.hash01(gx, gy, 22), self.hash01(gx, gy, 23)
        rects = self.surface_rects(cx, cy)
        I, J = np.indices((16, 16))
        nmax = np.maximum.reduce([HH[M + 1:M + 17, S], HH[M - 1:M + 15, S], HH[S, M + 1:M + 17], HH[S, M - 1:M + 15]])
        m = (nmax == h + 1) & (blk[I, J, h] == SILLY_GRASS) & (blk[I, J, np.minimum(h + 1, H - 1)] == AIR)
        blk[I[m], J[m], h[m] + 1] = SILLY_GRASS_SLAB
        if rng.rand() < .25:                                # puffy clouds high in the sky
            cx_, cy_, cz_ = rng.randint(4, 12), rng.randint(4, 12), rng.randint(86, 91)
            for dx in range(-4, 5):
                for dy in range(-3, 4):
                    for dz in range(-1, 2):
                        if (dx / 4.2) ** 2 + (dy / 3.2) ** 2 + (dz / 1.4) ** 2 <= 1 and 0 <= cx_ + dx < 16 and 0 <= cy_ + dy < 16:
                            blk[cx_ + dx, cy_ + dy, cz_ + dz] = CLOUD_BLOCK
        for i, j in zip(*np.nonzero((r1 < .013) & (HH > SILLY_SEA))):
            tx, ty = x0 - M + i, y0 - M + j
            if any(r[0] - 4 <= tx <= r[2] + 4 and r[1] - 4 <= ty <= r[3] + 4 for r in rects):
                continue
            k = r2[i, j]
            kind = 0 if k < .4 else (1 if k < .7 else (2 if k < .82 else (3 if k < .92 else 4)))
            self.put_shape(blk, i - M, j - M, int(HH[i, j]) + 1, silly_tree(kind, r3[i, j]))
        self.apply_structures(blk, cx, cy)
        return blk


def _vhouse(self, sb, cx, cy, face, mats, rng):
    wall, log, roof, floor = mats
    hw, hd = 2, rng.choice((2, 3))
    x0, y0, x1, y1 = cx - hw, cy - hd, cx + hw, cy + hd
    z0 = self.base_z(x0, y0, x1, y1)
    self.found(sb, x0 - 1, y0 - 1, x1 + 1, y1 + 1, z0, COBBLE, 10)
    sb.fill(x0, y0, z0 - 1, x1, y1, z0 - 1, floor)
    sb.fill(x0, y0, z0, x1, y1, z0 + 3, wall)
    sb.fill(x0 + 1, y0 + 1, z0, x1 - 1, y1 - 1, z0 + 3, AIR)
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        sb.fill(x, y, z0 - 1, x, y, z0 + 3, log)
    fx, fy = face
    dx, dy = (x0 if fx < 0 else x1, cy) if fx else (cx, y0 if fy < 0 else y1)
    sb.fill(dx, dy, z0, dx, dy, z0 + 1, AIR)
    for wx, wy in ((x0, cy), (x1, cy), (cx, y0), (cx, y1)):
        if (wx, wy) != (dx, dy):
            sb.set(wx, wy, z0 + 1, GLASS)
    trim = {SANDSTONE: SANDSTONE_SLAB, COBBLE: COBBLE_SLAB}.get(roof, PLANK_SLAB)
    zt = z0 + 3                                       # top row of the walls
    if roof == SANDSTONE:                             # desert: flat roof with a slab parapet
        sb.fill(x0 - 1, y0 - 1, zt + 1, x1 + 1, y1 + 1, zt + 1, SANDSTONE)
        for x in range(x0 - 1, x1 + 2):
            for y in range(y0 - 1, y1 + 2):
                if x in (x0 - 1, x1 + 1) or y in (y0 - 1, y1 + 1):
                    sb.set(x, y, zt + 2, SANDSTONE_SLAB)
    else:                                             # gable roof, ridge along y, solid gable ends
        for k in range(hw + 2):
            z = zt + k
            xa, xb = x0 - 1 + k, x1 + 1 - k
            if xa > xb:
                break
            for y in range(y0 - 1, y1 + 2):
                sb.set(xa, y, z, roof)
                sb.set(xb, y, z, roof)
            if k >= 1:
                for x in range(xa + 1, xb):           # gable triangle on both ends, air inside
                    sb.set(x, y0, z, wall)
                    sb.set(x, y1, z, wall)
                    for y in range(y0 + 1, y1):
                        sb.set(x, y, z, AIR)
            if xa == xb or xa + 1 == xb:
                for y in range(y0 - 1, y1 + 2):       # slab trim along the ridge
                    for x in range(xa, xb + 1):
                        sb.set(x, y, z + 1, trim)
                break
        sb.set(cx, y0, zt + 2, GLASS)                 # little attic windows in the gables
        sb.set(cx, y1, zt + 2, GLASS)
    inner = [(x0 + 1, y0 + 1), (x1 - 1, y0 + 1), (x0 + 1, y1 - 1), (x1 - 1, y1 - 1)]
    inner = [c for c in inner if abs(c[0] - dx) + abs(c[1] - dy) > 1]
    rng.shuffle(inner)
    if len(inner) >= 2:
        bx, by = inner[0]
        hx, hy = (bx, by + (1 if by == y0 + 1 else -1))
        sb.set(bx, by, z0, BED)
        sb.set(hx, hy, z0, BED_HEAD)
        sb.set(*inner[1], z0, rng.choice((CHEST, CRAFTING, HAY_BALE, BOOKSHELF)))
    sb.set(cx, cy, z0 + 2, LANTERN)


def _village(self, sb, ox, oy, biome, rng):
    desert, cold = biome == DESERT_B, biome in (TAIGA_B, SNOW_B)
    mats = ((SANDSTONE, SANDSTONE, SANDSTONE, SANDSTONE) if desert else
            ((SPRUCE_PLANKS, SPRUCE_LOG, COBBLE, SPRUCE_PLANKS) if cold else (PLANKS, LOG, SPRUCE_PLANKS, PLANKS)))
    gx, gy, hm = self.footprint(ox - 18, oy - 18, ox + 18, oy + 18)
    hz = lambda x, y: int(hm[min(36, max(0, x - ox + 18)), min(36, max(0, y - oy + 18))])
    sites = [(12, 0), (-12, 0), (0, 12), (0, -12), (11, 11), (-11, -11), (11, -11), (-11, 11)]
    rng.shuffle(sites)
    n = rng.randint(4, 6)
    for sx, sy in sites[:n + 1]:                     # paths first, buildings on top
        path = [(x, 0) for x in range(0, sx, 1 if sx > 0 else -1)] + [(sx, y) for y in range(0, sy, 1 if sy > 0 else -1)]
        for i, (px, py) in enumerate(path):
            z = hz(ox + px, oy + py)
            sb.set(ox + px, oy + py, z, DIRT_PATH)
            sb.set(ox + px, oy + py, z + 1, AIR)
            sb.set(ox + px, oy + py, z + 2, AIR)
            if i == 6:
                lx, ly = ox + px + (0 if px else 1), oy + py + (1 if px else 0)
                lz = hz(lx, ly)
                sb.fill(lx, ly, lz + 1, lx, ly, lz + 2, COBBLE)
                sb.set(lx, ly, lz + 3, LANTERN)
    self.build_well(sb, ox, oy, biome, rng)
    for sx, sy in sites[:n]:
        face = (-1 if sx > 0 else 1, 0) if abs(sx) >= abs(sy) else (0, -1 if sy > 0 else 1)
        self.vhouse(sb, ox + sx, oy + sy, face, mats, rng)
    fx, fy = sites[n]                                # a small farm plot
    fz = hz(ox + fx, oy + fy)
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            edge = abs(dx) == 3 or abs(dy) == 3
            sb.set(ox + fx + dx, oy + fy + dy, fz, LOG if edge else (WATER if (dx, dy) == (0, 0) else FARMLAND))
            sb.set(ox + fx + dx, oy + fy + dy, fz + 1, AIR if edge or (dx, dy) == (0, 0) else rng.choice((WHEAT2, WHEAT3)))
    bz = hz(ox + 3, oy + 3)
    sb.set(ox + 3, oy + 3, bz, COBBLE)
    sb.set(ox + 3, oy + 3, bz + 1, BELL)
    sb.set(ox - 3, oy + 3, hz(ox - 3, oy + 3) + 1, HAY_BALE)
    return (ox, oy, hz(ox, oy) + 1)


def _geode(self, sb, ox, oy, biome, rng):
    hm = self.footprint(ox - 6, oy - 6, ox + 6, oy + 6)[2]
    zmax = int(hm.min()) - 10
    if zmax < 14:
        return None
    z0, R = rng.randint(10, min(zmax, 40)), rng.uniform(4.5, 6.)
    Ri = int(math.ceil(R))
    for dx in range(-Ri, Ri + 1):
        for dy in range(-Ri, Ri + 1):
            for dz in range(-Ri, Ri + 1):
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if d <= R:
                    sb.set(ox + dx, oy + dy, z0 + dz, CALCITE if d > R - 1 else (AMETHYST_BLOCK if d > R - 2 else AIR))
    for dx in range(-Ri, Ri + 1):
        for dy in range(-Ri, Ri + 1):
            for dz in range(-Ri, 1):
                d, db = math.sqrt(dx * dx + dy * dy + dz * dz), math.sqrt(dx * dx + dy * dy + (dz - 1) ** 2)
                if d <= R - 2 < db and rng.random() < .35:
                    sb.set(ox + dx, oy + dy, z0 + dz, CRYSTAL)
    return (ox, oy, z0)


def _cave_outpost(self, sb, ox, oy, biome, rng):
    hm = self.footprint(ox - 5, oy - 5, ox + 5, oy + 5)[2]
    zmax = int(hm.min()) - 8
    if zmax < 12:
        return None
    z0 = rng.randint(10, min(zmax, 36))
    for x in range(ox - 4, ox + 5):
        for y in range(oy - 3, oy + 4):
            for z in range(z0 - 1, z0 + 5):
                sb.set(x, y, z, PLANKS if z in (z0 - 1, z0 + 4) else (COBBLE if rng.random() < .7 else MOSSY))
    sb.fill(ox - 3, oy - 2, z0, ox + 3, oy + 2, z0 + 3, AIR)
    for x, y in ((ox - 3, oy - 2), (ox + 3, oy - 2), (ox - 3, oy + 2), (ox + 3, oy + 2)):
        sb.fill(x, y, z0, x, y, z0 + 3, LOG)
    sb.set(ox - 2, oy + 2, z0, CHEST)
    sb.set(ox + 2, oy + 2, z0, CRAFTING)
    sb.set(ox - 2, oy - 2, z0, BED)
    sb.set(ox - 1, oy - 2, z0, BED_HEAD)
    sb.set(ox + 2, oy - 2, z0, HAY_BALE)
    sb.set(ox - 1, oy, z0 + 3, LANTERN)
    sb.set(ox + 1, oy, z0 + 3, LANTERN)
    sb.set(ox + 3, oy, z0 + 3, COBWEB)
    sb.fill(ox + 4, oy, z0, ox + 12, oy, z0 + 1, AIR)
    sb.set(ox + 8, oy + 1, z0 + 1, WALL_TORCH)
    return (ox, oy, z0)


def _jelly_throne(self, sb, ox, oy, biome, rng):
    z0 = self.base_z(ox - 12, oy - 12, ox + 12, oy + 12)
    self.found(sb, ox - 13, oy - 13, ox + 13, oy + 13, z0, SILLY_BRICKS, 16)
    for dx in range(-13, 14):
        for dy in range(-13, 14):
            d = math.hypot(dx, dy)
            if d <= 12.5:
                b = SILLIUM_BLOCK if d < 2.5 else (CANDY_BLOCK if int(d) % 4 == 0 else SILLY_BRICKS)
                sb.set(ox + dx, oy + dy, z0 - 1, b)
            if 12 <= d <= 13 and (int(math.degrees(math.atan2(dy, dx))) // 20) % 2 == 0:
                sb.fill(ox + dx, oy + dy, z0, ox + dx, oy + dy, z0 + 1, SILLY_BRICKS)
    for i in range(8):
        a = i * math.pi / 4
        px, py = ox + int(round(math.cos(a) * 9)), oy + int(round(math.sin(a) * 9))
        sb.fill(px, py, z0, px, py, z0 + 5, SILLY_CRYSTAL)
        sb.set(px, py, z0 + 6, CANDY_BLOCK)
        sb.set(px, py, z0 + 7, JELLY)
    sb.fill(ox - 1, oy - 1, z0, ox + 1, oy + 1, z0, SILLIUM_BLOCK)
    sb.set(ox, oy, z0 + 1, BOSS_ALTAR)
    return (ox, oy, z0)


for _nm, _f in (('vhouse', _vhouse), ('build_village', _village), ('build_geode', _geode),
                ('build_cave_outpost', _cave_outpost), ('build_jelly_throne', _jelly_throne)):
    setattr(TerrainGen, _nm, _f)
SURFACE_KINDS = SURFACE_KINDS + ('village', 'jelly_throne')

# ====================================================================== world
def calc_height(blocks):
    lb = LIGHTB[blocks]
    top = H - 1 - np.argmax(lb[:, :, ::-1], axis=2)
    return np.where(lb.any(axis=2), top, -1).astype(np.int32)


def relax(src, cost, iters):
    """Flood-fill light: each step light spreads one block, losing `cost`."""
    L = src.copy()
    M = np.empty_like(L)
    for i in range(iters):
        np.copyto(M, L)
        np.maximum(M[1:], L[:-1], out=M[1:])
        np.maximum(M[:-1], L[1:], out=M[:-1])
        np.maximum(M[:, 1:], L[:, :-1], out=M[:, 1:])
        np.maximum(M[:, :-1], L[:, 1:], out=M[:, :-1])
        np.maximum(M[:, :, 1:], L[:, :, :-1], out=M[:, :, 1:])
        np.maximum(M[:, :, :-1], L[:, :, 1:], out=M[:, :, :-1])
        M -= cost
        np.maximum(M, src, out=M)
        if i % 3 == 2 and np.array_equal(M, L):
            return M
        L, M = M, L
    return L


def compute_light(reg):
    cost = COST[reg]
    sk = SKYB[reg]
    top = np.where(sk.any(2), H - 1 - np.argmax(sk[:, :, ::-1], 2), -1)
    sky = np.where(np.arange(H)[None, None, :] > top[:, :, None], 15, 0).astype(np.int16)
    zlo, zhi = max(0, int(top.min()) - 14), min(H, int(top.max()) + 2)
    if zhi > zlo:
        sky[:, :, zlo:zhi] = relax(sky[:, :, zlo:zhi], cost[:, :, zlo:zhi], 15)
    em = EMIT[reg]
    blk = np.zeros(reg.shape, np.int16)
    zs = np.nonzero(em.any((0, 1)))[0]
    if zs.size:
        lo, hi = max(0, zs[0] - 14), min(H, zs[-1] + 15)
        blk[:, :, lo:hi] = relax(em[:, :, lo:hi], cost[:, :, lo:hi], 14)
    return sky, blk


def mesh_job(reg, cx, cy, fancy):
    """Lighting + mesh arrays for one chunk from a 3x3 chunk snapshot. Pure numpy: runs in a worker process."""
    hides, tex = (HIDES_FANCY, TEXIDX_FANCY) if fancy else (HIDES_FAST, TEXIDX_FAST)
    sky, blk = compute_light(reg[2:46, 2:46])
    pb = np.empty((18, 18, PS), np.uint8)
    pb[:, :, 1:H + 1] = reg[15:33, 15:33]
    pb[:, :, 0], pb[:, :, H + 1] = BEDROCK, AIR
    ps = np.zeros((18, 18, PS), np.float32)
    pl = np.zeros((18, 18, PS), np.float32)
    ps[:, :, 1:H + 1] = sky[13:31, 13:31]
    ps[:, :, H + 1] = 15
    pl[:, :, 1:H + 1] = blk[13:31, 13:31]
    sky_u8 = ps[1:17, 1:17, 1:H + 1].astype(np.uint8)
    blk_u8 = pl[1:17, 1:17, 1:H + 1].astype(np.uint8)
    psf, plf, pbf = ps.ravel(), pl.ravel(), pb.ravel()
    occ = AO_OCC[pbf]
    inner = pb[1:17, 1:17, 1:H + 1]
    fam_in, cube = FAMILY[inner], CUBE[inner]
    leafy = LEAFM[inner] if fancy else np.zeros(inner.shape, bool)
    out = {g: [] for g in range(5)}
    wx0, wy0 = cx * 16, cy * 16
    # fluid corner heights
    fx, fy, fz = np.nonzero(FLUID[inner])
    CH = np.ones((16, 16, H, 2, 2), np.float32)
    if fx.size:
        f = FAMILY[inner[fx, fy, fz]]
        for ccx in (0, 1):
            for ccy in (0, 1):
                hs, ws, full = np.zeros(fx.size, np.float32), np.zeros(fx.size, np.float32), np.zeros(fx.size, bool)
                for ox in (ccx - 1, ccx):
                    for oy in (ccy - 1, ccy):
                        nb = pb[fx + 1 + ox, fy + 1 + oy, fz + 1]
                        same = FAMILY[nb] == f
                        full |= same & (FAMILY[pb[fx + 1 + ox, fy + 1 + oy, fz + 2]] == f)
                        hs += np.where(same, FHEIGHT[nb], 0)
                        ws += same | ~SOLID[nb]
                CH[fx, fy, fz, ccx, ccy] = np.where(full, 1., hs / np.maximum(ws, 1))
        abv = FAMILY[pb[fx + 1, fy + 1, fz + 2]] == f
        CH[fx[abv], fy[abv], fz[abv]] = 1.
    for fi, ((dx, dy, dz), corn, shade, fk) in enumerate(FACES):
        nbk = pb[1 + dx:17 + dx, 1 + dy:17 + dy, 1 + dz:H + 1 + dz]
        vis = cube & ~hides[nbk] & ((FAMILY[nbk] != fam_in) | leafy)
        xs, ys, zs = np.nonzero(vis)
        if not xs.size:
            continue
        b = inner[xs, ys, zs]
        base = (xs + 1 + dx) * STR[0] + (ys + 1 + dy) * STR[1] + (zs + 1 + dz)
        fl = FLUID[b]
        nf = ~fl
        if nf.any():
            bb, bs = b[nf], base[nf]
            pos = np.stack([xs[nf], ys[nf], zs[nf]], 1)
            sk0, bl0 = psf[bs], plf[bs]
            skc, blc, aoc = np.empty((bs.size, 4), np.float32), np.empty((bs.size, 4), np.float32), np.empty((bs.size, 4), np.int32)
            for k, (d1, d2) in enumerate(FACE_INFO[fi]):
                a1, a2, ac = occ[bs + d1], occ[bs + d2], occ[bs + d1 + d2]
                aoc[:, k] = np.where(a1 & a2, 0, 3 - a1.astype(np.int32) - a2 - ac)
                w1, w2 = ~a1, ~a2
                wc = ~ac & ~(a1 & a2)
                n = 1. + w1 + w2 + wc
                skc[:, k] = (sk0 + w1 * psf[bs + d1] + w2 * psf[bs + d2] + wc * psf[bs + d1 + d2]) / n
                blc[:, k] = (bl0 + w1 * plf[bs + d1] + w2 * plf[bs + d2] + wc * plf[bs + d1 + d2]) / n
            v, c, uv = quads(pos, corn, tex[bb, fk], 1.)
            c[..., 0], c[..., 1], c[..., 2] = skc / 15., blc / 15., shade * AOT[aoc]
            c[..., 3] = np.where(SWAY[bb], .5, 1.)[:, None]
            flip = (aoc[:, 0] + aoc[:, 2]) < (aoc[:, 1] + aoc[:, 3])
            if flip.any():
                v[flip], c[flip], uv[flip] = [np.roll(a[flip], -1, 1) for a in (v, c, uv)]
            g = GROUP[bb]
            for gi in (0, 1):
                m = g == gi
                if m.any():
                    out[gi].append((v[m], c[m], uv[m]))
        if fl.any():
            bb, bs = b[fl], base[fl]
            X, Y, Zz = xs[fl], ys[fl], zs[fl]
            v, c, uv = quads(np.stack([X, Y, Zz], 1), corn, np.zeros(bb.size, int), 1.)
            for k in range(4):
                if corn[k][2] > .5:
                    hgt = CH[X, Y, Zz, int(corn[k][0]), int(corn[k][1])]
                    v[:, k, 2] = Zz + hgt
                    c[:, k, 3] = np.where(hgt < .999, .5, 1.)
                else:
                    c[:, k, 3] = 1.
            c[..., 0], c[..., 1], c[..., 2] = (psf[bs] / 15.)[:, None], (plf[bs] / 15.)[:, None], shade
            wx, wy = (v[..., 0] + wx0) % 256, (v[..., 1] + wy0) % 256
            if dz:
                uv[..., 0], uv[..., 1] = wx, wy
            else:
                uv[..., 0] = (wy if dx else wx) + 1000.
                uv[..., 1] = v[..., 2]
            g = GROUP[bb]
            for gi in (2, 3):
                m = g == gi
                if m.any():
                    out[gi].append((v[m], c[m], uv[m]))
    # cross plants
    xs, ys, zs = np.nonzero(PLANT[inner])
    if xs.size:
        b = inner[xs, ys, zs]
        own = (xs + 1) * STR[0] + (ys + 1) * STR[1] + zs + 1
        pos = np.stack([xs, ys, zs], 1)
        for k in range(2):
            v, c, uv = quads(pos, CROSS[k], tex[b, 1], 1.)
            c[..., 0], c[..., 1], c[..., 2] = (psf[own] / 15.)[:, None], (plf[own] / 15.)[:, None], 1.
            c[:, 2:, 3] = np.where(SWAY[b], .5, 1.)[:, None]
            out[4].append((v, c, uv))
    # small box models: torches, lanterns, chests, beds
    for bid in BOXES:
        xs, ys, zs = np.nonzero(inner == bid)
        if not xs.size:
            continue
        b0 = np.array(BOXES[bid][:3], np.float32)
        b1 = np.array(BOXES[bid][3:], np.float32)
        off = np.zeros((xs.size, 3), np.float32)
        P = lambda ox, oy, oz: pb[xs + 1 + ox, ys + 1 + oy, zs + 1 + oz]
        if bid == WALL_TORCH:
            for (ox, oy), o in (((1, 0), (5, 0)), ((-1, 0), (-5, 0)), ((0, 1), (0, 5)), ((0, -1), (0, -5))):
                m = OPAQUE[P(ox, oy, 0)] & (off[:, 2] == 0)
                off[m] = (o[0] / 16., o[1] / 16., 3 / 16.)
        elif bid == LANTERN:
            m = ~OPAQUE[P(0, 0, -1)] & OPAQUE[P(0, 0, 1)]
            off[m, 2] = 7 / 16.
        own = (xs + 1) * STR[0] + (ys + 1) * STR[1] + zs + 1
        pos = np.stack([xs, ys, zs], 1).astype(np.float32) + off
        for fi, ((dx, dy, dz), corn, shade, fk) in enumerate(FACES):
            tile = int(tex[bid, fk])
            u0, v0 = (tile % 16) / 16., 1 - (tile // 16 + 1) / AR
            uvf = BOX_UV[bid][fi]
            v = pos[:, None, :] + (b0 + corn * (b1 - b0))[None]
            c = np.empty((xs.size, 4, 4), np.float32)
            c[..., 0], c[..., 1], c[..., 2], c[..., 3] = (psf[own] / 15.)[:, None], (plf[own] / 15.)[:, None], shade, 1.
            uv = np.empty((xs.size, 4, 2), np.float32)
            uv[..., 0] = u0 + EPS + uvf[None, :, 0] * TSU
            uv[..., 1] = v0 + EPS + uvf[None, :, 1] * TSV
            if fi == 4 and bid in (BED, BED_HEAD):
                other, sgn = (BED_HEAD, 1) if bid == BED else (BED, -1)
                for (ox, oy), k in (((1, 0), -1), ((0, -1), -2), ((-1, 0), -3)):
                    m = P(ox * sgn, oy * sgn, 0) == other
                    if m.any():
                        uv[m] = np.roll(uv[m], k, 1)
            out[int(GROUP[bid])].append((v, c, uv))
    parts = {gi: tuple(np.concatenate([p[i] for p in lst]) for i in range(3)) for gi, lst in out.items() if lst}
    return parts, sky_u8, blk_u8, np.flatnonzero(TICKY[reg[16:32, 16:32]])


_GENS = {}


def worker_init():
    try:
        os.nice(4)                    # keep the render thread snappy (POSIX only)
    except Exception:
        pass


def proc_gen(seed, cx, cy, dim='over'):
    """Terrain generation entry point for worker processes."""
    g = _GENS.get((seed, dim))
    if g is None:
        if len(_GENS) > 3:
            _GENS.clear()
        g = _GENS[(seed, dim)] = (SillyGen if dim == 'silly' else TerrainGen)(seed)
    return g.chunk(cx, cy)


class Chunk:
    __slots__ = ('key', 'blocks', 'height', 'np', 'dirty', 'modified', 'sky', 'blk', 'job', 'ticks', 'mapimg')

    def __init__(self, key, blocks, modified=False):
        self.key, self.blocks, self.np, self.dirty, self.modified = key, blocks, None, 2, modified
        self.height = calc_height(blocks)
        self.sky = self.blk = self.job = self.mapimg = None
        self.ticks = np.zeros(0, np.int64)


N6 = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
HN = ((1, 0), (-1, 0), (0, 1), (0, -1))
PS = H + 2                                  # padded column length
STR = np.array([18 * PS, PS, 1])            # flat strides of the padded (18, 18, H+2) arrays
LEAFM = _mask(LEAF_IDS)
HIDES_FANCY, HIDES_FAST = OPAQUE.copy(), OPAQUE | LEAFM
AOT = np.array([.5, .66, .82, 1.], np.float32)
FACE_INFO = []                              # per face: tangent offsets for each corner (flat)
for _d, _corn, _sh, _fk in FACES:
    _t = [a for a in range(3) if _d[a] == 0]
    _offs = []
    for _k in range(4):
        _o1, _o2 = np.zeros(3, int), np.zeros(3, int)
        _o1[_t[0]] = 1 if _corn[_k][_t[0]] > .5 else -1
        _o2[_t[1]] = 1 if _corn[_k][_t[1]] > .5 else -1
        _offs.append((int(_o1 @ STR), int(_o2 @ STR)))
    FACE_INFO.append(_offs)


def _box_uv(b0, b1):
    """Per face (4, 2) texture fractions for a box, Minecraft-style (uv follows the box faces)."""
    out = []
    b0, b1 = np.array(b0, np.float32), np.array(b1, np.float32)
    for d, corn, sh, fk in FACES:
        ua = int(np.nonzero(corn[1] - corn[0])[0][0])
        va = int(np.nonzero(corn[3] - corn[0])[0][0])
        su, sv = corn[1][ua] - corn[0][ua], corn[3][va] - corn[0][va]
        uv = np.zeros((4, 2), np.float32)
        for k in range(4):
            pu, pv = b0[ua] + corn[k][ua] * (b1[ua] - b0[ua]), b0[va] + corn[k][va] * (b1[va] - b0[va])
            uv[k] = (pu if su > 0 else 1 - pu, pv if sv > 0 else 1 - pv)
        out.append(uv)
    return out


BOX_UV = {b: _box_uv(bx[:3], bx[3:]) for b, bx in BOXES.items()}


class World:
    def __init__(self, game, seed, saved=None, chests=None, dim='over'):
        self.game, self.seed, self.dim = game, seed, dim
        self.gen = (SillyGen if dim == 'silly' else TerrainGen)(seed)
        self.chunks, self.saved, self.chests = {}, dict(saved or {}), dict(chests or {})
        self.spawners = {}
        self.root = game.render.attachNewNode('world')
        self.root.setTexture(game.atlas)
        game.setup_world_shader(self.root)
        self.sched, self.pending, self.tick = [], {}, 0
        self._order_key, self._order = None, []
        self.pool = game.pool
        self.futures, self.jobs = {}, {}
        self.net, self.remote_apply, self.no_physics, self.overrides = None, False, False, {}
        self.markers = {BOSS_ALTAR: set(), BELL: set()}

    def destroy(self):
        for f in self.futures.values():
            f.cancel()
        for ch in self.jobs.values():
            ch.job.cancel()
        self.root.removeNode()

    # ---------------------------------------------------------------- access
    def get(self, x, y, z):
        if z < 0:
            return BEDROCK
        if z >= H:
            return AIR
        ch = self.chunks.get((x >> 4, y >> 4))
        return AIR if ch is None else int(ch.blocks[x & 15, y & 15, z])

    def loaded(self, x, y):
        ch = self.chunks.get((int(math.floor(x)) >> 4, int(math.floor(y)) >> 4))
        return ch is not None and ch.np is not None

    def light_top(self, x, y):
        ch = self.chunks.get((x >> 4, y >> 4))
        return H if ch is None else int(ch.height[x & 15, y & 15])

    def light_at(self, x, y, z):
        if z >= H:
            return 15, 0
        ch = self.chunks.get((x >> 4, y >> 4))
        if ch is None or ch.sky is None or z < 0:
            return 15, 0
        return int(ch.sky[x & 15, y & 15, z]), int(ch.blk[x & 15, y & 15, z])

    def surface_z(self, x, y, zstart):
        """Highest solid (incl. leaves) block below zstart, or None if it's water/void."""
        for z in range(min(H - 1, zstart), 0, -1):
            b = self.get(x, y, z)
            if FLUID[b]:
                return None
            if SOLID[b]:
                return z
        return None

    def top_solid(self, x, y):
        for z in range(H - 1, 0, -1):
            if SOLID[self.get(x, y, z)]:
                return z
        return 0

    def set(self, x, y, z, b, upd=True):
        if z < 0 or z >= H:
            return False
        cx, cy = x >> 4, y >> 4
        ch = self.chunks.get((cx, cy))
        if ch is None:
            return False
        lx, ly = x & 15, y & 15
        old = int(ch.blocks[lx, ly, z])
        if old == b:
            return False
        ch.blocks[lx, ly, z] = b
        nz = np.flatnonzero(LIGHTB[ch.blocks[lx, ly]])
        ch.height[lx, ly] = nz[-1] if nz.size else -1
        ch.dirty, ch.modified = 2, True
        lc = EMIT[old] != EMIT[b] or COST[old] != COST[b] or SKYB[old] != SKYB[b]
        r = (14 if (EMIT[old] or EMIT[b]) else 8) if lc else 1
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    n = self.chunks.get((cx + dx, cy + dy))
                    if n is None:
                        continue
                    ddx = (lx + 1) if dx < 0 else ((16 - lx) if dx > 0 else 0)
                    ddy = (ly + 1) if dy < 0 else ((16 - ly) if dy > 0 else 0)
                    dd = max(ddx, ddy)
                    if dd <= r:
                        n.dirty = max(n.dirty, 2 if dd <= 1 else 1)
        for mb, st in self.markers.items():
            if b == mb:
                st.add((x, y, z))
            elif old == mb:
                st.discard((x, y, z))
        if b == SPAWNER:
            self.spawners[(x, y, z)] = 0.
        elif old == SPAWNER:
            self.spawners.pop((x, y, z), None)
        ch.mapimg = None
        if self.net is not None and not self.remote_apply:
            self.net.on_local_set(x, y, z, b)
        if upd:
            self.schedule(x, y, z, int(DELAY[b]))
            for dx, dy, dz in N6:
                self.schedule(x + dx, y + dy, z + dz, int(DELAY[self.get(x + dx, y + dy, z + dz)]))
        return True

    def remote_set(self, x, y, z, b):
        """Apply a block change received from the network (no physics, no echo)."""
        key = (x >> 4, y >> 4)
        if key not in self.chunks:
            self.overrides.setdefault(key, []).append((x & 15, y & 15, z, b))
            return
        self.remote_apply = True
        try:
            self.set(x, y, z, b, upd=False)
        finally:
            self.remote_apply = False

    # ---------------------------------------------------------------- generation / streaming
    def add_chunk(self, key, blk, modified):
        ov = self.overrides.pop(key, None)
        if ov:
            for lx, ly, z, b in ov:
                blk[lx, ly, z] = b
            modified = True
        ch = Chunk(key, blk, modified)
        self.chunks[key] = ch
        for i in np.flatnonzero(blk == SPAWNER):
            x, y, z = np.unravel_index(i, blk.shape)
            self.spawners[(key[0] * 16 + int(x), key[1] * 16 + int(y), int(z))] = 0.
        for mb, st in self.markers.items():
            for i in np.flatnonzero(blk == mb):
                x, y, z = np.unravel_index(i, blk.shape)
                st.add((key[0] * 16 + int(x), key[1] * 16 + int(y), int(z)))
        return ch

    def ensure_chunk(self, key):
        """Synchronously load/generate a chunk (used where a chunk is needed right now)."""
        ch = self.chunks.get(key)
        if ch is None:
            if key in self.saved:
                blk = np.frombuffer(zlib.decompress(self.saved[key]), np.uint8).reshape(CS, CS, H).copy()
                ch = self.add_chunk(key, blk, True)
            else:
                ch = self.add_chunk(key, self.gen.chunk(*key), False)
        return ch

    def stream(self, px, py, R, budget=.008):
        t0 = time.perf_counter()
        pc = (int(math.floor(px)) >> 4, int(math.floor(py)) >> 4)
        if self._order_key != (pc, R):
            self._order_key = (pc, R)
            offs = [(dx, dy) for dx in range(-R - 2, R + 3) for dy in range(-R - 2, R + 3) if dx * dx + dy * dy <= (R + 2) ** 2]
            offs.sort(key=lambda o: o[0] * o[0] + o[1] * o[1])
            self._order = [((pc[0] + dx, pc[1] + dy), dx * dx + dy * dy <= R * R) for dx, dy in offs]
            for k in list(self.chunks):
                d2 = (k[0] - pc[0]) ** 2 + (k[1] - pc[1]) ** 2
                ch = self.chunks[k]
                if ch.np is not None and d2 > (R + 2) ** 2:
                    ch.np.removeNode()
                    ch.np, ch.dirty = None, 2
                if d2 > (R + 5) ** 2:
                    if ch.modified:
                        self.saved[k] = zlib.compress(ch.blocks.tobytes())
                    del self.chunks[k]
                    for p in [p for p in self.spawners if (p[0] >> 4, p[1] >> 4) == k]:
                        del self.spawners[p]
        for key, fut in list(self.futures.items()):
            if fut.done():
                del self.futures[key]
                try:
                    blk = fut.result()
                except Exception as e:
                    print('chunk generation failed', key, e)
                    continue
                if key not in self.chunks:
                    self.add_chunk(key, blk, False)
        applied = 0
        for key, ch in list(self.jobs.items()):        # upload finished meshes (time-budgeted)
            if not ch.job.done():
                continue
            if applied and time.perf_counter() - t0 > budget:
                break
            applied += 1
            del self.jobs[key]
            fut, ch.job = ch.job, None
            if self.chunks.get(key) is not ch:
                continue
            try:
                self.apply_mesh(ch, fut.result())
            except Exception as e:
                print('meshing failed', key, e)
                ch.dirty = 2
        for key, inner in self._order:                 # edited meshes first
            if len(self.jobs) >= self.game.workers + 2:
                break
            ch = self.chunks.get(key)
            if ch is not None and ch.np is not None and ch.dirty == 2 and ch.job is None:
                self.schedule_mesh(ch)
        for key, inner in self._order:
            ch = self.chunks.get(key)
            if ch is None:
                if key in self.saved:
                    self.ensure_chunk(key)
                elif key not in self.futures and len(self.futures) < self.game.workers + 2:
                    self.futures[key] = self.game.submit(proc_gen, self.seed, key[0], key[1], self.dim)
            elif inner and ch.dirty and ch.job is None and len(self.jobs) < self.game.workers + 2:
                self.schedule_mesh(ch)

    def ready(self, px, py, r):
        pc = (int(math.floor(px)) >> 4, int(math.floor(py)) >> 4)
        tot = done = 0
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    tot += 1
                    ch = self.chunks.get((pc[0] + dx, pc[1] + dy))
                    done += ch is not None and ch.np is not None and not ch.dirty and ch.job is None
        return done, tot

    # ---------------------------------------------------------------- meshing
    def region(self, cx, cy):
        out = np.empty((48, 48, H), np.uint8)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = self.chunks.get((cx + dx, cy + dy))
                if n is None:
                    return None
                out[(dx + 1) * 16:(dx + 2) * 16, (dy + 1) * 16:(dy + 2) * 16] = n.blocks
        return out

    def schedule_mesh(self, ch):
        reg = self.region(*ch.key)
        if reg is None:
            return False
        ch.dirty = 0
        ch.job = self.game.submit(mesh_job, reg, ch.key[0], ch.key[1], bool(self.game.settings['fancy_leaves']))
        self.jobs[ch.key] = ch
        return True

    def build_mesh(self, ch):
        """Synchronous rebuild (tests / tools)."""
        reg = self.region(*ch.key)
        if reg is None:
            return False
        ch.dirty = 0
        self.apply_mesh(ch, mesh_job(reg, ch.key[0], ch.key[1], bool(self.game.settings['fancy_leaves'])))
        return True

    def apply_mesh(self, ch, res):
        parts, ch.sky, ch.blk, ch.ticks = res
        cx, cy = ch.key
        if ch.np is not None:
            ch.np.removeNode()
        ch.np = self.root.attachNewNode('chunk')
        ch.np.setPos(cx * CS, cy * CS, 0)
        g = self.game
        for gi, arrs in parts.items():
            n = geom_np(*arrs)
            n.reparentTo(ch.np)
            if gi == 2:
                n.setTexture(g.water_tex, 1)
                n.setShaderInput('mode', 1.)
                n.setTransparency(TransparencyAttrib.MAlpha)
                n.setDepthWrite(False)
                n.setTwoSided(True)
            elif gi == 3:
                n.setTexture(g.lava_tex, 1)
                n.setShaderInput('mode', 2.)
            elif gi == 4:
                n.setTwoSided(True)

    # ---------------------------------------------------------------- block updates (physics)
    def schedule(self, x, y, z, delay=1):
        if self.no_physics:
            return
        key, due = (x, y, z), self.tick + delay
        if self.pending.get(key, 1 << 60) <= due:
            return
        self.pending[key] = due
        heapq.heappush(self.sched, (due, key))

    def do_tick(self):
        self.tick += 1
        n, t0 = 0, time.perf_counter()
        while self.sched and self.sched[0][0] <= self.tick and n < 300:
            due, key = heapq.heappop(self.sched)
            if self.pending.get(key) != due:
                continue
            del self.pending[key]
            if (key[0] >> 4, key[1] >> 4) in self.chunks:
                self.block_update(*key)
            n += 1
            if n % 25 == 0 and time.perf_counter() - t0 > .006:
                break

    def pop_block(self, x, y, z, b):
        self.set(x, y, z, AIR)
        if self.game.mode == 'survival' or b in (TORCH, WALL_TORCH, LANTERN):
            for it, c in drops_for(b):
                self.game.spawn_item((x + .5, y + .5, z + .2), it, c)

    def block_update(self, x, y, z):
        b = self.get(x, y, z)
        g, get = self.game, self.get
        if b in (SAND, GRAVEL, RED_SAND):
            if z > 0 and REPL[get(x, y, z - 1)]:
                self.set(x, y, z, AIR)
                g.add_fx(FallingBlock(g, x, y, z, b))
        elif b == SILLY_PORTAL:
            ok = lambda n: n in (SILLY_PORTAL, COBBLE, SAND)
            vert = ok(get(x, y, z + 1)) and ok(get(x, y, z - 1))
            if not (vert and ((ok(get(x + 1, y, z)) and ok(get(x - 1, y, z))) or (ok(get(x, y + 1, z)) and ok(get(x, y - 1, z))))):
                self.set(x, y, z, AIR)
        elif b in (BED, BED_HEAD):
            other = BED_HEAD if b == BED else BED
            if not any(get(x + dx, y + dy, z) == other for dx, dy in HN):
                self.set(x, y, z, AIR)
        elif PLANT[b] or b in (TORCH, SNOW_LAYER):
            if not supported(b, get(x, y, z - 1)):
                self.pop_block(x, y, z, b)
        elif b == WALL_TORCH:
            if not any(OPAQUE[get(x + dx, y + dy, z)] for dx, dy in HN):
                self.pop_block(x, y, z, b)
        elif b == LANTERN:
            if not (OPAQUE[get(x, y, z - 1)] or OPAQUE[get(x, y, z + 1)]):
                self.pop_block(x, y, z, b)
        elif b == FARMLAND:
            if OPAQUE[get(x, y, z + 1)]:
                self.set(x, y, z, DIRT)
        elif b == CACTUS:
            if get(x, y, z - 1) not in (SAND, RED_SAND, CACTUS) or any(SOLID[get(x + dx, y + dy, z)] for dx, dy in HN):
                self.pop_block(x, y, z, b)
        elif FLUID[b]:
            self.fluid_update(x, y, z, b)

    def fid(self, fam, L):
        src, ids, mx, _ = FLUIDS[fam]
        return src if L >= mx else ids[L]

    def place_fluid(self, x, y, z, f):
        old = self.get(x, y, z)
        if old and not FLUID[old]:
            if old in (TORCH, WALL_TORCH) or old in (FLOWER_RED, FLOWER_YELLOW, BLUE_ORCHID, SAPLING, SUGAR_CANE,
                                                     RED_MUSHROOM, BROWN_MUSHROOM, WHEAT3):
                for it, c in drops_for(old):
                    self.game.spawn_item((x + .5, y + .5, z + .3), it, c)
        self.set(x, y, z, f)

    def open_for(self, fam, n, s):
        return (FLOWINTO[n] and not FLUID[n]) or (FAMILY[n] == fam and LEVEL[n] < s and n != FLUIDS[fam][0])

    def drop_dist(self, x, y, z, fam, depth, came, limit):
        b = self.get(x, y, z - 1)
        if (FLOWINTO[b] and not FLUID[b]) or FAMILY[b] == fam:
            return depth
        if depth >= limit:
            return 99
        best = 99
        for dx, dy in HN:
            if (dx, dy) != came:
                n = self.get(x + dx, y + dy, z)
                if (FLOWINTO[n] and not FLUID[n]) or FAMILY[n] == fam:
                    best = min(best, self.drop_dist(x + dx, y + dy, z, fam, depth + 1, (-dx, -dy), limit))
        return best

    def fluid_update(self, x, y, z, b):
        fam = int(FAMILY[b])
        src, ids, mx, _ = FLUIDS[fam]
        L, get = int(LEVEL[b]), self.get
        hn = [(x + dx, y + dy, z) for dx, dy in HN]
        if fam == LAVA:
            for dx, dy, dz in N6:
                if FAMILY[get(x + dx, y + dy, z + dz)] == WATER:
                    self.set(x, y, z, OBSIDIAN if L >= mx else COBBLE)
                    self.game.sounds.play('fizz', (x, y, z))
                    self.game.particles((x + .5, y + .5, z + 1), 6, color=(.8, .8, .8), up=True)
                    return
        below = get(x, y, z - 1)
        if L < mx:                               # flowing: is it still fed?
            if FAMILY[get(x, y, z + 1)] == fam:
                t = mx - 1
            else:
                t, srcs = 0, 0
                for p in hn:
                    n = get(*p)
                    if FAMILY[n] == fam:
                        t = max(t, int(LEVEL[n]) - 1)
                        srcs += n == src
                if fam == WATER and srcs >= 2 and (SOLID[below] or below == src):
                    t = mx
            if t <= 0:
                self.set(x, y, z, AIR)
                return
            if t != L:
                self.set(x, y, z, self.fid(fam, t))
                return
        if z > 0 and FLOWINTO[below] and not FLUID[below]:
            self.place_fluid(x, y, z - 1, self.fid(fam, mx - 1))
            if L < mx:
                return
        elif FAMILY[below] == fam and L < mx:
            return
        s = mx - 1 if L >= mx else L - 1
        if s < 1:
            return
        limit = 4 if fam == WATER else 2
        opts = []
        for dx, dy in HN:
            n = get(x + dx, y + dy, z)
            if (FLOWINTO[n] and not FLUID[n]) or (FAMILY[n] == fam and n != src):
                opts.append((self.drop_dist(x + dx, y + dy, z, fam, 1, (-dx, -dy), limit), x + dx, y + dy, n))
        if opts:
            m = min(o[0] for o in opts)
            for d, nx, ny, n in opts:
                if d == m and self.open_for(fam, n, s):
                    self.place_fluid(nx, ny, z, self.fid(fam, s))

    def flow_vec(self, x, y, z):
        b = self.get(x, y, z)
        f = FAMILY[b]
        if f not in (WATER, LAVA) or FAMILY[self.get(x, y, z + 1)] == f:
            return 0., 0.
        L, vx, vy = LEVEL[b], 0., 0.
        for dx, dy in HN:
            n = self.get(x + dx, y + dy, z)
            if FAMILY[n] == f:
                d = L - LEVEL[n]
            elif not SOLID[n]:
                d = L
            else:
                continue
            vx += dx * d
            vy += dy * d
        n = math.hypot(vx, vy)
        return (vx / n, vy / n) if n else (0., 0.)

    # ---------------------------------------------------------------- growth
    def random_tick(self, px, py):
        pcx, pcy = int(math.floor(px)) >> 4, int(math.floor(py)) >> 4
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                ch = self.chunks.get((pcx + dx, pcy + dy))
                if ch is None or ch.np is None or not ch.ticks.size:
                    continue
                for i in ch.ticks[np.random.rand(ch.ticks.size) < .06]:
                    x, y, z = np.unravel_index(i, ch.blocks.shape)
                    if TICKY[ch.blocks[x, y, z]]:
                        self.grow(ch.key[0] * 16 + int(x), ch.key[1] * 16 + int(y), int(z))

    def grow(self, x, y, z, meal=False):
        b, get = self.get(x, y, z), self.get
        if b in (WHEAT1, WHEAT2):
            self.set(x, y, z, WHEAT3 if meal else b + 1)
            return True
        if b == SAPLING:
            return (meal and random.random() < .45 or not meal and random.random() < .25) and self.grow_tree(x, y, z)
        if b == SUGAR_CANE:
            zz = z
            while get(x, y, zz + 1) == SUGAR_CANE:
                zz += 1
            n = zz - z + 1
            while get(x, y, z - 1) == SUGAR_CANE:
                z -= 1
                n += 1
            if n < 3 and get(x, y, zz + 1) == AIR:
                self.set(x, y, zz + 1, SUGAR_CANE)
                return True
            return False
        if b in (GRASS, SNOWY_GRASS) and meal:
            for _ in range(12):
                px, py = x + random.randint(-3, 3), y + random.randint(-3, 3)
                for pz in (z + 1, z, z + 2):
                    if get(px, py, pz) == AIR and get(px, py, pz - 1) == GRASS:
                        r = random.random()
                        self.set(px, py, pz, TALL_GRASS if r < .7 else (FLOWER_RED if r < .85 else FLOWER_YELLOW))
                        break
            return True
        return False

    def grow_tree(self, x, y, z):
        biome, _ = self.gen.biome_at(x, y)
        kind = 2 if biome in (TAIGA_B, SNOW_B) else (3 if biome == AUTUMN_B else (1 if random.random() < .25 else 0))
        shape = tree_shape(kind, 4 + random.randint(0, 2), random.random())
        for dx, dy, dz, b in shape:
            if b not in LEAF_IDS and (dx or dy or dz) and not (REPL[self.get(x + dx, y + dy, z + dz)] or
                                                                PLANT[self.get(x + dx, y + dy, z + dz)]):
                return False
            if z + dz >= H - 1:
                return False
        for dx, dy, dz, b in shape:
            cur = self.get(x + dx, y + dy, z + dz)
            if b not in LEAF_IDS or NOT_LEAF_TARGET[cur]:
                self.set(x + dx, y + dy, z + dz, b, upd=False)
        return True

    # ---------------------------------------------------------------- containers
    def chest_inv(self, pos):
        inv = self.chests.get(pos)
        if inv is None:
            inv = self.chests[pos] = gen_loot(self.seed, pos, self.dim)
        return inv

    # ---------------------------------------------------------------- queries
    def raycast(self, o, d, maxd, mask=None):
        mask = TARGET if mask is None else mask
        x, y, z = (int(math.floor(v)) for v in o)
        step, tmax, tdel = [], [], []
        for i, c in enumerate((x, y, z)):
            if d[i] > 0:
                step.append(1), tdel.append(1 / d[i]), tmax.append((c + 1 - o[i]) / d[i])
            elif d[i] < 0:
                step.append(-1), tdel.append(-1 / d[i]), tmax.append((o[i] - c) / -d[i])
            else:
                step.append(0), tdel.append(1e30), tmax.append(1e30)
        prev, t = None, 0.0
        while t <= maxd:
            if mask[self.get(x, y, z)]:
                return (x, y, z), prev, t
            prev = (x, y, z)
            if tmax[0] < tmax[1] and tmax[0] < tmax[2]:
                x += step[0]; t = tmax[0]; tmax[0] += tdel[0]
            elif tmax[1] < tmax[2]:
                y += step[1]; t = tmax[1]; tmax[1] += tdel[1]
            else:
                z += step[2]; t = tmax[2]; tmax[2] += tdel[2]
        return None, None, None

    def explode(self, x, y, z, r):
        g = self.game
        ix, iy, iz = int(math.floor(x)), int(math.floor(y)), int(math.floor(z))
        ri, tnt = int(math.ceil(r)), []
        for dx in range(-ri, ri + 1):
            for dy in range(-ri, ri + 1):
                for dz in range(-ri, ri + 1):
                    if dx * dx + dy * dy + dz * dz > (r + random.random() * .6 - .3) ** 2:
                        continue
                    p = (ix + dx, iy + dy, iz + dz)
                    b = self.get(*p)
                    if not BLAST[b]:
                        continue
                    if b == CHEST:
                        for s in self.chest_inv(p):
                            if s:
                                g.spawn_item((p[0] + .5, p[1] + .5, p[2] + .5), s[0], s[1])
                        self.chests.pop(p, None)
                    self.set(*p, AIR)
                    if b == TNT:
                        tnt.append(p)
                    elif g.mode == 'survival' and random.random() < .25:
                        for it, c in drops_for(b):
                            g.spawn_item((p[0] + .5, p[1] + .5, p[2] + .3), it, c)
        for p in tnt:
            g.add_fx(PrimedTNT(g, *p, fuse=random.uniform(.4, 1.2)))
        g.on_explosion((x, y, z), r)

    def save_chunks(self):
        d = dict(self.saved)
        for k, ch in self.chunks.items():
            if ch.modified:
                d[k] = zlib.compress(ch.blocks.tobytes())
        return d


def drops_for(b):
    r = random.random()
    if b in LEAF_IDS:
        out = [(SAPLING, 1)] if r < .06 else []
        if b in (LEAVES, AUTUMN_LEAVES) and random.random() < .07:
            out.append((APPLE, 1))
        return out
    if b in (GLASS, ICE, SPAWNER, AIR, SNOW_LAYER) or FLUID[b]:
        return []
    if b in (TALL_GRASS, FERN):
        return [(SEEDS, 1)] if r < .15 else []
    if b == WHEAT3:
        return [(WHEAT, 1), (SEEDS, random.randint(1, 2))]
    return [(DROP.get(b, b), 1)]


LOOT = {'dungeon': [(IRON_INGOT, 1, 3, 10), (GOLD_INGOT, 1, 2, 5), (DIAMOND, 1, 1, 1), (BREAD, 1, 3, 10),
                    (GOLDEN_APPLE, 1, 1, 1), (BONE, 1, 4, 10), (STRING, 1, 4, 8), (GUNPOWDER, 1, 3, 8),
                    (ARROW, 2, 8, 6), (BUCKET, 1, 1, 3), (EMERALD, 1, 1, 2), (COAL, 2, 6, 10), (tool_id(2, 0), 1, 1, 1),
                    (BOW, 1, 1, 2), (SEEDS, 2, 6, 6), (ROTTEN_FLESH, 1, 4, 10)],
        'surface': [(BREAD, 1, 3, 10), (APPLE, 1, 4, 10), (TORCH, 2, 6, 8), (COAL, 1, 4, 8), (IRON_INGOT, 1, 2, 4),
                    (SEEDS, 2, 6, 8), (WHEAT, 2, 5, 6), (EMERALD, 1, 1, 1), (tool_id(1, 0), 1, 1, 2),
                    (tool_id(1, 3), 1, 1, 2), (SAPLING, 1, 3, 6), (STICK, 2, 6, 8), (STRING, 1, 3, 4), (BONE_MEAL, 2, 5, 4)],
        'silly': [(SILLIUM_INGOT, 1, 2, 4), (PRISM_SHARD, 1, 4, 8), (JELLY_BALL, 1, 4, 8), (SILLY_BERRY, 1, 4, 8),
                  (SADDLE, 1, 1, 3), (GRAPPLE, 1, 1, 1), (PARAGLIDER, 1, 1, 1), (GLOWBLOOM, 1, 3, 5), (SILLY_PLANKS, 2, 8, 6)],
        'sky': [(GOLD_INGOT, 1, 3, 6), (IRON_INGOT, 1, 4, 8), (DIAMOND, 1, 1, 2), (GOLDEN_APPLE, 1, 1, 1),
                (EMERALD, 1, 2, 3), (CRYSTAL, 1, 4, 6), (GLOWSTONE, 1, 3, 4), (COOKED_FISH, 2, 5, 6), (SAPLING, 1, 2, 5),
                (FEATHER, 1, 4, 6)]}


def gen_loot(seed, pos, dim='over'):
    x, y, z = pos
    rng = random.Random((seed * 92821) ^ (x * 73856093) ^ (y * 19349663) ^ (z * 83492791))
    table = LOOT['silly' if dim == 'silly' else ('dungeon' if z < SEA - 6 else ('sky' if z > 70 else 'surface'))]
    if dim == 'over' and SEA - 6 <= z <= 70 and rng.random() < .15:
        table = table + [(SADDLE, 1, 1, 6), (IRON_SPEAR, 1, 1, 3), (SLINGSHOT, 1, 1, 3)]
    tot = sum(t[3] for t in table)
    inv = [None] * 27
    for slot in rng.sample(range(27), rng.randint(3, 6)):
        r = rng.random() * tot
        for it, a, b, w in table:
            r -= w
            if r <= 0:
                inv[slot] = [it, min(max_stack(it), rng.randint(a, b))]
                break
    return inv

# ====================================================================== entities
class Body:
    def __init__(self, game, pos, hw, hh):
        self.game, self.pos, self.vel = game, [float(v) for v in pos], [0., 0., 0.]
        self.hw, self.hh = hw, hh
        self.on_ground = self.in_water = self.in_lava = self.hit_wall = self.gone = self.in_web = False
        self.land_vz, self.flow, self.step_off = 0., (0., 0.), 0.

    def collides(self, x, y, z):
        get, hw, hh = self.game.world.get, self.hw, self.hh
        for bx in range(math.floor(x - hw), math.floor(x + hw - 1e-7) + 1):
            for by in range(math.floor(y - hw), math.floor(y + hw - 1e-7) + 1):
                for bz in range(math.floor(z), math.floor(z + hh - 1e-7) + 1):
                    b = get(bx, by, bz)
                    if SOLID[b]:
                        bb = BOXES.get(b)
                        if bb is None or (x - hw < bx + bb[3] and x + hw > bx + bb[0] and y - hw < by + bb[4] and
                                          y + hw > by + bb[1] and z < bz + bb[5] and z + hh > bz + bb[2]):
                            return True
        return False

    def floor_top(self, x, y, znew, zold):
        get, hw, best = self.game.world.get, self.hw, None
        for bx in range(math.floor(x - hw), math.floor(x + hw - 1e-7) + 1):
            for by in range(math.floor(y - hw), math.floor(y + hw - 1e-7) + 1):
                for bz in range(math.floor(znew), math.floor(zold) + 1):
                    b = get(bx, by, bz)
                    if SOLID[b]:
                        top = bz + (BOXES[b][5] if b in BOXES else 1.)
                        if top <= zold + 1e-6 and (best is None or top > best):
                            best = top
        return zold if best is None else best

    def touching(self, block):
        get, hw, p = self.game.world.get, self.hw + .05, self.pos
        for bx in range(math.floor(p[0] - hw), math.floor(p[0] + hw) + 1):
            for by in range(math.floor(p[1] - hw), math.floor(p[1] + hw) + 1):
                for bz in range(math.floor(p[2] - .05), math.floor(p[2] + self.hh) + 1):
                    if get(bx, by, bz) == block:
                        return True
        return False

    def below(self):
        return self.game.world.get(math.floor(self.pos[0]), math.floor(self.pos[1]), math.floor(self.pos[2] - .05))

    def check_fluids(self):
        w, p = self.game.world, self.pos
        x, y = math.floor(p[0]), math.floor(p[1])
        fa, fb = w.get(x, y, math.floor(p[2] + .2)), w.get(x, y, math.floor(p[2] + self.hh * .6))
        a, b = FAMILY[fa], FAMILY[fb]
        self.in_water, self.in_lava = WATER in (a, b), LAVA in (a, b)
        self.in_web = COBWEB in (fa, fb)
        self.flow = w.flow_vec(x, y, math.floor(p[2] + .2)) if (self.in_water or self.in_lava) else (0., 0.)

    def move(self, dt, edge_guard=False):
        p, v, hw, hh = self.pos, self.vel, self.hw, self.hh
        was_ground = self.on_ground
        self.on_ground = self.hit_wall = False
        if self.collides(*p):                       # stuck inside a block: pop upwards
            p[2] += .25
            v[2] = 0.
            return
        if self.in_web:
            dt *= .25
        dx, dy, dz = v[0] * dt, v[1] * dt, v[2] * dt
        n = int(max(abs(dx), abs(dy), abs(dz)) / .45) + 1
        dx, dy, dz = dx / n, dy / n, dz / n
        for _ in range(n):
            if dz:
                old = p[2]
                p[2] += dz
                if self.collides(*p):
                    if dz < 0:
                        p[2] = self.floor_top(p[0], p[1], p[2], old)
                        self.on_ground, self.land_vz = True, v[2]
                    else:
                        p[2] = math.floor(p[2] + hh) - hh - 1e-4
                        if self.collides(*p):
                            p[2] = old
                    v[2] = dz = 0.
            for ax in (0, 1):
                d = dx if ax == 0 else dy
                if not d:
                    continue
                old = p[ax]
                p[ax] += d
                blocked = False
                if self.collides(*p):
                    top = self.floor_top(p[0], p[1], p[2], p[2] + .6) if was_ground else p[2]
                    if was_ground and p[2] + 1e-4 < top <= p[2] + .6 and not self.collides(p[0], p[1], top):
                        self.step_off -= top - p[2]          # step up onto a slab: exact height, camera eases
                        p[2] = top
                        self.on_ground = True
                    else:
                        p[ax] = (math.floor(p[ax] + hw) - hw - 1e-4) if d > 0 else (math.floor(p[ax] - hw) + 1 + hw + 1e-4)
                        if self.collides(*p):
                            p[ax] = old
                        blocked = True
                elif edge_guard and self.on_ground and not self.collides(p[0], p[1], p[2] - .1):
                    p[ax] = old
                    blocked = True
                if blocked:
                    v[ax] = 0.
                    self.hit_wall = True
                    if ax == 0:
                        dx = 0.
                    else:
                        dy = 0.
            if was_ground and v[2] <= 0 and not self.on_ground and (dx or dy) and not edge_guard:
                top = self.floor_top(p[0], p[1], p[2] - .55, p[2])   # step down off a slab instead of falling
                if p[2] - .56 < top < p[2] - 1e-4 and not self.collides(p[0], p[1], top):
                    self.step_off += p[2] - top
                    p[2] = top
                    self.on_ground = True
                    v[2] = 0.

MOBDEF = {
    'pig': dict(hp=10, hw=.45, hh=.9, speed=1.5, drops=[(PORK, 1, 3)], sound='oink'),
    'cow': dict(hp=10, hw=.45, hh=1.3, speed=1.4, drops=[(BEEF, 1, 3)], sound='moo'),
    'sheep': dict(hp=8, hw=.45, hh=1.25, speed=1.4, drops=[(MUTTON, 1, 2), (WOOL_WHITE, 1, 1)], sound='baa'),
    'chicken': dict(hp=4, hw=.25, hh=.7, speed=1.4, drops=[(CHICKEN, 1, 1), (FEATHER, 0, 2)], sound='cluck'),
    'zombie': dict(hp=20, hw=.3, hh=1.9, speed=2.6, hostile=True, drops=[(ROTTEN_FLESH, 0, 2)], sound='groan',
                   dmg=3, burns=True),
    'creeper': dict(hp=20, hw=.3, hh=1.7, speed=2.4, hostile=True, drops=[(GUNPOWDER, 0, 2)], sound=None),
    'rabbit': dict(hp=3, hw=.2, hh=.5, speed=3.4, drops=[(RAW_RABBIT, 0, 1)], sound='squeak', hop=True, skittish=True),
    'fox': dict(hp=10, hw=.3, hh=.7, speed=3.2, drops=[], sound='yip', skittish=True),
    'deer': dict(hp=12, hw=.4, hh=1.6, speed=2.4, drops=[(VENISON, 1, 3)], sound='bleat', skittish=True),
    'goat': dict(hp=10, hw=.4, hh=1.3, speed=1.6, drops=[(MUTTON, 1, 2)], sound='bleat', jump=11.),
    'penguin': dict(hp=6, hw=.25, hh=.9, speed=1.2, drops=[(RAW_FISH, 0, 1), (FEATHER, 0, 1)], sound='squawk'),
    'duck': dict(hp=4, hw=.25, hh=.65, speed=1.3, drops=[(CHICKEN, 1, 1), (FEATHER, 0, 2)], sound='quack'),
    'fish': dict(hp=3, hw=.2, hh=.35, speed=2.2, drops=[(RAW_FISH, 1, 1)], sound=None, fish=True),
    'skeleton': dict(hp=20, hw=.3, hh=1.9, speed=2.4, hostile=True, drops=[(BONE, 0, 2), (ARROW, 0, 2)],
                     sound='rattle', burns=True, ranged=True),
    'spider': dict(hp=16, hw=.6, hh=.8, speed=3.0, hostile=True, drops=[(STRING, 0, 2)], sound='chitter', dmg=2,
                   climb=True),
    'bird': dict(hp=3, hw=.15, hh=.32, speed=5.5, drops=[(FEATHER, 0, 1)], sound='chirp', bird=True),
    'butterfly': dict(hp=1, hw=.12, hh=.2, speed=1.6, drops=[], sound=None, flutter=True),
    'frog': dict(hp=4, hw=.2, hh=.3, speed=2.4, drops=[], sound='croak', hop=True, skittish=True),
    'horse': dict(hp=15, hw=.55, hh=1.6, speed=1.8, drops=[(BEEF, 0, 1)], sound='neigh', mount=(9.5, 9.5, 1.15)),
    'wolf': dict(hp=12, hw=.3, hh=.8, speed=3.2, drops=[(BONE, 0, 2)], sound='growl', neutral=True, dmg=3),
    'gloop': dict(hp=8, hw=.4, hh=.75, speed=2.2, hostile=True, drops=[(JELLY_BALL, 1, 2)], sound='blorp', dmg=2,
                  hop=True, silly=True),
    'floatie': dict(hp=5, hw=.35, hh=.7, speed=1.1, drops=[(JELLY_BALL, 0, 1), (SILLY_BERRY, 0, 1)], sound=None,
                    flutter=True, alt=(3., 7.)),
    'imp': dict(hp=14, hw=.3, hh=1.2, speed=2.6, hostile=True, drops=[(PRISM_SHARD, 0, 2)], sound='giggle',
                ranged=True, shard=True, silly=True),
    'hopper': dict(hp=16, hw=.5, hh=1.2, speed=1.6, drops=[(SILLY_BERRY, 1, 2)], sound='blorp', hop=True,
                   mount=(7.5, 15., 1.0)),
}
MOBDEF.update({
    'turtle': dict(hp=8, hw=.35, hh=.4, speed=.7, drops=[], sound=None),
    'bear': dict(hp=25, hw=.5, hh=1.2, speed=2.4, drops=[(BEEF, 1, 3)], sound='growl', neutral=True, dmg=5),
    'villager': dict(hp=20, hw=.3, hh=1.9, speed=1.2, drops=[], sound='hmm'),
    'bee': dict(hp=2, hw=.1, hh=.18, speed=2., drops=[], sound=None, flutter=True, alt=(.6, 2.2)),
    'ant': dict(hp=1, hw=.07, hh=.06, speed=1.1, drops=[], sound=None),
    'dragonfly': dict(hp=2, hw=.12, hh=.12, speed=3.2, drops=[], sound=None, flutter=True, alt=(.8, 2.)),
    'mummy': dict(hp=22, hw=.3, hh=1.9, speed=2.2, hostile=True, drops=[(STRING, 0, 3), (ROTTEN_FLESH, 0, 1)],
                  sound='groan', dmg=3),
    'yeti': dict(hp=40, hw=.55, hh=2.3, speed=2.2, hostile=True, drops=[(WOOL_WHITE, 1, 3), (BEEF, 1, 2)],
                 sound='growl', dmg=6),
    'ghost': dict(hp=12, hw=.3, hh=1.5, speed=3., hostile=True, drops=[(STRING, 0, 1)], sound='hmm', dmg=2, ghost=True),
    'silly_king': dict(hp=300, hw=1.15, hh=3.0, speed=2., hostile=True, drops=[], sound='blorp', dmg=4, boss=True),
})
TRADES = [((EMERALD, 1), (BREAD, 4)), ((EMERALD, 2), (IRON_INGOT, 3)), ((EMERALD, 3), (SADDLE, 1)),
          ((EMERALD, 6), (DIAMOND, 1)), ((EMERALD, 1), (ARROW, 12)), ((EMERALD, 1), (TORCH, 12)),
          ((WHEAT, 12), (EMERALD, 1)), ((COAL, 10), (EMERALD, 1)), ((STRING, 8), (EMERALD, 1)),
          ((EMERALD, 4), (PARAGLIDER, 1)), ((EMERALD, 8), (GOLDEN_APPLE, 1)), ((RAW_FISH, 6), (EMERALD, 1)),
          ((EMERALD, 2), (FISHING_ROD, 1)), ((EMERALD, 3), (GRAPPLE, 1)), ((HONEY, 3), (EMERALD, 1))]
ROBES = ((.45, .3, .2), (.25, .45, .25), (.6, .55, .5), (.3, .3, .55), (.6, .25, .25))
HORSE_COLS = ((.5, .32, .18), (.2, .14, .1), (.85, .82, .78), (.62, .4, .22), (.35, .35, .38))
BIRD_COLS = (((.45, .3, .2), (.92, .46, .2)), ((.25, .42, .85), (.9, .92, .96)), ((.82, .12, .12), (.72, .1, .1)),
             ((.55, .45, .35), (.82, .74, .6)), ((.14, .14, .17), (.24, .24, .3)))
WING_COLS = ((.95, .6, .1), (.3, .5, .95), (.96, .96, .96), (.9, .3, .6), (.95, .85, .2))
FISH_COLS = ((.35, .55, .8), (.9, .55, .2), (.85, .85, .3), (.6, .35, .7))


def build_mob(kind):
    root, limbs, arms = NodePath('mob'), [], []

    def limb(x, y, top, w, ln, col, s, ax='p', d=None, lst=limbs):
        piv = root.attachNewNode('limb')
        piv.setPos(x, y, top)
        dd = w if d is None else d
        box_np(piv, (-w / 2, -dd / 2, -ln), (w / 2, dd / 2, 0), col)
        lst.append((piv, s, ax))
        return piv

    body = root.attachNewNode('body')

    def eyes(y, z, x, s=.045, col=(.05, .05, .05)):
        for sx in (-x, x):
            box_np(body, (sx - s, y, z - s), (sx + s, y + .02, z + s), col)
    B = lambda a, b, c: box_np(body, a, b, c)
    quad = ((-1, -1, 1), (1, -1, -1), (-1, 1, -1), (1, 1, 1))
    if kind == 'pig':
        P = (.95, .68, .68)
        B((-.3, -.45, .35), (.3, .45, .85), P)
        B((-.25, .38, .42), (.25, .82, .9), P)
        B((-.13, .82, .5), (.13, .88, .66), (.85, .5, .5))
        eyes(.82, .74, .14)
        for sx, sy, s in quad:
            limb(sx * .17, sy * .3, .36, .2, .36, P, s)
    elif kind == 'cow':
        C, W = (.35, .24, .15), (.9, .9, .88)
        B((-.35, -.6, .6), (.35, .6, 1.2), C)
        B((-.36, -.2, .8), (.36, .15, 1.1), W)
        B((-.25, .55, .8), (.25, .95, 1.3), C)
        B((-.15, .95, .82), (.15, 1.0, 1.0), (.75, .7, .65))
        B((-.32, .7, 1.22), (-.22, .78, 1.38), W)
        B((.22, .7, 1.22), (.32, .78, 1.38), W)
        eyes(.95, 1.15, .14)
        for sx, sy, s in quad:
            limb(sx * .22, sy * .42, .6, .2, .6, C, s)
    elif kind == 'sheep':
        W, F = (.93, .93, .93), (.72, .62, .57)
        B((-.38, -.55, .55), (.38, .55, 1.15), W)
        B((-.2, .5, .75), (.2, .88, 1.15), F)
        B((-.23, .48, 1.05), (.23, .75, 1.22), W)
        eyes(.88, 1.0, .11)
        for sx, sy, s in quad:
            limb(sx * .2, sy * .35, .55, .18, .55, F, s)
    elif kind == 'chicken':
        W = (.97, .97, .97)
        B((-.18, -.25, .25), (.18, .25, .55), W)
        B((-.12, .15, .5), (.12, .35, .82), W)
        B((-.08, .35, .62), (.08, .45, .7), (.95, .65, .1))
        B((-.04, .35, .52), (.04, .4, .62), (.85, .1, .1))
        B((-.21, -.15, .3), (-.18, .15, .5), W)
        B((.18, -.15, .3), (.21, .15, .5), W)
        eyes(.35, .76, .08, .025)
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .08, 0, .25, .06, .25, (.95, .7, .1), s)
    elif kind == 'zombie':
        G = (.35, .6, .3)
        B((-.25, -.13, .75), (.25, .13, 1.45), (.1, .65, .65))
        B((-.22, -.22, 1.45), (.22, .22, 1.9), G)
        eyes(.22, 1.7, .1, .04)
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .12, 0, .75, .24, .75, (.25, .25, .6), s)
            limb(sx * .35, 0, 1.4, .2, .7, G, 0, lst=arms).setP(90)
    elif kind == 'creeper':
        G, D = (.3, .75, .3), (.2, .55, .2)
        B((-.22, -.13, .45), (.22, .13, 1.25), G)
        B((-.23, -.14, .7), (.23, .14, .9), D)
        B((-.22, -.22, 1.25), (.22, .22, 1.7), G)
        eyes(.22, 1.55, .1, .05)
        B((-.05, .22, 1.3), (.05, .245, 1.48), (.05, .05, .05))
        B((-.11, .22, 1.3), (.11, .245, 1.38), (.05, .05, .05))
        for sx, sy, s in quad:
            limb(sx * .12, sy * .2, .45, .18, .45, G, s)
    elif kind == 'rabbit':
        C = (.62, .48, .34)
        B((-.13, -.2, .12), (.13, .18, .38), C)
        B((-.1, .12, .25), (.1, .32, .45), C)
        B((-.08, .2, .45), (-.03, .26, .7), C)
        B((.03, .2, .45), (.08, .26, .7), C)
        B((-.05, -.27, .2), (.05, -.2, .3), (.95, .95, .95))
        eyes(.32, .38, .06, .025)
        for sx in (-1, 1):
            limb(sx * .08, .1, .14, .07, .14, C, 1)
            limb(sx * .09, -.12, .16, .09, .16, C, -1)
    elif kind == 'fox':
        O, W, K = (.86, .46, .16), (.95, .92, .88), (.15, .1, .08)
        B((-.15, -.32, .3), (.15, .3, .55), O)
        B((-.16, .25, .35), (.16, .52, .6), O)
        B((-.07, .52, .36), (.07, .66, .46), W)
        B((-.03, .66, .42), (.03, .69, .46), K)
        B((-.15, .33, .6), (-.06, .4, .72), O)
        B((.06, .33, .6), (.15, .4, .72), O)
        eyes(.52, .52, .08, .03)
        B((-.08, -.62, .32), (.08, -.3, .48), O)
        B((-.07, -.74, .33), (.07, -.62, .46), W)
        for sx, sy, s in quad:
            limb(sx * .09, sy * .2, .3, .09, .3, K, s)
    elif kind == 'deer':
        Bn, L = (.56, .38, .22), (.85, .78, .65)
        B((-.22, -.5, .75), (.22, .45, 1.15), Bn)
        B((-.1, .35, 1.0), (.1, .55, 1.4), Bn)
        B((-.13, .45, 1.3), (.13, .78, 1.52), Bn)
        B((-.07, .78, 1.32), (.07, .86, 1.42), (.2, .15, .1))
        for sx in (-1, 1):
            B((sx * .1 - .02, .5, 1.52), (sx * .1 + .02, .55, 1.85), L)
            B((min(sx * .1, sx * .25), .5, 1.74), (max(sx * .1, sx * .25), .55, 1.78), L)
            B((sx * .2 - .02, .5, 1.78), (sx * .2 + .02, .55, 1.92), L)
        B((-.08, -.56, 1.0), (.08, -.5, 1.12), (.95, .95, .95))
        eyes(.78, 1.45, .11, .03)
        for sx, sy, s in quad:
            limb(sx * .13, sy * .35, .75, .1, .75, Bn, s)
    elif kind == 'goat':
        W, G = (.92, .9, .85), (.55, .52, .48)
        B((-.28, -.45, .55), (.28, .45, 1.0), W)
        B((-.15, .4, .8), (.15, .72, 1.15), W)
        B((-.05, .6, .65), (.05, .7, .82), W)
        B((-.13, .45, 1.15), (-.07, .55, 1.35), G)
        B((.07, .45, 1.15), (.13, .55, 1.35), G)
        eyes(.72, 1.02, .1, .03)
        for sx, sy, s in quad:
            limb(sx * .17, sy * .3, .55, .13, .55, W, s)
    elif kind == 'penguin':
        K, Wt, O = (.12, .12, .16), (.95, .95, .95), (.95, .6, .1)
        B((-.2, -.16, .12), (.2, .16, .85), K)
        B((-.15, .16, .15), (.15, .19, .68), Wt)
        B((-.04, .16, .7), (.04, .3, .76), O)
        eyes(.16, .77, .09, .03, (.95, .95, .95))
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .1, .05, .12, .12, .12, O, s, d=.2)
            limb(sx * .22, 0, .72, .05, .45, K, s, 'r', d=.18)
    elif kind == 'duck':
        Wd, G, Y, O = (.95, .95, .92), (.15, .5, .25), (.95, .8, .2), (.95, .55, .15)
        B((-.16, -.25, .15), (.16, .22, .4), Wd)
        B((-.1, .12, .35), (.1, .32, .6), G)
        B((-.06, .32, .42), (.06, .45, .48), Y)
        B((-.08, -.32, .3), (.08, -.22, .42), Wd)
        eyes(.32, .53, .07, .025)
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .08, 0, .15, .05, .15, O, s)
    elif kind == 'fish':
        C = random.choice(FISH_COLS)
        B((-.08, -.22, .05), (.08, .2, .3), C)
        B((-.02, -.05, .3), (.02, .1, .38), (.95, .6, .2))
        eyes(.2, .22, .06, .025)
        piv = root.attachNewNode('tail')
        piv.setPos(0, -.21, .18)
        box_np(piv, (-.02, -.17, -.1), (.02, 0, .1), (.95, .6, .2))
        limbs.append((piv, 1, 'h'))
    elif kind == 'skeleton':
        Gr, D = (.82, .82, .8), (.35, .35, .35)
        B((-.2, -.1, .75), (.2, .1, 1.45), Gr)
        B((-.21, -.11, .95), (.21, .11, 1.0), D)
        B((-.21, -.11, 1.15), (.21, .11, 1.2), D)
        B((-.21, -.21, 1.45), (.21, .21, 1.88), Gr)
        eyes(.21, 1.68, .09, .045)
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .1, 0, .75, .1, .75, Gr, s)
            limb(sx * .28, 0, 1.4, .09, .7, Gr, 0, lst=arms).setP(90)
        B((-.04, .66, 1.1), (.04, .72, 1.7), (.45, .3, .15))
    elif kind == 'spider':
        K, R = (.22, .18, .16), (.85, .1, .1)
        B((-.3, -.55, .25), (.3, .08, .62), K)
        B((-.2, .08, .25), (.2, .45, .55), K)
        B((-.14, .45, .42), (-.06, .47, .5), R)
        B((.06, .45, .42), (.14, .47, .5), R)
        B((-.05, .45, .33), (-.01, .47, .37), R)
        B((.01, .45, .33), (.05, .47, .37), R)
        for sx in (-1, 1):
            for i, ly in enumerate((.3, .12, -.06, -.24)):
                piv = root.attachNewNode('leg')
                piv.setPos(sx * .2, ly, .45)
                box_np(piv, (min(0, sx * .55), -.03, -.03), (max(0, sx * .55), .03, .03), K)
                box_np(piv, (sx * .55 - .03, -.03, -.45), (sx * .55 + .03, .03, 0), K)
                limbs.append((piv, (1 if i % 2 else -1) * sx, 'h'))
    elif kind == 'bird':
        bc, belly = random.choice(BIRD_COLS)
        B((-.08, -.14, .1), (.08, .12, .25), bc)
        B((-.075, .02, .1), (.075, .13, .2), belly)
        B((-.065, .07, .22), (.065, .2, .34), bc)
        B((-.02, .2, .26), (.02, .27, .3), (.95, .75, .2))
        eyes(.2, .3, .04, .016)
        B((-.04, -.27, .16), (.04, -.13, .2), bc)
        for sx in (-1, 1):
            B((sx * .04 - .01, -.01, 0), (sx * .04 + .01, .01, .1), (.6, .45, .2))
        for sx, s in ((-1, 1), (1, -1)):
            piv = root.attachNewNode('wing')
            piv.setPos(sx * .08, 0, .22)
            box_np(piv, (min(0, sx * .22), -.1, -.012), (max(0, sx * .22), .08, .012), tuple(c * .8 for c in bc))
            limbs.append((piv, s, 'r'))
    elif kind == 'butterfly':
        c = random.choice(WING_COLS)
        B((-.015, -.08, .08), (.015, .08, .11), (.1, .1, .1))
        for sx, s in ((-1, 1), (1, -1)):
            piv = root.attachNewNode('wing')
            piv.setPos(sx * .015, 0, .1)
            box_np(piv, (min(0, sx * .15), -.09, -.005), (max(0, sx * .15), .08, .005), c)
            box_np(piv, (min(sx * .05, sx * .1), -.02, -.006), (max(sx * .05, sx * .1), .03, .006), (.1, .1, .1))
            limbs.append((piv, s, 'r'))
    elif kind == 'horse':
        C = random.choice(HORSE_COLS)
        D = tuple(c * .55 for c in C)
        B((-.32, -.7, .75), (.32, .62, 1.25), C)
        B((-.14, .48, 1.05), (.14, .76, 1.75), C)
        B((-.15, .62, 1.6), (.15, 1.15, 1.9), C)
        B((-.04, .5, 1.25), (.04, .7, 2.0), D)
        B((-.12, .5, 1.88), (-.05, .58, 2.02), C)
        B((.05, .5, 1.88), (.12, .58, 2.02), C)
        B((-.06, -.82, .85), (.06, -.7, 1.2), D)
        eyes(1.0, 1.82, .15, .03)
        for sx, sy, s in quad:
            limb(sx * .2, sy * .45, .75, .16, .75, C, s)
        sad = root.attachNewNode('saddle')
        box_np(sad, (-.34, -.25, 1.24), (.34, .25, 1.33), (.42, .24, .12))
        box_np(sad, (-.36, -.05, .95), (-.32, .05, 1.25), (.3, .3, .32))
        box_np(sad, (.32, -.05, .95), (.36, .05, 1.25), (.3, .3, .32))
    elif kind == 'wolf':
        G, W = (.62, .62, .64), (.85, .85, .86)
        B((-.17, -.38, .35), (.17, .3, .66), G)
        B((-.18, .26, .38), (.18, .55, .68), G)
        B((-.08, .55, .4), (.08, .72, .52), W)
        B((-.15, .32, .68), (-.06, .4, .82), G)
        B((.06, .32, .68), (.15, .4, .82), G)
        B((-.06, -.62, .5), (.06, -.38, .62), G)
        eyes(.55, .6, .08, .03)
        for sx, sy, s in quad:
            limb(sx * .1, sy * .25, .35, .1, .35, G, s)
    elif kind == 'gloop':
        c = random.choice(((.35, .9, .55), (.95, .45, .8), (.45, .7, 1.)))
        B((-.38, -.38, 0), (.38, .38, .72), c)
        B((-.24, -.24, .1), (.24, .24, .5), tuple(x * .7 for x in c))
        eyes(.38, .5, .14, .06)
    elif kind == 'floatie':
        c = random.choice(((.6, .9, 1.), (1., .6, .9), (.8, .7, 1.)))
        B((-.32, -.32, .35), (.32, .32, .7), c)
        B((-.22, -.22, .7), (.22, .22, .8), tuple(min(1, x * 1.15) for x in c))
        for i in range(6):
            a = i * math.pi / 3
            piv = root.attachNewNode('tent')
            piv.setPos(math.cos(a) * .2, math.sin(a) * .2, .38)
            box_np(piv, (-.03, -.03, -.38), (.03, .03, 0), tuple(x * .85 for x in c))
            limbs.append((piv, 1 if i % 2 else -1, 'p'))
        eyes(.32, .55, .1, .04)
    elif kind == 'imp':
        P, K = (.55, .25, .7), (.95, .85, .3)
        B((-.18, -.1, .5), (.18, .1, .95), P)
        B((-.18, -.18, .95), (.18, .18, 1.25), P)
        B((-.16, -.04, 1.25), (-.1, .04, 1.42), K)
        B((.1, -.04, 1.25), (.16, .04, 1.42), K)
        eyes(.18, 1.12, .08, .035, (1., .9, .2))
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .09, 0, .5, .1, .5, P, s)
            limb(sx * .25, 0, .92, .08, .4, P, -s)
    elif kind == 'hopper':
        C = random.choice(((.95, .8, .95), (.75, .9, 1.), (1., .9, .7)))
        B((-.35, -.5, .35), (.35, .45, 1.05), C)
        B((-.25, .35, .85), (.25, .75, 1.3), C)
        B((-.2, .5, 1.3), (-.1, .6, 1.85), C)
        B((.1, .5, 1.3), (.2, .6, 1.85), C)
        B((-.1, -.6, .6), (.1, -.5, .8), (1, 1, 1))
        eyes(.75, 1.12, .13, .04)
        for sx, sy, s in quad:
            limb(sx * .22, sy * .3, .38, .18, .38, C, s)
        sad = root.attachNewNode('saddle')
        box_np(sad, (-.37, -.2, 1.04), (.37, .25, 1.12), (.42, .24, .12))
    elif kind == 'turtle':
        G, S = (.35, .55, .3), (.45, .35, .2)
        B((-.3, -.35, .08), (.3, .35, .38), S)
        B((-.22, -.28, .38), (.22, .28, .45), tuple(c * 1.15 for c in S))
        B((-.1, .32, .1), (.1, .55, .28), G)
        eyes(.55, .22, .06, .025)
        for sx, sy, s in quad:
            limb(sx * .3, sy * .25, .12, .12, .1, G, s, d=.18)
    elif kind == 'bear':
        Bn = (.35, .24, .15)
        B((-.42, -.6, .5), (.42, .55, 1.15), Bn)
        B((-.3, .45, .7), (.3, .9, 1.2), Bn)
        B((-.14, .9, .75), (.14, 1.05, .95), (.55, .42, .3))
        B((-.28, .55, 1.2), (-.16, .65, 1.32), Bn)
        B((.16, .55, 1.2), (.28, .65, 1.32), Bn)
        eyes(.9, 1.05, .14, .035)
        for sx, sy, s in quad:
            limb(sx * .25, sy * .38, .5, .26, .5, Bn, s)
    elif kind in ('villager', 'mummy'):
        robe = random.choice(ROBES) if kind == 'villager' else (.85, .82, .7)
        skin = (.75, .55, .42) if kind == 'villager' else (.8, .76, .62)
        B((-.25, -.15, .7), (.25, .15, 1.45), robe)
        B((-.21, -.21, 1.45), (.21, .21, 1.9), skin)
        B((-.05, .21, 1.55), (.05, .3, 1.7), tuple(c * .9 for c in skin))
        if kind == 'mummy':
            for z in (.85, 1.05, 1.25, 1.6, 1.78):
                B((-.26, -.16, z), (.26, .16, z + .04), (.65, .62, .52))
        eyes(.21, 1.72, .1, .035, (.1, .3, .1) if kind == 'villager' else (.1, .1, .1))
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .12, 0, .75, .22, .75, tuple(c * .8 for c in robe), s)
            a_ = limb(sx * .32, 0, 1.4, .16, .62, robe if kind == 'villager' else skin, 0, lst=arms)
            a_.setP(90 if kind == 'mummy' else 35)
    elif kind == 'yeti':
        W = (.92, .94, .97)
        B((-.5, -.32, .95), (.5, .32, 1.9), W)
        B((-.3, -.3, 1.9), (.3, .3, 2.35), W)
        B((-.2, .29, 1.95), (.2, .31, 2.2), (.55, .6, .7))
        eyes(.31, 2.12, .1, .04)
        for sx, s in ((-1, 1), (1, -1)):
            limb(sx * .25, 0, .95, .3, .95, W, s)
            limb(sx * .62, 0, 1.85, .24, 1.1, W, -s)
    elif kind == 'ghost':
        Wt = (.9, .95, 1.)
        B((-.3, -.3, .3), (.3, .3, 1.5), Wt)
        B((-.25, -.25, 0), (.25, .25, .3), tuple(c * .9 for c in Wt))
        B((-.14, .3, 1.15), (-.05, .31, 1.3), (.05, .05, .1))
        B((.05, .3, 1.15), (.14, .31, 1.3), (.05, .05, .1))
        B((-.08, .3, .85), (.08, .31, .98), (.05, .05, .1))
    elif kind == 'bee':
        Y, K = (.98, .8, .15), (.1, .08, .05)
        B((-.07, -.12, .05), (.07, .12, .18), Y)
        for yy in (-.06, .02):
            B((-.075, yy, .05), (.075, yy + .035, .185), K)
        for sx, s in ((-1, 1), (1, -1)):
            piv = root.attachNewNode('wing')
            piv.setPos(sx * .06, 0, .18)
            box_np(piv, (min(0, sx * .12), -.05, -.004), (max(0, sx * .12), .05, .004), (.9, .95, 1.))
            limbs.append((piv, s, 'r'))
    elif kind == 'ant':
        K = (.12, .06, .04)
        B((-.025, -.07, 0), (.025, -.02, .04), K)
        B((-.02, -.02, 0), (.02, .02, .035), K)
        B((-.025, .02, 0), (.025, .06, .04), K)
    elif kind == 'dragonfly':
        c = random.choice(((.2, .6, .9), (.3, .8, .4), (.8, .3, .4)))
        B((-.02, -.18, .05), (.02, .12, .09), c)
        B((-.035, .1, .04), (.035, .16, .1), c)
        for yy in (.02, -.04):
            for sx, s in ((-1, 1), (1, -1)):
                piv = root.attachNewNode('wing')
                piv.setPos(sx * .02, yy, .09)
                box_np(piv, (min(0, sx * .16), -.025, -.003), (max(0, sx * .16), .025, .003), (.85, .92, 1.))
                limbs.append((piv, s, 'r'))
    elif kind == 'silly_king':
        J, C = (.95, .45, .85), (1., .8, .2)
        B((-1.1, -1.1, 0), (1.1, 1.1, 2.3), J)
        B((-.8, -.8, .2), (.8, .8, 1.8), (.75, .3, .7))
        for i in range(6):
            a_ = i * math.pi / 3
            x, y = math.cos(a_) * .75, math.sin(a_) * .75
            B((x - .14, y - .14, 2.3), (x + .14, y + .14, 2.85 + .15 * (i % 2)), C)
        B((-.8, -.8, 2.3), (.8, .8, 2.45), C)
        B((-.5, 1.1, 1.45), (-.2, 1.12, 1.8), (1, 1, 1))
        B((.2, 1.1, 1.45), (.5, 1.12, 1.8), (1, 1, 1))
        B((-.4, 1.12, 1.5), (-.28, 1.13, 1.65), (.1, .05, .15))
        B((.28, 1.12, 1.5), (.4, 1.13, 1.65), (.1, .05, .15))
        B((-.4, 1.1, .8), (.4, 1.12, .95), (.4, .1, .3))
    elif kind == 'frog':
        G, L = (.36, .62, .26), (.86, .86, .62)
        B((-.15, -.16, .05), (.15, .15, .22), G)
        B((-.12, .05, .05), (.12, .16, .15), L)
        for sx in (-1, 1):
            B((sx * .085 - .035, .07, .2), (sx * .085 + .035, .14, .27), G)
            B((sx * .085 - .02, .14, .225), (sx * .085 + .02, .145, .255), (.05, .05, .05))
        for sx, sy, s in quad:
            limb(sx * .14, sy * .08, .08, .07, .08, G, s)
    body.flattenStrong()
    root.setTextureOff(1)
    return root, limbs, arms


def ray_aabb(o, d, mn, mx):
    t0, t1 = 0., 1e9
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < mn[i] or o[i] > mx[i]:
                return None
        else:
            a, b = (mn[i] - o[i]) / d[i], (mx[i] - o[i]) / d[i]
            if a > b:
                a, b = b, a
            t0, t1 = max(t0, a), min(t1, b)
            if t0 > t1:
                return None
    return t0


def inside(e, p, pad=0.):
    return (e.pos[0] - e.hw - pad <= p[0] <= e.pos[0] + e.hw + pad and e.pos[1] - e.hw - pad <= p[1] <= e.pos[1] + e.hw + pad
            and e.pos[2] - pad <= p[2] <= e.pos[2] + e.hh + pad)


class Mob(Body):
    def __init__(self, game, kind, pos):
        d = MOBDEF[kind]
        Body.__init__(self, game, pos, d['hw'], d['hh'])
        self.kind, self.d, self.hp = kind, d, d['hp']
        self.node, self.limbs, self.arms = build_mob(kind)
        self.node.reparentTo(game.ent_root)
        self.h = self.th = random.uniform(0, 360)
        self.walk, self.ai_t, self.hurt_t, self.panic, self.dead = False, 0., 0., 0., -1.
        self.atk, self.fuse, self.anim, self.burn_t, self.dry_t, self.swim_dz = 0., 0., 0., 0., 0., 0.
        self.snd_t = random.uniform(10, 40)
        self.flying = kind in ('butterfly', 'floatie', 'bee', 'dragonfly', 'ghost')
        self.trade = random.choice(TRADES) if kind == 'villager' else None
        self.hop_t, self.vol_t, self.sum_t, self.was_air, self.altar = 1.5, 4., 9., False, None
        if kind == 'ghost':
            self.node.setTransparency(TransparencyAttrib.MAlpha)
            self.node.setAlphaScale(.55)
        self.rider, self.angry = None, 0.
        self.saddle = self.node.find('saddle')
        self.saddled = False
        if not self.saddle.isEmpty():
            self.saddle.hide()
        self.landing, self.goal = False, tuple(self.pos)
        self.node.setPos(*self.pos)

    def head_to(self, vx, vy):
        return math.degrees(math.atan2(-vx, vy))

    def update(self, dt):
        g, p, d = self.game, self.game.player, self.d
        if self.dead >= 0:
            self.dead += dt
            self.node.setR(min(90, self.dead * 250))
            if self.dead > .7:
                self.gone = True
                if d.get('boss'):
                    g.boss_defeated(self)
                for it, a, b in d['drops']:
                    c = random.randint(a, b)
                    if c:
                        g.spawn_item((self.pos[0], self.pos[1], self.pos[2] + .5), it, c)
                g.puff(self.pos)
            return
        dx, dy, dz = p.pos[0] - self.pos[0], p.pos[1] - self.pos[1], p.pos[2] - self.pos[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        hostile = d.get('hostile', False)
        if d.get('ghost') and g.daylight > .6:
            g.puff(self.pos)
            self.gone = True
            return
        if not self.saddled and not d.get('boss') and (dist > g.settings['render_dist'] * 16 + 16 or
                                 (hostile and (dist > 90 or g.settings['difficulty'] == 0)) or not g.world.loaded(*self.pos[:2])):
            self.gone = True
            return
        self.angry -= dt
        active = (hostile or self.angry > 0) and g.mode == 'survival' and not p.dead and \
            dist < (20 if self.kind == 'spider' else 24) and self.rider is None
        self.check_fluids()
        if self.rider is not None:
            self.ride_ai(dt)
        elif d.get('boss'):
            self.boss_ai(dt, dx, dy, dist, active)
        elif d.get('ghost'):
            if active:
                self.goal = (p.pos[0], p.pos[1], p.pos[2] + 1.)
                self.steer(dt, d['speed'], 2.)
                self.move(dt)
            else:
                self.flutter_ai(dt)
        elif d.get('fish'):
            self.fish_ai(dt, dx, dy, dist)
        elif d.get('bird'):
            self.bird_ai(dt, dist)
        elif d.get('flutter'):
            if g.daylight < .35 and self.kind == 'butterfly':
                self.gone = True
                return
            self.flutter_ai(dt)
        else:
            speed = 0.
            if active:
                self.th, speed = self.head_to(dx, dy), d['speed']
                if d.get('ranged'):
                    if dist < 7:
                        self.th, speed = self.head_to(-dx, -dy), d['speed'] * .8
                    elif dist < 13:
                        speed = 0.
            elif d.get('skittish') and dist < 7 and not p.dead and not p.sneak:
                self.th, speed = self.head_to(-dx, -dy), d['speed'] * 1.5
            elif self.panic > 0:
                self.panic -= dt
                self.ai_t -= dt
                if self.ai_t <= 0:
                    self.th, self.ai_t = random.uniform(0, 360), random.uniform(.5, 1.2)
                speed = d['speed'] * 1.9
            else:
                self.ai_t -= dt
                if self.ai_t <= 0:
                    self.walk, self.th, self.ai_t = random.random() < .55, random.uniform(0, 360), random.uniform(2, 6)
                speed = d['speed'] * .6 if self.walk else 0.
            diff = (self.th - self.h + 180) % 360 - 180
            self.h += max(-400 * dt, min(400 * dt, diff))
            hr = math.radians(self.h)
            f = min(1., (10 if self.on_ground else 2) * dt)
            self.vel[0] += (-math.sin(hr) * speed + self.flow[0] * 2 - self.vel[0]) * f
            self.vel[1] += (math.cos(hr) * speed + self.flow[1] * 2 - self.vel[1]) * f
            if self.in_water or self.in_lava:
                self.vel[2] = min(self.vel[2] + 16 * dt, 2.)
            else:
                self.vel[2] = max(-50, self.vel[2] - 32 * dt)
            if speed > 0:
                if self.hit_wall and d.get('climb'):
                    self.vel[2] = 4.
                elif self.hit_wall and self.on_ground:
                    self.vel[2] = d.get('jump', 8.6)
                elif d.get('hop') and self.on_ground:
                    self.vel[2] = 5.5
            self.move(dt)
        if self.in_lava:
            self.hurt(4)
        sp = math.hypot(self.vel[0], self.vel[1])
        flap = 6. if (self.flying and d.get('bird')) else (5. if d.get('flutter') else 0.)
        self.anim += dt * max(sp, 1.5 if d.get('fish') else 0, flap) * 4
        a = math.sin(self.anim) * min(1., max(sp, 1.5 if d.get('fish') else 0, flap) / 1.5) * (55 if flap else 35)
        for piv, s, ax in self.limbs:
            if ax == 'p':
                piv.setP(a * s)
            elif ax == 'h':
                piv.setH(a * s * .7)
            else:
                piv.setR(a * s * .8)
        self.atk -= dt
        mult = (.5, .5, 1, 1.5)[g.settings['difficulty']]
        if 'dmg' in d:
            for arm, _, _ in self.arms:
                arm.setP(90 - max(0, self.atk) * 60)
            if active and dist < 1.3 + self.hw and abs(dz) < 1.6 and self.atk <= 0:
                if p.hurt(d['dmg'] * mult, self.pos):
                    self.atk = 1.
        if d.get('ranged') and active and 3 < dist < 16 and self.atk <= 0:
            eye = (self.pos[0], self.pos[1], self.pos[2] + 1.6)
            tgt = (p.pos[0], p.pos[1], p.pos[2] + 1.4)
            v = [tgt[i] - eye[i] for i in range(3)]
            L = math.sqrt(sum(c * c for c in v))
            if g.world.raycast(eye, [c / L for c in v], L, OPAQUE)[0] is None:
                g.shoot_arrow(eye, tgt, self, 22., 3. * mult, (.12, .08, .04, .02)[g.settings['difficulty']],
                              'shard' if d.get('shard') else 'arrow')
                self.atk = random.uniform(1.8, 2.6)
        if d.get('burns') and g.daylight > .65 and not self.in_water:
            sk, _ = g.world.light_at(math.floor(self.pos[0]), math.floor(self.pos[1]), math.floor(self.pos[2] + self.hh))
            if sk >= 14:
                self.burn_t += dt
                if self.burn_t > 1:
                    self.burn_t = 0
                    self.hurt(1, kb=0)
                    g.particles((self.pos[0], self.pos[1], self.pos[2] + 1), 6, color=(1, .5, .1), up=True)
        tint = 1.
        if self.kind == 'creeper':
            if active and dist < 3.2:
                if self.fuse == 0:
                    g.sounds.play('hiss', self.pos)
                self.fuse += dt
            elif dist > 6 or not active:
                self.fuse = max(0., self.fuse - dt)
            if self.fuse >= 1.5:
                self.gone = True
                g.world.explode(self.pos[0], self.pos[1], self.pos[2] + .8, 3.0)
                return
            if self.fuse > 0:
                tint = 1 + (int(self.fuse * 8) % 2) * 1.2
                self.node.setScale(1 + self.fuse * .1)
        self.snd_t -= dt
        if self.snd_t <= 0:
            self.snd_t = random.uniform(18, 45)
            if d['sound'] and dist < 20 and g.mob_snd_t <= 0:
                g.mob_snd_t = 3.
                g.sounds.play(d['sound'], self.pos, .55)
        if self.hurt_t > 0:
            self.hurt_t -= dt
        L = g.light_scale(self.pos[0], self.pos[1], self.pos[2] + self.hh * .7) * tint
        if self.hurt_t > 0:
            self.node.setColorScale(L, L * .45, L * .45, 1)
        else:
            self.node.setColorScale(L, L, L, 1)
        self.node.setPos(*self.pos)
        self.node.setH(self.h)

    def fish_ai(self, dt, dx, dy, dist):
        w, sp = self.game.world, self.d['speed']
        if self.in_water:
            self.dry_t = 0.
            self.ai_t -= dt
            if self.ai_t <= 0 or self.hit_wall:
                self.th, self.ai_t = random.uniform(0, 360), random.uniform(1, 4)
                self.swim_dz = random.uniform(-.6, .6)
            if dist < 5 and not self.game.player.dead:
                self.th, sp = self.head_to(-dx, -dy), sp * 1.6
            hr = math.radians(self.th)
            ahead = w.get(math.floor(self.pos[0] - math.sin(hr) * .8), math.floor(self.pos[1] + math.cos(hr) * .8),
                          math.floor(self.pos[2] + .15))
            if FAMILY[ahead] != WATER:
                self.th += 180
                hr = math.radians(self.th)
            if FAMILY[w.get(math.floor(self.pos[0]), math.floor(self.pos[1]), math.floor(self.pos[2] + .6))] != WATER:
                self.swim_dz = -.5
            diff = (self.th - self.h + 180) % 360 - 180
            self.h += max(-300 * dt, min(300 * dt, diff))
            f = min(1., 3 * dt)
            self.vel[0] += (-math.sin(hr) * sp - self.vel[0]) * f
            self.vel[1] += (math.cos(hr) * sp - self.vel[1]) * f
            self.vel[2] += (self.swim_dz - self.vel[2]) * f
        else:
            self.vel[2] = max(-40, self.vel[2] - 30 * dt)
            self.vel[0] *= max(0, 1 - 5 * dt)
            self.vel[1] *= max(0, 1 - 5 * dt)
            if self.on_ground and random.random() < 3 * dt:
                self.vel = [random.uniform(-2, 2), random.uniform(-2, 2), 5.]
                self.h = random.uniform(0, 360)
            self.dry_t += dt
            if self.dry_t > 2:
                self.dry_t = 0.
                self.hurt(1, kb=0)
        self.move(dt)

    def set_goal(self, rad, dzlo, dzhi):
        self.goal = (self.pos[0] + random.uniform(-rad, rad), self.pos[1] + random.uniform(-rad, rad),
                     min(H - 4., self.pos[2] + random.uniform(dzlo, dzhi)))
        self.landing = False

    def steer(self, dt, sp, k=3.):
        v = [self.goal[i] - self.pos[i] for i in range(3)]
        d = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.
        sp = min(sp, d * 2.5) if self.landing else sp
        f = min(1., k * dt)
        for i in range(3):
            self.vel[i] += (v[i] / d * sp - self.vel[i]) * f
        if math.hypot(self.vel[0], self.vel[1]) > .2:
            self.h = self.head_to(self.vel[0], self.vel[1])
        return d

    def bird_ai(self, dt, dist):
        g, w = self.game, self.game.world
        p = g.player
        if not self.flying:
            self.vel[2] = max(-30., self.vel[2] - 32 * dt)
            self.vel[0] *= max(0., 1 - 6 * dt)
            self.vel[1] *= max(0., 1 - 6 * dt)
            self.ai_t -= dt
            if self.ai_t <= 0:
                self.ai_t = random.uniform(.6, 2.5)
                if self.on_ground and random.random() < .4:
                    self.h = random.uniform(0, 360)
                    hr = math.radians(self.h)
                    self.vel = [-math.sin(hr) * 1.5, math.cos(hr) * 1.5, 3.5]
            if (dist < 7 and not p.dead and not p.sneak) or random.random() < dt / 40. or self.in_water:
                self.flying = True
                self.set_goal(24, 6, 14)
                self.vel[2] = 4.
        else:
            d = self.steer(dt, self.d['speed'])
            if self.hit_wall:
                self.goal = (self.goal[0], self.goal[1], self.goal[2] + 4)
            if d < 1.0:
                if self.landing:
                    self.flying, self.vel = False, [0., 0., 0.]
                elif random.random() < .45:
                    tx, ty = int(math.floor(self.goal[0] + random.uniform(-6, 6))), int(math.floor(self.goal[1] + random.uniform(-6, 6)))
                    tz = w.surface_z(tx, ty, int(self.pos[2]) + 12)
                    if tz is not None:
                        self.goal, self.landing = (tx + .5, ty + .5, tz + 1.05), True
                    else:
                        self.set_goal(20, -4, 6)
                else:
                    self.set_goal(20, -4, 6)
        self.move(dt)

    def flutter_ai(self, dt):
        w = self.game.world
        self.ai_t -= dt
        if self.ai_t <= 0 or self.hit_wall:
            self.ai_t = random.uniform(.8, 2.5)
            tx, ty = self.pos[0] + random.uniform(-4, 4), self.pos[1] + random.uniform(-4, 4)
            gz = w.surface_z(int(math.floor(tx)), int(math.floor(ty)), int(self.pos[2]) + 4)
            lo, hi = self.d.get('alt', (1.6, 3.2))
            self.goal = (tx, ty, (gz if gz is not None else self.pos[2] - 1) + random.uniform(lo, hi))
        self.steer(dt, self.d['speed'], 2.)
        self.vel[2] += math.sin(self.anim * .7) * 6 * dt
        self.move(dt)

    def boss_ai(self, dt, dx, dy, dist, active):
        g, d, p = self.game, self.d, self.game.player
        rage = self.hp < d['hp'] * .5
        mult = (.5, .5, 1, 1.5)[g.settings['difficulty']]
        if dist > .5:
            self.h = self.head_to(dx, dy)
        self.vel[2] = max(-50, self.vel[2] - 30 * dt)
        if self.on_ground:
            if self.was_air:                           # landing shockwave
                g.shake = max(g.shake, .5)
                g.sounds.play('explode', self.pos, .5)
                for i in range(16):
                    a_ = i * math.pi / 8
                    g.fx.append(Particle(g, (self.pos[0] + math.cos(a_) * 2, self.pos[1] + math.sin(a_) * 2, self.pos[2] + .2),
                                         (math.cos(a_) * 6, math.sin(a_) * 6, 1.), color=(1., .6, .95), life=.6, size=.18, grav=2))
                if active and dist < 6 and p.on_ground:
                    p.inv_t = 0.
                    p.hurt(5 * mult, self.pos)
            self.vel[0] *= max(0., 1 - 8 * dt)
            self.vel[1] *= max(0., 1 - 8 * dt)
            self.hop_t -= dt
            if active and self.hop_t <= 0:
                n = max(1e-3, math.hypot(dx, dy))
                sp = min(n, 9.) * (1.35 if rage else 1.)
                self.vel = [dx / n * sp, dy / n * sp, 11.]
                self.hop_t = 1.5 if rage else 2.5
        self.was_air = not self.on_ground
        if active:
            self.vol_t -= dt
            if self.vol_t <= 0 and dist < 32:
                eye = (self.pos[0], self.pos[1], self.pos[2] + 2.)
                for k in range(7 if rage else 5):
                    tgt = (p.pos[0] + random.uniform(-2, 2), p.pos[1] + random.uniform(-2, 2), p.pos[2] + 1.)
                    g.shoot_arrow(eye, tgt, self, 20., 3. * mult, .04, 'shard')
                self.vol_t = 3.5 if rage else 5.5
            self.sum_t -= dt
            if self.sum_t <= 0:
                for _ in range(2 if not rage else 3):
                    g.spawn_mob('gloop', (self.pos[0] + random.uniform(-3, 3), self.pos[1] + random.uniform(-3, 3), self.pos[2] + 1))
                self.sum_t = 10. if rage else 14.
        self.move(dt)

    def ride_ai(self, dt):
        g, d, r = self.game, self.d, self.rider
        ok = g.state == 'playing' and not g.chat_open and not g.typing()
        k = g.key if ok else (lambda n: False)
        fwd, st = k('w') - k('s'), k('d') - k('a')
        hr = math.radians(r.h)
        mx, my = -math.sin(hr) * fwd + math.cos(hr) * st, math.cos(hr) * fwd + math.sin(hr) * st
        n = math.hypot(mx, my)
        if n:
            mx, my = mx / n, my / n
        sp = d['mount'][0] * (1.35 if k('ctrl') else 1.)
        self.h = r.h
        f = min(1., (8 if self.on_ground else 2.5) * dt)
        self.vel[0] += (mx * sp - self.vel[0]) * f
        self.vel[1] += (my * sp - self.vel[1]) * f
        if self.in_water:
            self.vel[2] = min(self.vel[2] + 16 * dt, 2.)
        else:
            self.vel[2] = max(-50, self.vel[2] - 32 * dt)
        if self.on_ground and (k('space') or (d.get('hop') and n)):
            self.vel[2] = d['mount'][1] * (1. if k('space') else .55)
        self.move(dt)

    def hurt(self, dmg, src=None, kb=6.):
        if self.dead >= 0 or self.hurt_t > .2:
            return False
        if self.d.get('neutral'):
            self.angry = 25.
        if self.d.get('boss'):
            kb = 0.
        g = self.game
        self.hp -= dmg
        self.hurt_t = .45
        if src is not None and kb:
            dx, dy = self.pos[0] - src[0], self.pos[1] - src[1]
            n = math.hypot(dx, dy) or 1
            self.vel[0], self.vel[1], self.vel[2] = dx / n * kb, dy / n * kb, 5.5
        if not self.d.get('hostile'):
            self.panic = 5.
        g.sounds.play(self.d['sound'] or 'hurt', self.pos)
        if self.hp <= 0:
            self.dead = 0.
            g.sounds.play('death', self.pos, .6)
        return True

    def ray(self, o, d):
        return ray_aabb(o, d, (self.pos[0] - self.hw, self.pos[1] - self.hw, self.pos[2]),
                        (self.pos[0] + self.hw, self.pos[1] + self.hw, self.pos[2] + self.hh))


class Arrow:
    def __init__(self, game, pos, vel, shooter, dmg, style='arrow'):
        self.game, self.pos, self.vel, self.shooter, self.dmg = game, list(pos), list(vel), shooter, dmg
        self.gone = self.stuck = False
        self.age, self.style = 0., style
        self.node = NodePath('arrow')
        if style == 'pebble':
            box_np(self.node, (-.07, -.07, -.06), (.07, .07, .06), (.55, .54, .52))
        elif style == 'shard':
            box_np(self.node, (-.04, -.25, -.04), (.04, .25, .04), (.8, .6, 1.))
            box_np(self.node, (-.02, .25, -.02), (.02, .35, .02), (1., .9, 1.))
        else:
            box_np(self.node, (-.02, -.35, -.02), (.02, .3, .02), (.55, .4, .25))
            box_np(self.node, (-.04, .3, -.04), (.04, .4, .04), (.7, .7, .75))
            box_np(self.node, (-.06, -.38, -.01), (.06, -.22, .01), (.95, .95, .95))
        self.node.setTextureOff(1)
        self.node.reparentTo(game.ent_root)
        self.node.setPos(*self.pos)

    def update(self, dt):
        g, w = self.game, self.game.world
        self.age += dt
        if self.age > 40:
            self.gone = True
            return
        if self.stuck:
            p = g.player
            if self.shooter is p and not p.dead and math.dist(self.pos, (p.pos[0], p.pos[1], p.pos[2] + .9)) < 1.5:
                if g.mode == 'survival' and self.style != 'shard' and p.add_item(PEBBLE if self.style == 'pebble' else ARROW, 1) == 0:
                    g.sounds.play('pop', None, .5)
                    g.refresh_inv()
                self.gone = True
            return
        self.vel[2] -= 20 * dt
        sp = math.sqrt(sum(v * v for v in self.vel))
        n = int(sp * dt / .25) + 1
        targets = ([g.player] if self.shooter is not g.player and not g.player.dead else []) + \
                  [m for m in g.mobs if m is not self.shooter and m.dead < 0]
        for _ in range(n):
            q = [self.pos[i] + self.vel[i] * dt / n for i in range(3)]
            b = w.get(math.floor(q[0]), math.floor(q[1]), math.floor(q[2]))
            if SOLID[b]:
                self.stuck = True
                g.sounds.play('click', self.pos, .6)
                break
            self.pos = q
            for e in targets:
                if inside(e, q, .1):
                    e.hurt(max(1, int(self.dmg * sp / 22.)), (q[0] - self.vel[0], q[1] - self.vel[1], q[2]))
                    if self.shooter is g.player and isinstance(e, Mob):
                        g.adv('bow')
                    self.gone = True
                    return
        self.node.setPos(*self.pos)
        if not self.stuck:
            self.node.lookAt(self.pos[0] + self.vel[0], self.pos[1] + self.vel[1], self.pos[2] + self.vel[2])
        L = g.light_scale(*self.pos)
        self.node.setColorScale(L, L, L, 1)


class ItemDrop(Body):
    def __init__(self, game, pos, item, count, vel=None):
        Body.__init__(self, game, pos, .125, .25)
        self.item, self.count, self.age = item, count, 0.
        self.vel = list(vel) if vel else [random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5), 4.]
        self.node = game.item_model(item, .3)
        self.node.reparentTo(game.ent_root)
        self.spin = random.uniform(0, 360)

    def update(self, dt):
        self.age += dt
        if self.age > 300 or self.pos[2] < -10:
            self.gone = True
            return
        self.check_fluids()
        if self.in_lava:
            self.gone = True
            self.game.sounds.play('fizz', self.pos, .5)
            return
        if self.in_water:
            self.vel[2] = min(self.vel[2] + 14 * dt, 1.)
            self.vel[0] += self.flow[0] * 6 * dt
            self.vel[1] += self.flow[1] * 6 * dt
        else:
            self.vel[2] = max(-40, self.vel[2] - 25 * dt)
        fr = min(1., (8 if self.on_ground else .5) * dt)
        self.vel[0] -= self.vel[0] * fr
        self.vel[1] -= self.vel[1] * fr
        self.move(dt)
        g, p = self.game, self.game.player
        if self.age > .6 and not p.dead and g.state in ('playing', 'inventory', 'paused'):
            tgt = (p.pos[0], p.pos[1], p.pos[2] + .8)
            d = math.dist(self.pos, tgt)
            if 1.2 < d < 3.2 and p.count_free(self.item):
                for i in range(3):                          # magnet towards the player
                    self.vel[i] += (tgt[i] - self.pos[i]) / d * 30 * dt
            if d < 1.3:
                left = p.add_item(self.item, self.count)
                if left < self.count:
                    g.sounds.play('pop', None, .5)
                    g.refresh_inv()
                self.count = left
                if left == 0:
                    self.gone = True
                    return
        self.spin += dt * 90
        self.node.setPos(self.pos[0], self.pos[1], self.pos[2] + .14 + math.sin(self.age * 3) * .05)
        self.node.setH(self.spin)
        L = g.light_scale(self.pos[0], self.pos[1], self.pos[2] + .3)
        self.node.setColorScale(L, L, L, 1)


class FallingBlock(Body):
    def __init__(self, game, x, y, z, b):
        Body.__init__(self, game, (x + .5, y + .5, z), .49, .98)
        self.b = b
        self.node = cube_np(TEXIDX[b], 1., (-.5, -.5, 0))
        self.node.reparentTo(game.ent_root)
        self.node.setPos(*self.pos)

    def update(self, dt):
        self.vel[2] = max(-40, self.vel[2] - 30 * dt)
        self.move(dt)
        if self.on_ground or self.pos[2] < 0:
            self.gone = True
            w = self.game.world
            x, y, z = (int(math.floor(v)) for v in (self.pos[0], self.pos[1], self.pos[2] + .01))
            if REPL[w.get(x, y, z)]:
                w.set(x, y, z, self.b)
            else:
                self.game.spawn_item(self.pos, self.b, 1)
        self.node.setPos(*self.pos)
        L = self.game.light_scale(self.pos[0], self.pos[1], self.pos[2] + .5)
        self.node.setColorScale(L, L, L, 1)


class PrimedTNT(FallingBlock):
    def __init__(self, game, x, y, z, fuse=4.):
        FallingBlock.__init__(self, game, x, y, z, TNT)
        self.fuse = fuse
        self.vel = [random.uniform(-1, 1), random.uniform(-1, 1), 4.]
        game.sounds.play('hiss', self.pos, .6)

    def update(self, dt):
        self.vel[2] = max(-40, self.vel[2] - 30 * dt)
        self.vel[0] *= max(0, 1 - 3 * dt)
        self.vel[1] *= max(0, 1 - 3 * dt)
        self.move(dt)
        self.fuse -= dt
        fl = 1 + (int(self.fuse * 5) % 2) * 1.5
        self.node.setColorScale(fl, fl, fl, 1)
        self.node.setScale(1 + max(0, .5 - self.fuse) * .3)
        self.node.setPos(*self.pos)
        if self.fuse <= 0:
            self.gone = True
            self.game.world.explode(self.pos[0], self.pos[1], self.pos[2] + .5, 4.)


class Particle:
    def __init__(self, game, pos, vel, tile=None, color=None, life=.7, size=.1, grav=18.):
        self.game, self.pos, self.vel, self.life, self.grav, self.gone = game, list(pos), list(vel), life, grav, False
        cm = CardMaker('p')
        cm.setFrame(-size, size, -size, size)
        if tile is not None:
            u0, v0, u1, v1 = tile_uv(tile)
            du, dv = random.uniform(0, .75) * (u1 - u0), random.uniform(0, .75) * (v1 - v0)
            cm.setUvRange((u0 + du, v0 + dv), (u0 + du + (u1 - u0) / 4, v0 + dv + (v1 - v0) / 4))
        self.node = game.ent_root.attachNewNode(cm.generate())
        if tile is None:
            self.node.setTextureOff(1)
            self.node.setColor(*color, 1)
        else:
            L = game.light_scale(*pos)
            self.node.setColorScale(L, L, L, 1)
        self.node.setBillboardPointEye()
        self.node.setPos(*pos)

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.gone = True
            return
        self.vel[2] -= self.grav * dt
        np_ = [self.pos[i] + self.vel[i] * dt for i in range(3)]
        if SOLID[self.game.world.get(*(int(math.floor(v)) for v in np_))]:
            self.vel = [0., 0., 0.]
        else:
            self.pos = np_
        self.node.setPos(*self.pos)


class Player(Body):
    def __init__(self, game):
        Body.__init__(self, game, (0, 0, H), .3, 1.8)
        self.h = self.p = 0.
        self.hp, self.food, self.air, self.exhaust = 20, 20, 10., 0.
        self.regen_t = self.drown_t = self.inv_t = self.jump_cd = 0.
        self.inv, self.sel = [None] * 36, 0
        self.flying = self.dead = self.sneak = self.sprint = False
        self.fall_start = self.riding = self.grapple = None
        self.boost_t = self.grapple_t = 0.
        self.gliding = False

    # ---- inventory
    def add_item(self, item, count):
        ms = max_stack(item)
        for s in self.inv:
            if s and s[0] == item and s[1] < ms:
                take = min(ms - s[1], count)
                s[1] += take
                count -= take
                if not count:
                    return 0
        for i in range(36):
            if self.inv[i] is None:
                take = min(ms, count)
                self.inv[i] = [item, take]
                count -= take
                if not count:
                    return 0
        return count

    def count_free(self, item):
        return any(s is None or (s[0] == item and s[1] < max_stack(item)) for s in self.inv)

    def count_item(self, item):
        items = item if isinstance(item, tuple) else (item,)
        return sum(s[1] for s in self.inv if s and s[0] in items)

    def remove_item(self, item, n):
        items = item if isinstance(item, tuple) else (item,)
        for i in range(35, -1, -1):
            s = self.inv[i]
            if s and s[0] in items and n:
                take = min(n, s[1])
                s[1] -= take
                n -= take
                if not s[1]:
                    self.inv[i] = None

    def held(self):
        s = self.inv[self.sel]
        return s[0] if s else None

    def consume_held(self):
        s = self.inv[self.sel]
        if s:
            s[1] -= 1
            if s[1] <= 0:
                self.inv[self.sel] = None

    def dismount(self):
        m, self.riding = self.riding, None
        if m is not None:
            m.rider = None
            self.pos = [m.pos[0] + 1.1, m.pos[1], m.pos[2] + .3]
        self.vel, self.fall_start = [0., 0., 0.], None

    # ---- damage
    def hurt(self, amt, src=None):
        g = self.game
        if g.mode == 'creative' or self.dead or self.inv_t > 0 or amt <= 0:
            return False
        self.hp -= max(1, int(round(amt)))
        self.inv_t = .5
        if src is not None:
            dx, dy = self.pos[0] - src[0], self.pos[1] - src[1]
            n = math.hypot(dx, dy) or 1
            self.vel[0], self.vel[1], self.vel[2] = dx / n * 7, dy / n * 7, 5.
        g.on_player_hurt()
        if self.hp <= 0:
            self.hp = 0
            g.player_died()
        return True

    # ---- per-frame
    def update(self, dt, active):
        g = self.game
        if not g.world.loaded(self.pos[0], self.pos[1]):
            return
        k = g.key if active else (lambda n: False)
        creative = g.mode == 'creative'
        self.boost_t -= dt
        if self.riding is not None:
            m = self.riding
            if m.gone or m.dead >= 0 or k('shift'):
                self.dismount()
            else:
                self.pos = [m.pos[0], m.pos[1], m.pos[2] + m.d['mount'][2]]
                self.vel, self.on_ground, self.fall_start = list(m.vel), m.on_ground, None
                self.check_fluids()
                self.inv_t -= dt
                return
        if self.grapple is not None:
            gp = self.grapple
            v = [gp[i] - self.pos[i] - (1. if i == 2 else 0.) for i in range(3)]
            dd = math.sqrt(sum(c * c for c in v))
            self.grapple_t += dt
            if dd < 1.4 or self.grapple_t > 2.5 or k('shift'):
                self.grapple = None
            else:
                self.vel = [c / dd * 17. for c in v]
                self.fall_start = None
                self.move(dt)
                self.inv_t -= dt
                return
        if not creative:
            self.flying = False
        fwd, st = k('w') - k('s'), k('d') - k('a')
        hr = math.radians(self.h)
        mx, my = -math.sin(hr) * fwd + math.cos(hr) * st, math.cos(hr) * fwd + math.sin(hr) * st
        n = math.hypot(mx, my)
        if n:
            mx, my = mx / n, my / n
        self.sneak = k('shift') and not self.flying
        self.sprint = k('ctrl') and fwd > 0 and not self.sneak and (creative or self.food > 6)
        was_water = self.in_water
        self.check_fluids()
        if self.in_water and not was_water and self.vel[2] < -4:
            g.sounds.play('splash', None, .6)
            g.particles((self.pos[0], self.pos[1], self.pos[2] + .5), 10, color=(.6, .7, 1.), up=True)
        if self.flying:
            sp = 21. if self.sprint else 10.9
        else:
            sp = 5.6 if self.sprint else (1.3 if self.sneak else 4.3)
        if self.in_water:
            sp *= .55
        if self.in_lava:
            sp *= .35
        acc = 8 if (self.in_water or self.in_lava) else (14 if (self.on_ground or self.flying) else 4)
        f = min(1., acc * dt)
        cur = 2.5 if self.in_water else 1.
        self.vel[0] += (mx * sp + self.flow[0] * cur - self.vel[0]) * f
        self.vel[1] += (my * sp + self.flow[1] * cur - self.vel[1]) * f
        self.jump_cd -= dt
        if self.flying:
            self.vel[2] += ((k('space') - k('shift')) * 9 - self.vel[2]) * min(1., 12 * dt)
        elif self.in_water or self.in_lava:
            self.vel[2] = (self.vel[2] - 9 * dt) * max(0., 1 - 3 * dt)
            if k('space'):
                self.vel[2] = min(self.vel[2] + 30 * dt, 3.6)
                if self.hit_wall:
                    self.vel[2] = 5.5
        else:
            self.vel[2] = max(-60., self.vel[2] - 32 * dt)
            if k('space') and self.on_ground and self.jump_cd <= 0:
                self.vel[2], self.jump_cd = (12.5 if self.boost_t > 0 else 8.6), .1
                self.exhaust += .2 if self.sprint else .05
        if self.in_web:
            self.vel[2] = max(self.vel[2], -2.)
        self.gliding = (self.held() == PARAGLIDER and not self.on_ground and not self.in_water and not self.flying
                        and self.vel[2] < 0 and k('space'))
        if self.gliding:
            self.vel[2] = max(self.vel[2], -2.2)
            gx, gy = -math.sin(hr) * 8.5, math.cos(hr) * 8.5
            self.vel[0] += (gx - self.vel[0]) * min(1., 2. * dt)
            self.vel[1] += (gy - self.vel[1]) * min(1., 2. * dt)
            self.fall_start = None
            g.adv('glide')
        ox, oy = self.pos[0], self.pos[1]
        self.move(dt, edge_guard=self.sneak)
        if self.flying and self.on_ground:
            self.flying = False
        under = self.below() if self.on_ground else AIR
        if under in (SLIME, JELLY) and self.land_vz < -3 and not self.sneak:
            self.vel[2], self.on_ground, self.fall_start = -self.land_vz * .8, False, None
            self.land_vz = 0.
            g.sounds.play('bounce', None, .6)
        moved = math.hypot(self.pos[0] - ox, self.pos[1] - oy)
        # fall damage
        if self.on_ground or self.in_water or self.flying or self.in_lava or self.in_web:
            if self.fall_start is not None and self.on_ground and not self.in_water and under not in (SLIME, JELLY):
                d = self.fall_start - self.pos[2]
                if d > 3.4:
                    self.hurt(int(d - 3))
            self.fall_start = None
        else:
            self.fall_start = self.pos[2] if self.fall_start is None else max(self.fall_start, self.pos[2])
        self.inv_t -= dt
        if creative:
            self.air = 10.
            return
        # survival stats
        diff = g.settings['difficulty']
        self.exhaust += dt * .012 + moved * (.1 if self.sprint else .02)
        if diff == 0:
            self.food = 20
        if self.exhaust >= 4:
            self.exhaust -= 4
            self.food = max(0, self.food - 1)
            g.hud_dirty = True
        head = g.world.get(math.floor(self.pos[0]), math.floor(self.pos[1]), math.floor(self.pos[2] + 1.62))
        if FAMILY[head] == WATER:
            self.air -= dt
            if self.air <= 0:
                self.air, self.drown_t = 0., self.drown_t + dt
                if self.drown_t >= 1:
                    self.drown_t = 0.
                    self.hurt(2)
        else:
            self.air = min(10., self.air + dt * 4)
        if self.in_lava:
            self.hurt(4)
        if self.touching(CACTUS):
            self.hurt(1)
        if under == MAGMA and not self.sneak:
            self.hurt(1)
        if self.pos[2] < -20:
            self.hurt(4)
        self.regen_t += dt
        if self.food >= 18 and self.hp < 20 and self.regen_t >= (1 if diff == 0 else 4):
            self.hp, self.regen_t = self.hp + 1, 0.
            self.exhaust += 1.5
            g.hud_dirty = True
        elif self.food == 0 and self.regen_t >= 4:
            self.regen_t = 0.
            if self.hp > (10, 10, 1, 0)[diff]:
                self.hurt(1)
        if self.regen_t > 4:
            self.regen_t = 4.

# ====================================================================== sound
SR = 22050


def _env(n, k):
    return np.exp(-np.arange(n) / SR * k)


def _noise(d, k=1, decay=10., seed=0):
    x = np.random.RandomState(seed).uniform(-1, 1, int(SR * d))
    if k > 1:
        x = np.convolve(x, np.ones(k) / k, 'same') * math.sqrt(k)
    return x * _env(len(x), decay)


def _tone(f0, f1, d, decay=4., harm=(1,), vib=0.):
    t = np.arange(int(SR * d)) / SR
    ph = 2 * np.pi * np.cumsum(f0 + (f1 - f0) * t / d) / SR
    if vib:
        ph = ph + vib * np.sin(2 * np.pi * 7 * t)
    return sum(np.sin(ph * h) / h for h in harm) * _env(len(t), decay)


def _place(x, at, total):
    out = np.zeros(int(SR * total))
    i = int(SR * at)
    n = min(x.size, out.size - i)
    out[i:i + n] = x[:n]
    return out


SYNTH = {
    'break': lambda: _noise(.18, 4, 22, 1) * .7,
    'place': lambda: _noise(.1, 10, 35, 2) * .8,
    'step': lambda: _noise(.07, 8, 50, 3) * .3,
    'hurt': lambda: _tone(420, 180, .22, 9, (1, 2, 3)) * .6 + _noise(.22, 3, 15, 4) * .15,
    'pop': lambda: _tone(700, 1500, .08, 30) * .5,
    'explode': lambda: _noise(1.4, 30, 3.5, 5) * 1.1,
    'eat': lambda: np.concatenate([_noise(.09, 3, 30, i) for i in range(3)]) * .6,
    'click': lambda: _tone(1100, 900, .04, 60) * .4,
    'oink': lambda: np.concatenate([_tone(160, 120, .14, 12, (1, 2, 3, 4))] * 2) * .5,
    'moo': lambda: _tone(120, 95, .8, 2.5, (1, 2, 3, 4, 5)) * .45,
    'baa': lambda: _tone(330, 300, .55, 4, (1, 2, 3), vib=3) * .4,
    'cluck': lambda: np.concatenate([_tone(700, 500, .06, 30, (1, 2)), np.zeros(1500), _tone(750, 520, .06, 30, (1, 2))]) * .4,
    'groan': lambda: _tone(95, 70, .9, 2.5, (1, 2, 3, 4)) * .45 + _noise(.9, 6, 3, 6) * .15,
    'hiss': lambda: _noise(1.2, 1, 1.2, 7) * .35,
    'fizz': lambda: _noise(.5, 1, 6, 8) * .4,
    'splash': lambda: _noise(.45, 5, 7, 9) * .6,
    'death': lambda: _tone(400, 120, .5, 4, (1, 2, 3)) * .6,
    'twang': lambda: _tone(220, 160, .3, 9, (1, 2, 3)) * .5 + np.pad(_noise(.05, 2, 60, 10), (0, 5513)) * .3,
    'squeak': lambda: _tone(1400, 1800, .12, 14, (1, 2)) * .35,
    'yip': lambda: _tone(900, 600, .1, 18, (1, 2, 3)) * .4,
    'bleat': lambda: _tone(260, 240, .5, 4, (1, 2, 3, 4), vib=4) * .4,
    'squawk': lambda: _tone(600, 450, .25, 8, (1, 2, 3, 4)) * .4,
    'quack': lambda: np.concatenate([_tone(330, 260, .14, 12, (1, 2, 3, 5))] * 2) * .45,
    'rattle': lambda: np.concatenate([_noise(.04, 2, 70, i) for i in range(5)]) * .5,
    'chitter': lambda: np.concatenate([_tone(1800, 1500, .03, 60, (1, 2)) for _ in range(6)]) * .3,
    'bounce': lambda: _tone(200, 500, .2, 10) * .5,
    'chest': lambda: _tone(180, 140, .35, 6, (1, 2, 3)) * .35 + _noise(.35, 8, 8, 11) * .2,
    'sleep': lambda: _tone(440, 440, 1.2, 2, (1, 2)) * .25,
    'chirp': lambda: np.concatenate([_tone(3200 + 300 * i, 4200, .07, 30, (1,)) for i in range(3)]) * .25,
    'croak': lambda: _tone(190, 120, .35, 6, (1, 2, 3)) * (.6 + .4 * np.sin(np.arange(int(SR * .35)) / SR * 2 * np.pi * 28)) * .45,
    'thunder': lambda: _noise(3.5, 80, .9, 21) * .6 + _noise(3.5, 20, 2.5, 22) * .25,
    'rain': lambda: _noise(3., 3, 0., 23) * .22,
    'cave1': lambda: _tone(70, 62, 5., .5, (1, 2, 3), vib=6) * .35 * np.minimum(1, np.arange(int(SR * 5.)) / SR),
    'cave2': lambda: sum(_place(_tone(1300 + 200 * k, 900, .25, 20), k * .55, 2.5) * (.5 ** k) for k in range(4)) * .3,
    'portal': lambda: _tone(180, 520, 2.2, .8, (1, 1.5, 2.01), vib=8) * .35 + _noise(2.2, 40, .8, 31) * .08,
    'neigh': lambda: _tone(700, 420, .7, 3, (1, 2, 3), vib=14) * .35,
    'growl': lambda: _tone(110, 90, .6, 3, (1, 2, 3, 4), vib=10) * .4,
    'blorp': lambda: _tone(160, 420, .18, 12, (1, 2)) * .45,
    'giggle': lambda: np.concatenate([_tone(900 + 100 * i, 1100, .07, 25, (1, 2)) for i in range(5)]) * .3,
    'hmm': lambda: _tone(160, 130, .45, 4, (1, 2, 3, 4), vib=5) * .35,
    'zip': lambda: _tone(400, 1600, .25, 8, (1,)) * .35 + _noise(.25, 2, 12, 32) * .1,
    'cave3': lambda: _noise(5., 150, 0., 24) * np.sin(np.linspace(0, np.pi, int(SR * 5.))) * .1,
}


def _note(f, dur, vel, kind):
    t = np.arange(int(SR * dur)) / SR
    if kind == 'bell':
        env = np.exp(-t * 1.6) * (1 - np.exp(-t * 120))
        x = np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 2) + \
            .25 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 4)
        return x * env * vel
    if kind == 'piano':
        env = np.exp(-t * 2.4) * (1 - np.exp(-t * 90))
        x = (np.sin(2 * np.pi * f * t) + .45 * np.sin(4 * np.pi * f * t) * np.exp(-t * 1.5) +
             .18 * np.sin(6 * np.pi * f * t) * np.exp(-t * 3) + .07 * np.sin(2 * np.pi * 4.01 * f * t) * np.exp(-t * 4))
    else:
        env = np.minimum(1, t / 1.2) * np.minimum(1, (dur - t) / 1.2)
        x = np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 1.004 * t) + .25 * np.sin(4 * np.pi * f * t)
    return x * env * vel


def make_track(seed, dur, style='calm'):
    r = np.random.RandomState(seed)
    key = int(r.choice([55, 57, 60, 62]))
    major = [0, 2, 4, 5, 7, 9, 11]
    silly = style == 'silly'
    penta = [0, 2, 4, 6, 8, 10] if silly else ([0, 2, 4, 7, 9] if r.rand() < .6 else [0, 3, 5, 7, 10])
    beat = 60. / (r.uniform(88, 104) if silly else r.uniform(58, 80))
    prog = [[0, 5, 3, 4], [0, 3, 4, 0], [5, 3, 0, 4], [0, 4, 5, 3]][r.randint(4)]
    buf = np.zeros(int(SR * (dur + 6)), np.float32)
    hz = lambda n: 440. * 2 ** ((n - 69) / 12.)
    t, bar, mel = 0., 0, 2
    while t < dur:
        deg = prog[bar % 4]
        root = key - 12 + major[deg]
        third = major[(deg + 2) % 7] - major[deg] + (12 if (deg + 2) % 7 < deg else 0)
        for n in (root, root + third, root + 7):
            x = _note(hz(n), beat * 4.4, .16, 'pad')
            i = int(t * SR)
            buf[i:i + x.size] += x[:buf.size - i]
        for k in range(8):
            if r.rand() < (.42 if k % 2 == 0 else .18):
                mel = int(np.clip(mel + r.choice([-2, -1, -1, 0, 1, 1, 2]), 0, len(penta) * 2 - 1))
                n = key + 12 * (mel // len(penta)) + penta[mel % len(penta)]
                x = _note(hz(n), 2.6, r.uniform(.22, .34), 'bell' if silly else 'piano')
                i = int((t + k * beat / 2) * SR)
                if i < buf.size:
                    buf[i:i + x.size] += x[:buf.size - i]
        t += beat * 4
        bar += 1
    y = buf.copy()
    for d, g in ((.09, .3), (.23, .22), (.41, .15), (.67, .09)):
        n = int(d * SR)
        y[n:] += buf[:-n] * g
    y *= np.minimum(1, np.linspace(dur + 6, 0, y.size) / 5)
    return y / (np.abs(y).max() + 1e-6) * .6


MUSIC_DIR = os.path.join(DATA_DIR, 'music_v1')
MUSIC_TRACKS = [('menu', 101, 70, 'calm'), ('calm1', 202, 90, 'calm'), ('calm2', 303, 90, 'calm'),
                ('calm3', 404, 80, 'calm'), ('calm4', 505, 85, 'calm'), ('silly1', 606, 80, 'silly'),
                ('silly2', 707, 85, 'silly')]


def write_music():
    os.makedirs(MUSIC_DIR, exist_ok=True)
    for name, seed, dur, style in MUSIC_TRACKS:
        p = os.path.join(MUSIC_DIR, name + '.wav')
        if os.path.exists(p):
            continue
        x = (np.clip(make_track(seed, dur, style), -1, 1) * 32000).astype('<i2')
        with wave.open(p + '.tmp', 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(x.tobytes())
        os.replace(p + '.tmp', p)


class Sounds:
    def __init__(self, game):
        self.game, self.snd, self.i = game, {}, 0
        d = os.path.join(DATA_DIR, 'sounds_v4')
        os.makedirs(d, exist_ok=True)
        for name, fn in SYNTH.items():
            p = os.path.join(d, name + '.wav')
            try:
                if not os.path.exists(p):
                    x = (np.clip(fn(), -1, 1) * 32000).astype('<i2')
                    with wave.open(p, 'wb') as w:
                        w.setnchannels(1)
                        w.setsampwidth(2)
                        w.setframerate(SR)
                        w.writeframes(x.tobytes())
                self.snd[name] = [game.loader.loadSfx(Filename.fromOsSpecific(p)) for _ in range(3)]
            except Exception as e:
                print('sound error', name, e)

    def play(self, name, pos=None, vol=1., cat='volume'):
        lst = self.snd.get(name)
        if not lst:
            return
        v = vol * self.game.settings[cat] / 100.
        pl = self.game.player
        if pos is not None and pl is not None:
            v *= max(0., 1 - math.dist(pos, pl.pos) / 28)
        if v <= .01:
            return
        s = lst[self.i % len(lst)]
        self.i += 1
        s.setVolume(v)
        s.setPlayRate(random.uniform(.9, 1.1))
        s.play()


DEFAULTS = dict(render_dist=6, fov=70, sens=50, volume=70, difficulty=2, bobbing=True, clouds=True,
                show_fps=False, fullscreen=False, brightness=50, fancy_leaves=True, music=50, ambient=70,
                discord=True, discord_app_id='')
DIFF_NAMES = ('Peaceful', 'Easy', 'Normal', 'Hard')
SPLASHES = ['Now in Python!', 'Mobs included!', '100% procedural!', 'Watch out for creepers!', 'Ssssss...',
            'NumPy powered!', 'Also try the real one!', 'Punch trees!', 'Now with dungeons!',
            'Sky islands!', 'Smooth lighting!', 'Torches work now!', 'Mind the spiders!', 'Deer are shy!']
KB = {'w': [KeyboardButton.asciiKey('w')], 'a': [KeyboardButton.asciiKey('a')], 's': [KeyboardButton.asciiKey('s')],
      'd': [KeyboardButton.asciiKey('d')], 'space': [KeyboardButton.space()],
      'shift': [KeyboardButton.shift(), KeyboardButton.lshift(), KeyboardButton.rshift()],
      'ctrl': [KeyboardButton.control(), KeyboardButton.lcontrol(), KeyboardButton.rcontrol()]}


# ====================================================================== shaders
WORLD_VS = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat4 p3d_ModelMatrix;
attribute vec4 p3d_Vertex;
attribute vec4 p3d_Color;
attribute vec2 p3d_MultiTexCoord0;
uniform float time;
uniform float mode;
varying vec2 uv;
varying vec4 col;
varying float dist;
void main() {
    vec4 v = p3d_Vertex;
    vec4 w = p3d_ModelMatrix * v;
    if (p3d_Color.a < 0.75) {
        if (mode > 0.5) {
            v.z += (sin(time * 1.7 + w.x * 0.6 + w.y * 0.4) + sin(time * 2.3 - w.x * 0.35 + w.y * 0.8)) * 0.025 - 0.06;
        } else {
            v.x += sin(time * 1.4 + w.x * 0.5 + w.y * 0.3 + w.z * 0.2) * 0.035;
            v.y += cos(time * 1.1 + w.y * 0.45 + w.z * 0.3) * 0.035;
        }
    }
    gl_Position = p3d_ModelViewProjectionMatrix * v;
    uv = p3d_MultiTexCoord0;
    col = p3d_Color;
    dist = length((p3d_ModelViewMatrix * v).xyz);
}
"""
WORLD_FS = """#version 120
uniform sampler2D p3d_Texture0;
uniform float time;
uniform float mode;
uniform float daylight;
uniform float brightness;
uniform float handlight;
uniform vec3 skytint;
uniform vec3 fogcolor;
uniform vec2 fogrange;
varying vec2 uv;
varying vec4 col;
varying float dist;
void main() {
    vec2 t = uv;
    if (mode > 0.5) {
        float k = mode > 1.5 ? 0.35 : 1.0;
        if (t.x > 500.0) {
            t.x -= 1000.0;
            t.y += time * 0.9 * k;
        } else {
            t += vec2(time * 0.03, time * 0.045) * k;
        }
    }
    vec4 tex = texture2D(p3d_Texture0, t);
    if (tex.a < 0.35) discard;
    float g = 1.0 - brightness * 0.45;
    float sb = col.r / (4.0 - 3.0 * col.r);
    float bb = col.g / (3.0 - 2.0 * col.g);
    vec3 warm = vec3(1.0, 0.82, 0.56);
    vec3 lsky = skytint * pow(sb, g) * daylight;
    vec3 lblk = warm * pow(bb, g);
    float hl = handlight * clamp(1.0 - dist / 14.0, 0.0, 1.0);
    lblk = max(lblk, warm * pow(hl, 1.5));
    vec3 light = min(max(lsky, lblk) + vec3(0.025 + brightness * 0.05), vec3(1.0));
    if (mode > 1.5) light = vec3(1.0);
    vec3 c = tex.rgb * light * col.b;
    float a = (mode > 0.5 && mode < 1.5) ? 0.8 : 1.0;
    float f = clamp((dist - fogrange.x) / (fogrange.y - fogrange.x), 0.0, 1.0);
    gl_FragColor = vec4(mix(c, fogcolor, f), a);
}
"""
SKY_VS = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
attribute vec4 p3d_Vertex;
varying vec3 dir;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    dir = p3d_Vertex.xyz;
}
"""
SKY_FS = """#version 120
uniform vec3 zenith;
uniform vec3 horizon;
uniform vec3 sundir;
uniform vec3 glow;
varying vec3 dir;
void main() {
    vec3 d = normalize(dir);
    float h = d.z;
    vec3 c = mix(horizon, zenith, smoothstep(-0.05, 0.5, h));
    float s = max(dot(d, normalize(sundir)), 0.0);
    c += glow * (pow(s, 5.0) * 0.55 + pow(s, 40.0) * 0.5) * clamp(1.0 - abs(h) * 1.5, 0.2, 1.0);
    c = mix(horizon * 0.85, c, smoothstep(-0.4, 0.0, h));
    gl_FragColor = vec4(c, 1.0);
}
"""
LOGO = {'P': ('####.', '#...#', '#...#', '####.', '#....', '#....', '#....'),
        'Y': ('#...#', '#...#', '.#.#.', '..#..', '..#..', '..#..', '..#..'),
        'C': ('.####', '#....', '#....', '#....', '#....', '#....', '.####'),
        'R': ('####.', '#...#', '#...#', '####.', '#.#..', '#..#.', '#...#'),
        'A': ('.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'),
        'F': ('#####', '#....', '#....', '####.', '#....', '#....', '#....'),
        'T': ('#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..')}

# ====================================================================== UI widgets
def make_card(parent, tex, w, h, pos=(0, 0), sort=0):
    cm = CardMaker('c')
    cm.setFrame(-w / 2, w / 2, -h / 2, h / 2)
    n = parent.attachNewNode(cm.generate(), sort)
    n.setPos(pos[0], 0, pos[1])
    if tex is not None:
        n.setTexture(tex)
    n.setTransparency(TransparencyAttrib.MAlpha)
    return n


class SlotWidget:
    def __init__(self, game, parent, x, y, s, ident):
        self.g = game
        self.f = DirectFrame(parent=parent, frameColor=(.25, .25, .25, 1), frameSize=(-s / 2, s / 2, -s / 2, s / 2),
                             pos=(x, 0, y), state=DGG.NORMAL)
        make_card(self.f, None, s - .014, s - .014).setColor(.55, .55, .55, 1)
        self.f.bind(DGG.B1PRESS, lambda p: game.slot_click(ident, 1))
        self.f.bind(DGG.B3PRESS, lambda p: game.slot_click(ident, 3))
        self.f.bind(DGG.WITHIN, lambda p: game.slot_hover(ident))
        self.f.bind(DGG.WITHOUT, lambda p: game.slot_hover(None))
        self.icon = make_card(self.f, None, s * .72, s * .72)
        self.icon.hide()
        self.txt = OnscreenText(parent=self.f, text='', pos=(s * .42, -s * .4), scale=.04, align=TextNode.ARight,
                                fg=(1, 1, 1, 1), shadow=(0, 0, 0, 1), mayChange=True)

    def set(self, st):
        if st:
            self.icon.setTexture(self.g.icons[st[0]], 1)
            self.icon.show()
            self.txt.setText(str(st[1]) if st[1] > 1 else '')
        else:
            self.icon.hide()
            self.txt.setText('')


def fluid_img(kind):
    r = np.random.RandomState(3 if kind == 'water' else 4)
    cell, edge = _vort(r, 7)
    if kind == 'water':
        t = _pal(_vn(r, 4, oct=2), [(38, 72, 196), (44, 82, 208), (52, 94, 218), (60, 106, 226)], .5)
        t[edge < .55, :3] = (92, 146, 240)
        t[edge < .25, :3] = (140, 186, 250)
    else:
        t = np.zeros((16, 16, 4), np.float32)
        t[..., 3] = 255
        t[..., :3] = np.array([(150, 40, 10), (176, 56, 14), (196, 70, 18)], np.float32)[r.randint(0, 3, 7)][cell]
        t[edge < .9, :3] = (240, 120, 24)
        t[edge < .5, :3] = (255, 196, 70)
        t[edge < .2, :3] = (255, 236, 150)
    return np.clip(t, 0, 255).astype(np.uint8)


def sphere_np(radius, nseg=32, nring=16):
    vs = []
    for i in range(nring):
        t0, t1 = -math.pi / 2 + math.pi * i / nring, -math.pi / 2 + math.pi * (i + 1) / nring
        for j in range(nseg):
            p0, p1 = 2 * math.pi * j / nseg, 2 * math.pi * (j + 1) / nseg
            vs.append([(math.cos(t) * math.cos(p) * radius, math.cos(t) * math.sin(p) * radius, math.sin(t) * radius)
                       for t, p in ((t0, p0), (t0, p1), (t1, p1), (t1, p0))])
    v = np.array(vs, np.float32)
    return geom_np(v, np.ones((len(vs), 4, 4), np.float32), np.zeros((len(vs), 4, 2), np.float32), 'sky')


# ====================================================================== game
class Game(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        gc.set_threshold(50000, 50, 50)
        try:                                    # worker processes: true parallel terrain generation + meshing
            import multiprocessing as mp
            from concurrent.futures import ProcessPoolExecutor
            self.workers = max(1, min(6, (os.cpu_count() or 4) - 2))
            self.pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=mp.get_context('spawn'),
                                            initializer=worker_init)
            for _ in range(self.workers):               # start the workers now, not mid-game
                self.pool.submit(worker_init)
        except Exception as e:
            print('process pool unavailable, using threads:', e)
            self.workers = 2
            self.pool = ThreadPoolExecutor(max_workers=2)
        self.disableMouse()
        self.clock = ClockObject.getGlobalClock()
        self.settings = dict(DEFAULTS)
        try:
            with open(SETTINGS_PATH) as f:
                self.settings.update(json.load(f))
        except Exception:
            pass
        self.mouseWatcherNode.setModifierButtons(ModifierButtons())
        self.buttonThrowers[0].node().setModifierButtons(ModifierButtons())
        atlas, self.tile_imgs = build_atlas()
        self.atlas = np_tex(atlas)
        self.icons, self.gtex = build_icons(self.tile_imgs), gui_textures()
        self.water_tex, self.lava_tex = np_tex(fluid_img('water'), True), np_tex(fluid_img('lava'), True)
        self.world_shader = Shader.make(Shader.SL_GLSL, WORLD_VS, WORLD_FS)
        self.sky_shader = Shader.make(Shader.SL_GLSL, SKY_VS, SKY_FS)
        self.world = self.player = None
        self.mobs, self.items, self.fx = [], [], []
        self.state, self.mode, self.cursor, self.hover = 'menu', 'survival', None, None
        self.time_of_day, self.daylight, self.skytint, self.handlight = .3, 1., (1., 1., 1.), 0.
        self.tick_acc = self.spawn_t = self.save_t = self.notice_t = self.name_t = self.grow_t = 0.
        self.mouse_locked, self.mref, self.mouse_skip = False, None, 0
        self.target = self.target_prev = self.target_mob = None
        self.mine_pos, self.mine_prog, self.break_cd, self.use_cd, self.attack_cd = None, 0., 0., 0., 0.
        self.swing, self.shake, self.flash, self.last_space, self.hand_item = 0., 0., 0., 0., -1
        self.hud_dirty, self.hud_hidden, self.debug, self.cre_page, self.craft_page = True, False, False, 0, 0
        self.had_focus, self.fade, self.fade_to, self.sleep_t, self.chest_pos = False, 1., 0., -1., None
        self.near_table, self.new_mode, self.settings_back, self.menu_t, self.step_phase = False, 'survival', 'menu', 0., 0.
        self.menu_center, self.ext_cache = (0., 0., 60.), {}
        self.weather, self.rain, self.weather_t, self.flash_sky, self.precip_t = 'clear', 0., random.uniform(200, 420), 0., 0.
        self.precip_type, self.bolt, self.bolt_t, self.amb, self.cave_t, self.mob_snd_t = None, None, 0., [], 20., 0.
        self.music, self.music_cur, self.music_t, self.music_ready, self.music_menu = {}, None, 3., False, False
        self.cre_tab, self.cre_query, self.cre_list, self.save_thread = 'All', '', list(CREATIVE_ITEMS), None
        self.net, self.discord_t = None, 0.
        self.dim, self.worlds, self.dim_saved, self.arrival = 'over', {}, {}, None
        self.portal_t, self.portal_lock, self.music_dim, self.rope = 0., False, 'over', None
        self.discord = Discord(self)
        threading.Thread(target=self.gen_music, daemon=True).start()
        self.ent_root = self.render.attachNewNode('entities')
        self.ent_root.setTexture(self.atlas)
        self.sounds = Sounds(self)
        self.rain_snd = self.sounds.snd.get('rain', [None])[0]
        if self.rain_snd:
            self.rain_snd.setLoop(True)
        self.camLens.setNearFar(.05, 1000)
        self.fog = Fog('fog')
        self.render.setFog(self.fog)
        self.build_sky()
        self.build_world_overlays()
        self.build_logo()
        self.build_ui()
        self.build_extras()
        self.build_help()
        self.build_bossbar()
        self.bind_keys()
        self.apply_leaves()
        self.apply_settings()
        self.exitFunc = self.on_exit
        self.taskMgr.add(self.update, 'update')
        self.start_menu()

    # ---------------------------------------------------------------- scene setup
    def submit(self, fn, *args):
        try:
            return self.pool.submit(fn, *args)
        except Exception as e:
            if isinstance(self.pool, ThreadPoolExecutor):
                raise
            print('process pool failed, falling back to threads:', e)
            self.pool, self.workers = ThreadPoolExecutor(max_workers=2), 2
            return self.pool.submit(fn, *args)

    def setup_world_shader(self, root):
        root.setShader(self.world_shader)
        for k, v in (('time', 0.), ('mode', 0.), ('daylight', 1.), ('brightness', .5), ('handlight', 0.),
                     ('skytint', Vec3(1, 1, 1)), ('fogcolor', Vec3(.6, .75, 1)), ('fogrange', Vec2(60., 100.))):
            root.setShaderInput(k, v)

    def build_sky(self):
        self.sky = sphere_np(600)
        self.sky.reparentTo(self.render)
        self.sky.setShader(self.sky_shader)
        for k, v in (('zenith', Vec3(.3, .5, .9)), ('horizon', Vec3(.7, .8, 1)), ('sundir', Vec3(0, 0, 1)),
                     ('glow', Vec3(0, 0, 0))):
            self.sky.setShaderInput(k, v)
        self.sky.setTwoSided(True)
        self.stars = self.render.attachNewNode('stars')
        r = np.random.RandomState(11)
        d = r.normal(size=(900, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        vd = GeomVertexData('stars', FMT, Geom.UHStatic)
        vd.uncleanSetNumRows(900)
        data = np.zeros((900, 9), np.float32)
        data[:, :3] = d * 550
        data[:, 3:6] = r.uniform(.6, 1., (900, 1))
        data[:, 6] = 1.
        vd.modifyArrayHandle(0).copyDataFrom(data)
        pts = GeomPoints(Geom.UHStatic)
        pts.addConsecutiveVertices(0, 900)
        gm = Geom(vd)
        gm.addPrimitive(pts)
        gn = GeomNode('stars')
        gn.addGeom(gm)
        self.stars_geom = self.stars.attachNewNode(gn)
        self.stars_geom.setRenderModeThickness(2)
        self.sun = make_card(self.render, self.gtex['sun'], 40, 40)
        self.moon = make_card(self.render, self.gtex['moon'], 30, 30)
        n = Noise(99)
        gy, gx = np.mgrid[0:64, 0:64].astype(float)
        c = n.n2(gx / 8., gy / 8.) + .5 * n.n2(gx / 4., gy / 4.)
        img = np.zeros((64, 64, 4), np.uint8)
        img[c > .18] = (255, 255, 255, 215)
        cm = CardMaker('clouds')
        cm.setFrame(-600, 600, -600, 600)
        cm.setUvRange((0, 0), (1200 / 768., 1200 / 768.))
        self.clouds = self.render.attachNewNode(cm.generate())
        self.clouds.setP(-90)
        self.clouds.setTexture(np_tex(img, repeat=True))
        self.clouds.setTwoSided(True)
        self.cloud_fog = Fog('cloudfog')
        self.cloud_fog.setLinearRange(150, 600)
        self.clouds.setFog(self.cloud_fog)
        for i, n_ in enumerate((self.sky, self.stars, self.sun, self.moon, self.clouds)):
            n_.setBin('background', i)
            n_.setDepthWrite(False)
            n_.setDepthTest(False)
            n_.setLightOff()
            n_.setTextureOff(1) if n_ in (self.sky, self.stars) else None
            if n_ is not self.clouds:
                n_.setFogOff()
            n_.setTransparency(TransparencyAttrib.MAlpha)
        for n_ in (self.sun, self.moon):
            n_.setBillboardPointEye()
        ls = LineSegs()
        ls.setThickness(2)
        ls.setColor(0, 0, 0, .75)
        e, f = -.003, 1.003
        c8 = [(x, y, z) for z in (e, f) for x, y in ((e, e), (f, e), (f, f), (e, f))]
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)):
            ls.moveTo(*c8[a])
            ls.drawTo(*c8[b])
        self.outline = self.render.attachNewNode(ls.create())
        self.outline.setTransparency(TransparencyAttrib.MAlpha)
        self.outline.hide()
        self.crack = cube_np((0, 0, 0), 1.006, (-.003, -.003, -.003))
        self.crack.reparentTo(self.render)
        self.crack.setTexture(self.atlas)
        self.crack.setTransparency(TransparencyAttrib.MAlpha)
        self.crack.setDepthOffset(1)
        self.crack.setColorScale(1, 1, 1, .9)
        self.crack.hide()
        self.precip = self.render.attachNewNode('precip')
        self.precip.setTransparency(TransparencyAttrib.MAlpha)
        self.precip.setDepthWrite(False)
        self.precip.setTwoSided(True)
        self.precip.setBin('transparent', 10)
        self.rain_tex = np_tex(self.tile_imgs['rain'], True)
        self.snow_tex = np_tex(self.tile_imgs['snowflake'], True)
        self.amb_root = self.render.attachNewNode('ambient')
        self.hand = self.camera.attachNewNode('hand')
        self.hand.setBin('fixed', 100)
        self.hand.setDepthTest(False)
        self.hand.setDepthWrite(False)
        self.hand.setFogOff()

    def build_world_overlays(self):
        cm = CardMaker('ov')
        cm.setFrame(-1, 1, -1, 1)
        self.ov_water = self.render2d.attachNewNode(cm.generate(), -10)
        self.ov_hurt = self.render2d.attachNewNode(cm.generate(), -9)
        self.ov_fade = self.render2d.attachNewNode(cm.generate(), 40)
        for o in (self.ov_water, self.ov_hurt, self.ov_fade):
            o.setTransparency(TransparencyAttrib.MAlpha)
            o.hide()
        self.ov_hurt.setColor(.8, 0, 0, .35)
        self.ov_fade.setColor(0, 0, 0, 1)
        yy, xx = np.mgrid[0:64, 0:64].astype(np.float32)
        rr = np.hypot(xx - 31.5, yy - 31.5) / 45.
        v = np.zeros((64, 64, 4), np.uint8)
        v[..., 3] = (np.clip((rr - .45) / .55, 0, 1) ** 1.6 * 200).astype(np.uint8)
        self.vignette = self.render2d.attachNewNode(cm.generate(), -11)
        self.vignette.setTexture(np_tex(v))
        self.vignette.setTransparency(TransparencyAttrib.MAlpha)
        self.vignette.hide()

    def build_logo(self):
        """3D voxel logo rendered in its own display region on top of the menu scene."""
        vox = {}
        x0 = 0
        for ch in 'PYCRAFT':
            rows = LOGO[ch]
            for r, row in enumerate(rows):
                for c, k in enumerate(row):
                    if k == '#':
                        for y in (0, 1):
                            vox[(x0 + c, y, 6 - r)] = 1
            x0 += len(rows[0]) + 1
        vs, cs, us = [], [], []
        for (x, y, z) in vox:
            b = GRASS if (x, y, z + 1) not in vox else COBBLE
            for (dx, dy, dz), corn, shade, fk in FACES:
                if (x + dx, y + dy, z + dz) in vox:
                    continue
                v, c, u = quads(np.array([[x, y, z]], np.float32), corn, [TEXIDX[b, fk]], [shade])
                vs.append(v), cs.append(c), us.append(u)
        logo = geom_np(np.concatenate(vs), np.concatenate(cs), np.concatenate(us), 'logo')
        self.logo_root = NodePath('logo_scene')
        self.logo = self.logo_root.attachNewNode('logo')
        logo.reparentTo(self.logo)
        logo.setPos(-(x0 - 1) / 2., -1., -3.5)
        logo.setTexture(self.atlas)
        self.logo.setPos(0, 0, 10.5)
        lens = PerspectiveLens()
        lens.setFov(32)
        self.logo_lens = lens
        cam = Camera('logo_cam', lens)
        self.logo_cam = self.logo_root.attachNewNode(cam)
        self.logo_cam.setPos(0, -110, 0)
        self.logo_dr = self.win.makeDisplayRegion()
        self.logo_dr.setSort(5)
        self.logo_dr.setClearColorActive(False)
        self.logo_dr.setClearDepthActive(True)
        self.logo_dr.setCamera(self.logo_cam)
        self.logo_dr.setActive(False)

    def button(self, parent, text, pos, cmd, w=.8, h=.11, scale=.05):
        def run():
            self.sounds.play('click')
            cmd()
        return DirectButton(parent=parent, text=text, text_scale=scale, text_fg=(1, 1, 1, 1),
                            text_shadow=(.15, .15, .15, 1), text_pos=(0, -scale * .33),
                            frameSize=(-w / 2, w / 2, -h / 2, h / 2), relief=DGG.FLAT,
                            frameColor=((.42, .42, .45, .95), (.3, .3, .55, 1), (.5, .52, .78, 1), (.25, .25, .25, .7)),
                            pos=(pos[0], 0, pos[1]), command=run, clickSound=None, rolloverSound=None)

    def text(self, parent, text, pos, scale=.05, fg=(1, 1, 1, 1), align=TextNode.ACenter, **kw):
        return OnscreenText(parent=parent, text=text, pos=pos, scale=scale, fg=fg, align=align,
                            shadow=(0, 0, 0, .8), mayChange=True, **kw)

    def build_ui(self):
        a = self.aspect2d
        # ---- main menu
        self.ui_menu = DirectFrame(parent=a, frameColor=(0, 0, 0, 0))
        self.splash = self.text(self.ui_menu, random.choice(SPLASHES), (.62, .43), .055, (1, 1, 0, 1), roll=-15)
        self.btn_continue = self.button(self.ui_menu, 'Continue World', (0, .14), self.continue_world, h=.095)
        self.button(self.ui_menu, 'New World', (0, .035), lambda: self.show('new'), h=.095)
        self.button(self.ui_menu, 'Multiplayer', (0, -.07), lambda: self.show('mp'), h=.095)
        self.button(self.ui_menu, 'Help & Guides', (0, -.175), lambda: self.show_help(0), h=.095)
        self.button(self.ui_menu, 'Settings', (0, -.28), lambda: self.open_settings('menu'), h=.095)
        self.button(self.ui_menu, 'Quit Game', (0, -.385), self.userExit, h=.095)
        self.text(self.ui_menu, 'PyCraft 2.0 - Python + Panda3D', (0, -.82), .035, (.85, .85, .85, 1))
        self.text(self.ui_menu, 'WASD move | Space jump | Ctrl sprint | Shift sneak | E inventory | '
                  'G creative/survival | F fly | Q drop | F4 weather | Esc pause', (0, -.9), .035, (.85, .85, .85, 1))
        # ---- new world
        self.ui_new = DirectFrame(parent=a, frameColor=(0, 0, 0, .6), frameSize=(-1, 1, -.7, .7))
        self.text(self.ui_new, 'Create New World', (0, .55), .08)
        self.text(self.ui_new, 'Seed (blank = random)', (0, .37), .045, (.8, .8, .8, 1))
        self.seed_entry = DirectEntry(parent=self.ui_new, scale=.05, width=16, pos=(-.4, 0, .25), numLines=1,
                                      frameColor=(0, 0, 0, .85), text_fg=(1, 1, 1, 1), initialText='')
        self.btn_mode = self.button(self.ui_new, 'Game Mode: Survival', (0, .07), self.cycle_new_mode)
        self.new_warn = self.text(self.ui_new, '', (0, -.08), .04, (1, .65, .4, 1))
        self.button(self.ui_new, 'Create World', (0, -.25), self.create_world)
        self.button(self.ui_new, 'Back', (0, -.4), lambda: self.show('menu'))
        # ---- settings
        self.ui_settings = DirectFrame(parent=a, frameColor=(0, 0, 0, .7), frameSize=(-1.15, 1.15, -.88, .88))
        self.text(self.ui_settings, 'Settings', (0, .73), .08)
        self.sliders, self.slider_lbl, self.toggles = {}, {}, {}
        for i, (k, label, rng) in enumerate((('render_dist', 'Render Distance', (2, 12)), ('fov', 'FOV', (50, 110)),
                                              ('sens', 'Mouse Sensitivity', (1, 100)), ('volume', 'Sound Volume', (0, 100)),
                                              ('music', 'Music', (0, 100)), ('ambient', 'Ambience & Weather', (0, 100)),
                                              ('brightness', 'Brightness', (0, 100)))):
            y = .52 - i * .17
            self.slider_lbl[k] = (label, self.text(self.ui_settings, '', (-.55, y + .055), .043))
            self.sliders[k] = DirectSlider(parent=self.ui_settings, range=rng, value=self.settings[k], pageSize=1,
                                           pos=(-.55, 0, y), scale=.42, command=self.on_slider, extraArgs=[k],
                                           frameColor=(.3, .3, .3, 1), thumb_frameColor=(.7, .7, .75, 1),
                                           thumb_relief=DGG.FLAT, relief=DGG.FLAT)
        for i, k in enumerate(('difficulty', 'fancy_leaves', 'bobbing', 'clouds', 'show_fps', 'fullscreen', 'discord')):
            self.toggles[k] = self.button(self.ui_settings, '', (.55, .52 - i * .14), lambda k=k: self.on_toggle(k), w=.9)
        self.button(self.ui_settings, 'Done', (0, -.74), self.close_settings)
        # ---- pause
        self.ui_pause = DirectFrame(parent=a, frameColor=(0, 0, 0, .5), frameSize=(-3, 3, -1.2, 1.2))
        self.text(self.ui_pause, 'Game Paused', (0, .45), .08)
        self.button(self.ui_pause, 'Back to Game', (0, .22), self.resume)
        self.btn_pmode = self.button(self.ui_pause, '', (0, .08), self.toggle_mode)
        self.button(self.ui_pause, 'Settings', (0, -.06), lambda: self.open_settings('pause'))
        self.button(self.ui_pause, 'Save & Quit to Title', (0, -.2), self.save_and_quit)
        self.btn_lan = self.button(self.ui_pause, 'Open to LAN / Host', (0, -.34), self.open_to_lan)
        self.button(self.ui_pause, 'Advancements', (0, -.48), self.show_advancements)
        self.button(self.ui_pause, 'Help & Guides', (0, -.62), lambda: self.show_help(0))
        # ---- death
        self.ui_dead = DirectFrame(parent=a, frameColor=(.5, 0, 0, .45), frameSize=(-3, 3, -1.2, 1.2))
        self.text(self.ui_dead, 'You Died!', (0, .3), .12)
        self.dead_txt = self.text(self.ui_dead, '', (0, .15), .045)
        self.button(self.ui_dead, 'Respawn', (0, -.05), self.respawn)
        self.button(self.ui_dead, 'Title Screen', (0, -.2), self.save_and_quit)
        # ---- loading
        self.ui_load = DirectFrame(parent=a, frameColor=(.1, .08, .06, 1), frameSize=(-3, 3, -1.2, 1.2))
        self.load_txt = self.text(self.ui_load, 'Generating world...', (0, .1), .07)
        DirectFrame(parent=self.ui_load, frameColor=(.2, .2, .2, 1), frameSize=(-.6, .6, -.025, .025), pos=(0, 0, -.05))
        self.load_bar = DirectFrame(parent=self.ui_load, frameColor=(.3, .85, .3, 1), frameSize=(-.6, -.6, -.025, .025), pos=(0, 0, -.05))
        self.build_hud()
        self.build_inventory_ui()
        for u in (self.ui_menu, self.ui_new, self.ui_settings, self.ui_pause, self.ui_dead, self.ui_load):
            u.hide()

    def build_hud(self):
        self.hud = self.aspect2d.attachNewNode('hud')
        self.hud_b = self.a2dBottomCenter.attachNewNode('hudb')
        self.crosshair = self.text(self.hud, '+', (0, -.022), .08, (1, 1, 1, .85))
        self.hot_bg, self.hot_icons, self.hot_txt = [], [], []
        for i in range(9):
            x = (i - 4) * .115
            self.hot_bg.append(make_card(self.hud_b, self.gtex['slot'], .115, .115, (x, .075)))
            ic = make_card(self.hud_b, None, .08, .08, (x, .075))
            ic.hide()
            self.hot_icons.append(ic)
            self.hot_txt.append(self.text(self.hud_b, '', (x + .05, .03), .04, align=TextNode.ARight))
        self.hot_sel = make_card(self.hud_b, self.gtex['sel'], .128, .128, (0, .075))
        self.hearts = [make_card(self.hud_b, self.gtex['heart'], .05, .05, (-.495 + i * .05, .165)) for i in range(10)]
        self.foods = [make_card(self.hud_b, self.gtex['food'], .05, .05, (.495 - i * .05, .165)) for i in range(10)]
        self.bubbles = [make_card(self.hud_b, self.gtex['bubble'], .045, .045, (.495 - i * .05, .22)) for i in range(10)]
        self.item_name = self.text(self.hud_b, '', (0, .26), .045)
        self.notice = self.text(self.hud, '', (0, .35), .055, (1, 1, .6, 1))
        self.debug_txt = self.text(self.a2dTopLeft, '', (.03, -.06), .04, align=TextNode.ALeft)
        self.hud.hide()
        self.hud_b.hide()

    def build_inventory_ui(self):
        a = self.aspect2d
        S = .145
        # survival inventory + crafting
        self.ui_inv = DirectFrame(parent=a, frameColor=(0, 0, 0, .45), frameSize=(-3, 3, -1.2, 1.2), state=DGG.NORMAL)
        self.ui_inv.bind(DGG.B1PRESS, lambda p: self.drop_cursor())
        panel = DirectFrame(parent=self.ui_inv, frameColor=(.78, .78, .78, 1), frameSize=(-.72, .72, -.62, .5),
                            pos=(-.42, 0, 0), state=DGG.NORMAL)
        self.button(self.ui_inv, 'Switch to Creative  [G]', (-.42, .6), self.toggle_mode, w=.7, h=.09, scale=.04)
        self.text(panel, 'Inventory', (-.66, .42), .05, (.2, .2, .2, 1), TextNode.ALeft)
        self.inv_slots = []
        for i in range(36):
            col, y = (i, -.5) if i < 9 else ((i - 9) % 9, .27 - ((i - 9) // 9) * S)
            self.inv_slots.append(SlotWidget(self, panel, -.58 + col * S, y, .13, ('inv', i)))
        self.inv_stats = self.text(panel, '', (-.66, -.2), .038, (.15, .15, .15, 1), TextNode.ALeft)
        cp = DirectFrame(parent=self.ui_inv, frameColor=(.78, .78, .78, 1), frameSize=(-.55, .55, -.62, .5),
                         pos=(.88, 0, 0), state=DGG.NORMAL)
        self.text(cp, 'Crafting', (-.49, .42), .05, (.2, .2, .2, 1), TextNode.ALeft)
        self.craft_note = self.text(cp, '', (.49, .43), .03, (.4, .2, .1, 1), TextNode.ARight)
        self.craft_rows = []
        for k in range(9):
            b = DirectButton(parent=cp, frameSize=(-.5, .5, -.045, .045), pos=(0, 0, .33 - k * .1), relief=DGG.FLAT,
                             frameColor=((.62, .62, .62, 1), (.45, .45, .7, 1), (.7, .7, .85, 1), (.62, .62, .62, .5)),
                             command=self.craft_click, extraArgs=[k], clickSound=None, rolloverSound=None)
            ic = make_card(b, None, .075, .075, (-.44, 0))
            t1 = OnscreenText(parent=b, text='', pos=(-.39, .005), scale=.034, align=TextNode.ALeft, mayChange=True)
            t2 = OnscreenText(parent=b, text='', pos=(-.39, -.03), scale=.026, align=TextNode.ALeft, mayChange=True)
            self.craft_rows.append((b, ic, t1, t2))
        self.button(cp, '<', (-.4, -.57), lambda: self.craft_flip(-1), w=.12, h=.07)
        self.button(cp, '>', (.4, -.57), lambda: self.craft_flip(1), w=.12, h=.07)
        self.craft_pg = self.text(cp, '', (0, -.585), .04, (.2, .2, .2, 1))
        # creative inventory: tabs + search + big grid
        self.ui_cre = DirectFrame(parent=a, frameColor=(0, 0, 0, .5), frameSize=(-3, 3, -1.2, 1.2), state=DGG.NORMAL)
        self.ui_cre.bind(DGG.B1PRESS, lambda p: self.drop_cursor())
        cp = DirectFrame(parent=self.ui_cre, frameColor=(.76, .76, .78, 1), frameSize=(-1.02, 1.02, -.88, .8),
                         state=DGG.NORMAL)
        DirectFrame(parent=cp, frameColor=(.62, .62, .66, 1), frameSize=(-.98, .98, -.43, .5))
        self.button(self.ui_cre, 'Switch to Survival  [G]', (0, .88), self.toggle_mode, w=.7, h=.09, scale=.04)
        self.text(cp, 'Creative Inventory', (-.96, .71), .055, (.15, .15, .15, 1), TextNode.ALeft)
        self.text(cp, 'Search:', (.12, .705), .042, (.2, .2, .2, 1), TextNode.ARight)
        self.cre_search = DirectEntry(parent=cp, scale=.042, width=19, pos=(.15, 0, .7), numLines=1, focus=0,
                                      frameColor=(.12, .12, .14, 1), text_fg=(1, 1, 1, 1), initialText='')
        self.cre_tabs = {}
        for i, t in enumerate(CRE_TABS):
            self.cre_tabs[t] = self.button(cp, t, (-.86 + i * .246, .58), lambda t=t: self.set_cre_tab(t),
                                           w=.235, h=.085, scale=.036)
        S = .15
        self.cre_slots = [SlotWidget(self, cp, -.675 + (k % 10) * S, .42 - (k // 10) * S, .138, ('cre', k))
                          for k in range(60)]
        self.cre_info = self.text(cp, '', (-.96, -.5), .036, (.2, .2, .2, 1), TextNode.ALeft)
        self.button(cp, '<', (.6, -.49), lambda: self.cre_flip(-1), w=.1, h=.07)
        self.button(cp, '>', (.92, -.49), lambda: self.cre_flip(1), w=.1, h=.07)
        self.cre_pg = self.text(cp, '', (.76, -.505), .04, (.2, .2, .2, 1))
        self.text(cp, 'Hotbar', (-.96, -.62), .04, (.2, .2, .2, 1), TextNode.ALeft)
        self.cre_hot = [SlotWidget(self, cp, -.6 + i * S, -.74, .138, ('inv', i)) for i in range(9)]
        self.text(cp, 'Left-click: full stack   Right-click: one   Click the grid while holding to delete   Wheel: page',
                  (0, -.84), .03, (.3, .3, .3, 1))
        # chest
        self.ui_chest = DirectFrame(parent=a, frameColor=(0, 0, 0, .45), frameSize=(-3, 3, -1.2, 1.2), state=DGG.NORMAL)
        self.ui_chest.bind(DGG.B1PRESS, lambda p: self.drop_cursor())
        cp = DirectFrame(parent=self.ui_chest, frameColor=(.78, .78, .78, 1), frameSize=(-.72, .72, -.8, .78),
                         state=DGG.NORMAL)
        self.text(cp, 'Chest', (-.66, .69), .05, (.2, .2, .2, 1), TextNode.ALeft)
        self.text(cp, 'Shift+click moves a whole stack', (.66, .7), .03, (.3, .3, .3, 1), TextNode.ARight)
        self.chest_slots = [SlotWidget(self, cp, -.58 + (k % 9) * S, .56 - (k // 9) * S, .13, ('chest', k)) for k in range(27)]
        self.text(cp, 'Inventory', (-.66, .07), .045, (.2, .2, .2, 1), TextNode.ALeft)
        self.chest_inv = []
        for i in range(36):
            col, y = (i, -.7) if i < 9 else ((i - 9) % 9, -.06 - ((i - 9) // 9) * S)
            self.chest_inv.append(SlotWidget(self, cp, -.58 + col * S, y, .13, ('inv', i)))
        self.cursor_icon = make_card(a, None, .1, .1, sort=100)
        self.cursor_icon.setBin('gui-popup', 60)
        self.cursor_txt = self.text(self.cursor_icon, '', (.05, -.05), .04, align=TextNode.ARight)
        self.tooltip = self.text(a, '', (0, 0), .04, (1, 1, 1, 1), TextNode.ALeft)
        self.tooltip.setBin('gui-popup', 70)
        for u in (self.ui_inv, self.ui_cre, self.ui_chest, self.cursor_icon, self.tooltip):
            u.hide()

    def bind_keys(self):
        for item in (('escape', self.on_escape), ('e', self.toggle_inventory), ('mouse1', self.on_lclick),
                       ('mouse3', self.on_rclick), ('mouse2', self.pick_block), ('g', self.toggle_mode),
                       ('f', self.toggle_fly), ('space', self.on_space), ('q', self.drop_held), ('f1', self.toggle_hud),
                       ('f2', self.take_screenshot), ('f3', self.toggle_debug), ('f11', self.toggle_fullscreen),
                       ('f4', self.cycle_weather), ('t', self.open_chat), ('slash', self.open_chat, ['/']),
                       ('m', self.toggle_minimap)):
            self.accept(item[0], item[1], *item[2:])
        self.accept('wheel_up', self.scroll, [-1])
        self.accept('wheel_down', self.scroll, [1])
        for i in range(9):
            self.accept(str(i + 1), self.select_slot, [i])

    def key(self, k):
        return any(self.mouseWatcherNode.isButtonDown(b) for b in KB[k])

    def apply_leaves(self):
        fancy = bool(self.settings['fancy_leaves'])
        for b in LEAF_IDS:
            TEXIDX[b] = (TEXIDX_FANCY if fancy else TEXIDX_FAST)[b]
            HIDES[b] = not fancy
        if self.world:
            for ch in self.world.chunks.values():
                ch.dirty = max(ch.dirty, 1)

    # ---------------------------------------------------------------- screens / states
    def show(self, name):
        for n, u in (('menu', self.ui_menu), ('new', self.ui_new), ('settings', self.ui_settings), ('pause', self.ui_pause),
                     ('dead', self.ui_dead), ('load', self.ui_load), ('inv', self.ui_inv), ('cre', self.ui_cre),
                     ('chest', self.ui_chest), ('adv', self.ui_adv), ('mp', self.ui_mp), ('help', self.ui_help)):
            u.show() if n == name else u.hide()
        if name == 'new':
            self.new_warn.setText('Warning: this replaces your saved world!' if os.path.exists(SAVE_PATH) else '')
        if name == 'menu':
            self.btn_continue['state'] = DGG.NORMAL if os.path.exists(SAVE_PATH) else DGG.DISABLED
        if name == 'pause':
            self.btn_pmode['text'] = 'Game Mode: ' + self.mode.capitalize()
        if name != 'cre':
            self.cre_search.guiItem.setFocus(False)
        in_game = name in (None, 'inv', 'cre', 'chest') and self.state not in ('menu', 'loading')
        for n_ in (self.hud, self.hud_b):
            n_.show() if in_game and not self.hud_hidden else n_.hide()
        menu = self.state == 'menu' and name in ('menu', 'new', 'settings')
        self.logo_dr.setActive(menu and name == 'menu')
        self.vignette.show() if menu else self.vignette.hide()

    def set_mouse_lock(self, lock):
        wp = WindowProperties()
        wp.setCursorHidden(lock)
        if lock:
            wp.setMouseMode(WindowProperties.M_relative if sys.platform == 'darwin' else WindowProperties.M_confined)
        else:
            wp.setMouseMode(WindowProperties.M_absolute)
        self.win.requestProperties(wp)
        self.mouse_locked, self.mouse_skip, self.mref = lock, 2, None

    def clear_world(self):
        if getattr(self, 'bobber', None) is not None:
            self.bobber.node.removeNode()
            self.bobber = None
        if getattr(self, 'bossbar', None) is not None:
            self.boss = None
            self.bossbar.hide()
        for lst in (self.mobs, self.items, self.fx):
            for e in lst:
                e.node.removeNode()
            lst.clear()
        for wd in set(list(self.worlds.values()) + ([self.world] if self.world else [])):
            wd.destroy()
        self.worlds, self.dim_saved, self.dim, self.arrival = {}, {}, 'over', None
        if self.rope is not None:
            self.rope.removeNode()
            self.rope = None
        self.world = self.player = None
        self.hand.getChildren().detach()
        self.hand_item, self.chest_pos, self.sleep_t = -1, None, -1.
        for a in self.amb:
            a[0].removeNode()
        self.amb = []
        self.precip.getChildren().detach()
        if self.bolt is not None:
            self.bolt.removeNode()
            self.bolt = None
        if self.rain_snd:
            self.rain_snd.stop()
        self.rain, self.weather, self.precip_type, self.flash_sky = 0., 'clear', None, 0.
        self.outline.hide()
        self.crack.hide()

    def start_menu(self):
        self.clear_world()
        self.state, self.cursor = 'menu', None
        self.world = World(self, random.randint(0, 10 ** 9))
        g = self.world.gen
        sx, sy = g.find_spawn()
        best = g.structure_near(sx, sy, ('cabin', 'tower', 'ruins', 'pyramid', 'igloo', 'well'), 2)
        if best:
            cx, cy, cz = best[2]
        else:
            b, h = g.biome_at(sx, sy)
            cx, cy, cz = sx, sy, max(SEA, h) + 1
        self.menu_center, self.time_of_day, self.menu_t = (cx, cy, cz), .36, 0.
        self.splash.setText(random.choice(SPLASHES))
        self.set_mouse_lock(False)
        self.ov_water.hide()
        self.fade, self.fade_to = 1., 0.
        self.show('menu')

    def cycle_new_mode(self):
        self.new_mode = 'creative' if self.new_mode == 'survival' else 'survival'
        self.btn_mode['text'] = 'Game Mode: ' + self.new_mode.capitalize()

    def create_world(self):
        s = self.seed_entry.get().strip()
        seed = (int(s) if s.lstrip('-').isdigit() else zlib.crc32(s.encode())) if s else random.randint(0, 2 ** 31)
        self.start_world(seed, self.new_mode)

    def continue_world(self):
        try:
            with open(SAVE_PATH, 'rb') as f:
                data = pickle.load(f)
            self.start_world(data['seed'], data['mode'], data)
        except Exception as e:
            print('load failed:', e)
            self.btn_continue['state'] = DGG.DISABLED

    def start_world(self, seed, mode, data=None):
        self.clear_world()
        dims = dict(data.get('dims') or {}) if data else {}
        if data and not dims:
            dims = {'over': (data.get('chunks') or {}, data.get('chests') or {})}
        self.dim = data.get('dim', 'over') if data else 'over'
        cur = dims.pop(self.dim, ({}, {}))
        self.dim_saved = dims
        self.world = World(self, seed, cur[0], cur[1], dim=self.dim)
        self.load_txt.setText('Generating world...')
        self.pending_mounts = list(data.get('mounts', [])) if data else []
        self.player = p = Player(self)
        self.mode, self.cursor = mode, None
        self.adv_done = set(data.get('adv', [])) if data else set()
        if self.net is None:
            self.btn_lan['text'] = 'Open to LAN / Host'
        if data and data.get('player'):
            pd = data['player']
            p.pos, p.h, p.p, p.hp, p.food = list(pd['pos']), pd['h'], pd['p'], pd['hp'], pd['food']
            p.inv, p.sel, p.flying, self.spawn = pd['inv'], pd['sel'], pd['flying'], tuple(pd['spawn'])
            self.time_of_day, self.weather = data['time'], data.get('weather', 'clear')
        else:
            sx, sy = (data['spawn'][0], data['spawn'][1]) if data and data.get('spawn') else self.world.gen.find_spawn()
            self.spawn, self.time_of_day = (sx, sy, None), (data['time'] if data else .02)
            if data:
                self.weather = data.get('weather', 'clear')
            p.pos = [sx, sy, H]
            if mode == 'survival':
                p.add_item(tool_id(0, 0), 1)
                p.add_item(APPLE, 3)
                p.add_item(TORCH, 8)
        self.state = 'loading'
        self.load_bar['frameSize'] = (-.6, -.6, -.025, .025)
        self.show('load')

    def loading_step(self):
        p = self.player
        done, tot = self.world.ready(p.pos[0], p.pos[1], min(3, self.settings['render_dist']))
        self.load_bar['frameSize'] = (-.6, -.6 + 1.2 * done / tot, -.025, .025)
        if done < tot:
            return
        for kind, pos in getattr(self, 'pending_mounts', []):
            self.spawn_mob(kind, pos)
            self.mobs[-1].saddled = True
            self.mobs[-1].saddle.show()
        self.pending_mounts = []
        if self.arrival is not None:
            self.arrive()
        elif self.spawn[2] is None:
            sx, sy = self.spawn[:2]
            self.spawn = (sx, sy, self.world.top_solid(int(math.floor(sx)), int(math.floor(sy))) + 1)
            p.pos = list(self.spawn)
        self.state = 'playing'
        self.show(None)
        self.set_mouse_lock(True)
        self.hud_dirty = True
        self.fade, self.fade_to = 1., 0.
        self.refresh_inv()
        self.say('Game Mode: ' + self.mode.capitalize())

    def save_world(self, background=False):
        if not self.world or not self.player or self.state in ('menu', 'loading'):
            return
        if self.net and self.net.role == 'client':
            return
        if self.save_thread is not None and self.save_thread.is_alive():
            if background:
                return
            self.save_thread.join()
        p, w = self.player, self.world
        cp = lambda inv: [list(s) if s else None for s in inv]
        allw = dict(self.worlds)
        allw[self.dim] = w
        raws = {d: ({k: ch.blocks.tobytes() for k, ch in wd.chunks.items() if ch.modified}, dict(wd.saved),
                    {k: cp(v) for k, v in wd.chests.items()}) for d, wd in allw.items()}
        for d, (chs, cst) in self.dim_saved.items():
            raws[d] = ({}, dict(chs), dict(cst))
        mounts = [(m.kind, list(m.pos)) for m in self.mobs if m.saddled]
        data = dict(version=4, seed=w.seed, time=self.time_of_day, mode=self.mode, weather=self.weather, dim=self.dim,
                    mounts=mounts,
                    player=dict(pos=list(p.pos), h=p.h, p=p.p, hp=max(1, p.hp), food=p.food, inv=cp(p.inv), sel=p.sel,
                                flying=p.flying, spawn=self.spawn),
                    adv=sorted(self.adv_done))

        def job():
            try:
                dims = {}
                for d, (raw, base, cst) in raws.items():
                    base.update({k: zlib.compress(b) for k, b in raw.items()})
                    dims[d] = (base, cst)
                data['dims'] = dims
                with open(SAVE_PATH + '.tmp', 'wb') as f:
                    pickle.dump(data, f, protocol=4)
                os.replace(SAVE_PATH + '.tmp', SAVE_PATH)
            except Exception as e:
                print('save failed:', e)
        if background:
            self.save_thread = threading.Thread(target=job, daemon=True)
            self.save_thread.start()
        else:
            job()

    def save_and_quit(self):
        if self.player and self.player.dead:
            self.respawn()
        if self.chat_open:
            self.close_chat()
        if self.state == 'inventory':
            self.toggle_inventory()
        self.save_world()
        if self.net:
            self.net.close()
            self.net = None
        self.start_menu()

    def on_exit(self):
        self.save_world()
        if self.net:
            self.net.close()
        try:
            self.pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def resume(self):
        if self.state == 'paused':
            self.state = 'playing'
            self.show(None)
            self.set_mouse_lock(True)

    def on_escape(self):
        if self.chat_open:
            self.close_chat()
        elif self.typing() and not self.ui_cre.isHidden():
            self.cre_search.guiItem.setFocus(False)
        elif not self.ui_settings.isHidden():
            self.close_settings()
        elif not self.ui_adv.isHidden():
            self.show('pause')
        elif self.state == 'playing':
            self.state = 'paused'
            self.set_mouse_lock(False)
            self.show('pause')
        elif self.state == 'paused':
            self.resume()
        elif self.state == 'inventory':
            self.toggle_inventory()
        elif self.state == 'menu':
            self.show('menu')

    def open_settings(self, back):
        self.settings_back = back
        for k in self.slider_lbl:
            self.sliders[k]['value'] = self.settings[k]
        self.refresh_settings()
        self.show('settings')

    def close_settings(self):
        self.save_settings()
        self.show(self.settings_back)

    def on_slider(self, k):
        self.settings[k] = int(round(self.sliders[k]['value']))
        self.refresh_settings()
        self.apply_settings()

    def on_toggle(self, k):
        if k == 'difficulty':
            self.settings[k] = (self.settings[k] + 1) % 4
        else:
            self.settings[k] = not self.settings[k]
        if k == 'fullscreen':
            self.apply_fullscreen()
        if k == 'fancy_leaves':
            self.apply_leaves()
        self.refresh_settings()
        self.apply_settings()

    def refresh_settings(self):
        for k, (label, t) in self.slider_lbl.items():
            t.setText('%s: %d' % (label, self.settings[k]))
        names = dict(bobbing='View Bobbing', clouds='Clouds', show_fps='Show FPS', fullscreen='Fullscreen')
        for k, b in self.toggles.items():
            if k == 'difficulty':
                b['text'] = 'Difficulty: ' + DIFF_NAMES[self.settings[k]]
            elif k == 'fancy_leaves':
                b['text'] = 'Leaves: ' + ('Fancy' if self.settings[k] else 'Fast')
            elif k == 'discord':
                b['text'] = 'Discord Status: %s' % (self.discord.status if self.settings[k] else 'OFF (restart)')
                b['text_scale'] = .032
            else:
                b['text'] = '%s: %s' % (names[k], 'ON' if self.settings[k] else 'OFF')

    def apply_settings(self):
        self.setFrameRateMeter(bool(self.settings['show_fps']))
        self.clouds.show() if self.settings['clouds'] else self.clouds.hide()

    def apply_fullscreen(self):
        wp = WindowProperties()
        wp.setFullscreen(bool(self.settings['fullscreen']))
        if self.settings['fullscreen']:
            wp.setSize(self.pipe.getDisplayWidth(), self.pipe.getDisplayHeight())
        else:
            wp.setSize(1280, 720)
        self.win.requestProperties(wp)

    def toggle_fullscreen(self):
        self.on_toggle('fullscreen')
        self.save_settings()

    def save_settings(self):
        try:
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(self.settings, f)
        except Exception:
            pass

    # ---------------------------------------------------------------- main loop
    def update(self, task):
        dt = min(self.clock.getDt(), .05)
        st, w = self.state, self.world
        self.mob_snd_t -= dt
        self.music_step(dt)
        if self.net:
            self.net.step(dt)
            st, w = self.state, self.world          # the network may have switched worlds / dropped us to the menu
        self.chat_step(dt)
        if self.player is not None and self.world is not None and st != 'menu':
            self.minimap_step(dt)
            self.adv_step(dt)
        self.discord_t -= dt
        if self.discord_t <= 0:
            self.discord_t = 5.
            self.discord.tick()
        if st == 'inventory' and self.mode == 'creative' and self.chest_pos is None:
            q = self.cre_search.get().strip().lower()
            if q != self.cre_query:
                self.cre_query, self.cre_page = q, 0
                self.refresh_inv()
        if w is not None:
            if st == 'menu':
                self.menu_step(dt)
            else:
                w.stream(self.player.pos[0], self.player.pos[1], self.settings['render_dist'],
                         .006 if st == 'playing' else .02)
        if st == 'loading':
            self.loading_step()
        elif st in ('playing', 'inventory', 'dead'):
            fg = self.win.getProperties().getForeground()
            if st == 'playing':
                if self.had_focus and not fg:
                    self.on_escape()
                elif self.sleep_t < 0:
                    self.mouse_look()
            self.had_focus = fg
            self.world_step(dt, st == 'playing' and self.sleep_t < 0 and not self.chat_open)
        self.fade += max(-dt * 1.4, min(dt * 1.4, self.fade_to - self.fade))
        if self.fade > .01:
            self.ov_fade.setAlphaScale(self.fade)
            self.ov_fade.show()
        else:
            self.ov_fade.hide()
        if self.cursor and self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            self.cursor_icon.setPos(m.x * self.getAspectRatio(), 0, m.y)
        if self.hover is not None and self.mouseWatcherNode.hasMouse():
            m = self.mouseWatcherNode.getMouse()
            self.tooltip.setPos(m.x * self.getAspectRatio() + .04, m.y + .04)
        return task.cont

    def menu_step(self, dt):
        """Cinematic orbit around a structure; the day cycles quickly so the lighting shows off."""
        self.menu_t += dt
        t = self.menu_t
        cx, cy, cz = self.menu_center
        a = t * .045
        r = 27 + math.sin(t * .13) * 4
        self.camera.setPos(cx + math.cos(a) * r, cy + math.sin(a) * r, cz + 15 + math.sin(t * .21) * 3)
        self.camera.lookAt(cx, cy, cz + 2.5)
        self.camLens.setMinFov(self.settings['fov'])
        self.world.stream(cx, cy, min(self.settings['render_dist'], 5))
        self.time_of_day = (self.time_of_day + dt / 110.) % 1.
        self.update_sky()
        self.logo.setH(math.sin(t * .6) * 14)
        self.logo.setP(math.sin(t * .45) * 4)
        self.logo.setZ(10.5 + math.sin(t * 1.3) * .3)
        self.logo_lens.setAspectRatio(self.getAspectRatio())
        self.splash.setScale(.055 * (1 + .07 * math.sin(t * 7)))

    def mouse_look(self):
        if not self.mouse_locked:
            return
        md = self.win.getPointer(0)
        x, y = md.getX(), md.getY()
        cx, cy = self.win.getXSize() // 2, self.win.getYSize() // 2
        if self.mouse_skip > 0:
            self.mouse_skip -= 1
        elif self.mref is not None:
            s, p = self.settings['sens'] * .004, self.player
            p.h -= (x - self.mref[0]) * s
            p.p = max(-89.9, min(89.9, p.p - (y - self.mref[1]) * s))
        self.mref = (cx, cy) if self.win.movePointer(0, cx, cy) else (x, y)

    def world_step(self, dt, active):
        p, w = self.player, self.world
        if not p.dead:
            p.update(dt, active)
        self.update_target()
        if active:
            self.handle_mouse(dt)
        else:
            self.mine_pos = None
            self.crack.hide()
        for lst in (self.mobs, self.items, self.fx):
            for e in lst:
                e.update(dt)
            if any(e.gone for e in lst):
                for e in lst:
                    if e.gone:
                        e.node.removeNode()
                lst[:] = [e for e in lst if not e.gone]
        if p.riding is not None:                     # keep the rider glued to the mount after it moved
            m = p.riding
            p.pos = [m.pos[0], m.pos[1], m.pos[2] + m.d['mount'][2]]
        self.tick_acc += dt
        while self.tick_acc >= .05:
            self.tick_acc -= .05
            w.do_tick()
        self.time_of_day = (self.time_of_day + dt / DAY_LEN) % 1.
        self.spawn_t -= dt
        if self.spawn_t <= 0:
            self.spawn_t = .34
            self.spawn_mobs()
            self.spawner_t = getattr(self, 'spawner_t', 0) + 1
            if self.spawner_t % 3 == 0:
                self.run_spawners()
        self.grow_t += dt
        if self.grow_t > 1:
            self.grow_t = 0.
            w.random_tick(p.pos[0], p.pos[1])
        self.save_t += dt
        if self.save_t > 120:
            self.save_t = 0
            self.save_world(background=True)
        self.weather_step(dt)
        self.ambient_step(dt)
        self.portal_step(dt)
        self.draw_rope()
        self.boss_step(dt)
        self.village_step(dt)
        self.fish_step(dt)
        self.cave_t -= dt
        if self.cave_t <= 0:
            sk, _ = w.light_at(math.floor(p.pos[0]), math.floor(p.pos[1]), math.floor(p.pos[2] + 1.6))
            if sk < 3 and not p.dead:
                self.cave_t = random.uniform(25, 70)
                self.sounds.play(random.choice(('cave1', 'cave2', 'cave3')), None, .8, 'ambient')
            else:
                self.cave_t = random.uniform(6, 15)
        self.attack_cd -= dt
        if self.sleep_t >= 0:
            self.sleep_step(dt)
        self.update_sky()
        self.update_camera(dt)
        self.update_hud(dt)
        self.update_hand(dt)

    def sleep_step(self, dt):
        old = self.sleep_t
        self.sleep_t += dt
        self.fade_to = 1. if self.sleep_t < 2.2 else 0.
        if old < 1.6 <= self.sleep_t:
            self.time_of_day = .03
            self.say('Good morning!')
        if self.sleep_t > 3.5:
            self.sleep_t = -1.

    # ---------------------------------------------------------------- sky, camera, hud
    @staticmethod
    def _mix(a, b, t):
        return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

    def update_sky(self):
        t = self.time_of_day
        s = math.sin(2 * math.pi * t)
        x = min(1., max(0., (s + .1) / .4))
        day = x * x * (3 - 2 * x)
        dusk = max(0., 1 - abs(s) / .3)
        zen = self._mix((.012, .018, .05), (.32, .52, .95), day)
        hor = self._mix((.04, .05, .11), (.7, .82, 1.), day)
        hor = self._mix(hor, (1., .56, .33), dusk * .75)
        zen = self._mix(zen, (.3, .33, .58), dusk * .35)
        glow = tuple(c * dusk for c in (1., .5, .2))
        tint = self._mix(self._mix((.5, .6, 1.), (1., 1., 1.), day), (1., .76, .58), dusk * .6)
        rn = self.rain if self.state != 'menu' else 0.
        if rn > 0:
            grey = tuple(c * (.25 + .5 * day) for c in (.62, .65, .7))
            zen, hor = self._mix(zen, grey, .75 * rn), self._mix(hor, grey, .7 * rn)
            glow = tuple(c * (1 - rn) for c in glow)
            tint = self._mix(tint, (.85, .88, .95), rn)
        self.daylight, self.skytint = min(1., (.16 + .84 * day) * (1 - .42 * rn) + self.flash_sky * .7), tint
        if self.dim == 'silly' and self.state != 'menu':          # Sillyland: endless pink dusk
            pulse = math.sin(self.clock.getFrameTime() * .07)
            zen, hor = (.3 + .05 * pulse, .12, .42), (.95, .55 + .05 * pulse, .78)
            glow, tint, day, rn = (1., .55, .9), (1., .82, .96), .9, 0.
            self.daylight, self.skytint = .8, tint
        if self.flash_sky > 0:
            zen = self._mix(zen, (.85, .85, 1.), self.flash_sky * .6)
            hor = self._mix(hor, (.85, .85, 1.), self.flash_sky * .6)
        cam = self.camera.getPos(self.render)
        R = self.settings['render_dist'] * 16
        fogc, fogr = hor, (R * .55 * (1 - .45 * rn), R * .95 * (1 - .3 * rn))
        under = None
        if self.player is not None and self.state != 'menu':
            head = self.world.get(math.floor(cam.x), math.floor(cam.y), math.floor(cam.z))
            under = FAMILY[head] if FAMILY[head] in (WATER, LAVA) else None
        if under == WATER:
            fogc, fogr = (.04 * self.daylight + .02, .14 * self.daylight + .03, .42 * self.daylight + .05), (0., 18.)
            self.ov_water.setColor(.1, .25, .7, .3)
            self.ov_water.show()
        elif under == LAVA:
            fogc, fogr = (.9, .3, 0), (0., 3.)
            self.ov_water.setColor(.9, .3, 0, .6)
            self.ov_water.show()
        else:
            self.ov_water.hide()
        if under:
            zen = hor = fogc
        a = 2 * math.pi * t
        d = Vec3(math.cos(a), .25, math.sin(a))
        d.normalize()
        self.sky.setPos(cam)
        self.sky.setShaderInput('zenith', Vec3(*zen))
        self.sky.setShaderInput('horizon', Vec3(*hor))
        self.sky.setShaderInput('sundir', d)
        self.sky.setShaderInput('glow', Vec3(*glow))
        self.stars.setPos(cam)
        self.stars.setR(-t * 360)
        self.stars.setAlphaScale(max(0., 1 - day * 1.6) ** 2 * (1 - rn))
        self.fog.setColor(*fogc)
        self.fog.setLinearRange(*fogr)
        self.cloud_fog.setColor(*hor)
        self.setBackgroundColor(*hor, 1)
        held = self.player.held() if (self.player and not self.player.dead) else None
        self.handlight = (.93 + .07 * math.sin(self.clock.getFrameTime() * 9)) if held in EMITTING_ITEMS else 0.
        if self.world:
            r = self.world.root
            r.setShaderInput('time', self.clock.getFrameTime() % 1000.)
            r.setShaderInput('daylight', self.daylight)
            r.setShaderInput('skytint', Vec3(*tint))
            r.setShaderInput('fogcolor', Vec3(*fogc))
            r.setShaderInput('fogrange', Vec2(*fogr))
            r.setShaderInput('brightness', self.settings['brightness'] / 100.)
            r.setShaderInput('handlight', self.handlight)
        self.sun.setPos(cam + d * 300)
        self.moon.setPos(cam - d * 300)
        self.clouds.setPos(cam.x, cam.y, 128)
        drift = self.clock.getFrameTime() * 1.5
        self.clouds.setTexOffset(TextureStage.getDefault(), ((cam.x - 600 + drift) / 768.) % 1, ((cam.y - 600) / 768.) % 1)
        cl = (.25 + .75 * day) * (1 - .4 * rn)
        self.clouds.setColorScale(cl * tint[0] + dusk * .2, cl * tint[1], cl * tint[2], 1)

    def update_camera(self, dt):
        p = self.player
        eye = 1.62 - (.25 if p.sneak else 0)
        sp = math.hypot(p.vel[0], p.vel[1])
        bz = bx = 0.
        if p.on_ground and sp > .5 and not p.dead:
            old = self.step_phase
            self.step_phase += dt * sp * 1.9
            if self.settings['bobbing']:
                bz, bx = abs(math.sin(self.step_phase)) * .06, math.cos(self.step_phase) * .03
            if int(old / math.pi) != int(self.step_phase / math.pi):
                self.sounds.play('step', None, .6)
        hr = math.radians(p.h)
        p.step_off = max(-.6, min(.6, p.step_off)) * max(0., 1 - 14 * dt)   # ease the camera through slab steps
        self.camera.setPos(p.pos[0] + math.cos(hr) * bx, p.pos[1] + math.sin(hr) * bx,
                           p.pos[2] + eye + bz + p.step_off - (1.4 if p.dead else 0))
        self.shake = max(0., self.shake - dt * 3)
        self.camera.setHpr(p.h, p.p, math.sin(self.shake * 30) * self.shake * 6 + (60 if p.dead else 0))
        target = self.settings['fov'] + (8 if p.sprint else 0) + (4 if p.flying else 0)
        self.fov_cur += (target - self.fov_cur) * min(1., 5. * dt)   # smooth, no FOV jumps when sprinting
        self.camLens.setMinFov(self.fov_cur)
        self.flash = max(0., self.flash - dt * 2)
        if self.flash > 0:
            self.ov_hurt.setAlphaScale(self.flash)
            self.ov_hurt.show()
        else:
            self.ov_hurt.hide()

    def say(self, msg):
        self.notice.setText(msg)
        self.notice_t = 2.5

    def update_hud(self, dt):
        p = self.player
        self.notice_t -= dt
        if self.notice_t <= 0:
            self.notice.setText('')
        self.name_t -= dt
        self.item_name.setAlphaScale(max(0., min(1., self.name_t)))
        if self.hud_dirty:
            self.hud_dirty = False
            surv = self.mode == 'survival'
            for i in range(10):
                v = p.hp - i * 2
                self.hearts[i].setTexture(self.gtex['heart' if v >= 2 else ('heart_half' if v == 1 else 'heart_empty')], 1)
                v = p.food - i * 2
                self.foods[i].setTexture(self.gtex['food' if v >= 2 else ('food_half' if v == 1 else 'food_empty')], 1)
                for n in (self.hearts[i], self.foods[i]):
                    n.show() if surv else n.hide()
        nb = int(math.ceil(p.air)) if (self.mode == 'survival' and p.air < 10) else 0
        for i, b in enumerate(self.bubbles):
            b.show() if i < nb else b.hide()
        hb = p.inv_t > .3 and self.mode == 'survival'
        for h in self.hearts:
            h.setColorScale((1.6, 1.6, 1.6, 1) if hb else (1, 1, 1, 1))
        if self.debug:
            x, y, z = p.pos
            sk, bl = self.world.light_at(math.floor(x), math.floor(y), math.floor(z + 1))
            biome, _ = self.world.gen.biome_at(x, y)
            self.debug_txt.setText('PyCraft 2.0  %d fps\nXYZ: %.1f / %.1f / %.1f\nChunk: %d, %d   Facing: %d\n'
                                   'Biome: %s   Light: sky %d, block %d\nMobs: %d  Items: %d  Chunks: %d\n'
                                   'Time: %02d:%02d  Seed: %s\nMode: %s   Weather: %s (%.2f)' % (
                                       self.clock.getAverageFrameRate(), x, y, z, math.floor(x) >> 4, math.floor(y) >> 4,
                                       p.h % 360, BIOME_NAMES[biome], sk, bl, len(self.mobs), len(self.items),
                                       len(self.world.chunks), (int(self.time_of_day * 24) + 6) % 24,
                                       int(self.time_of_day * 1440) % 60, self.world.seed, self.mode,
                                       self.weather, self.rain))
        else:
            self.debug_txt.setText('')

    def refresh_hotbar(self):
        p = self.player
        for i in range(9):
            s = p.inv[i]
            if s:
                self.hot_icons[i].setTexture(self.icons[s[0]], 1)
                self.hot_icons[i].show()
                self.hot_txt[i].setText(str(s[1]) if s[1] > 1 and self.mode == 'survival' else '')
            else:
                self.hot_icons[i].hide()
                self.hot_txt[i].setText('')
        self.hot_sel.setX((p.sel - 4) * .115)
        self.hud_dirty = True

    def update_hand(self, dt):
        p = self.player
        it = p.held()
        if it != self.hand_item:
            self.hand_item = it
            self.hand.getChildren().detach()
            if it is None:
                box_np(self.hand, (-.07, -.05, -.07), (.07, .45, .07), (.92, .72, .58)).setTextureOff(1)
                self.hand_base = ((.42, .55, -.42), (10, 25, 0))
            elif isblk(it) and (CUBE[it] or it in (CHEST, BED) or it in SLABS):
                cube_np(TEXIDX[it], .3, (-.15, -.15, -.15)).reparentTo(self.hand)
                self.hand_base = ((.38, .7, -.36), (35, 0, 0))
            else:
                m = self.item_model(it, .42)
                m.reparentTo(self.hand)
                m.setPos(0, 0, -.21)
                self.hand_base = ((.36, .62, -.3), (-75, -10, -20))
            self.hand.setTexture(self.atlas)
        self.swing = max(0., self.swing - dt * 4)
        s = math.sin(self.swing * math.pi)
        (x, y, z), (h, pp, r) = self.hand_base
        bob = math.sin(self.step_phase * 2) * .02 if self.settings['bobbing'] else 0
        self.hand.setPos(x - s * .15, y + s * .1, z - s * .12 + bob)
        self.hand.setHpr(h, pp - s * 50, r)
        L = self.light_scale(p.pos[0], p.pos[1], p.pos[2] + 1.5)
        self.hand.setColorScale(L, L, L, 1)
        self.hand.show() if (self.state in ('playing', 'inventory') and not self.hud_hidden and not p.dead) else self.hand.hide()

    # ---------------------------------------------------------------- targeting / mining / placing
    def look_dir(self):
        p = self.player
        hr, pr = math.radians(p.h), math.radians(p.p)
        return (-math.sin(hr) * math.cos(pr), math.cos(hr) * math.cos(pr), math.sin(pr))

    def eye(self):
        p = self.player
        return (p.pos[0], p.pos[1], p.pos[2] + 1.62 - (.25 if p.sneak else 0))

    def update_target(self):
        p = self.player
        self.target = self.target_prev = self.target_mob = None
        if p.dead or self.state not in ('playing', 'inventory'):
            self.outline.hide()
            return
        o, d = self.eye(), self.look_dir()
        hit, prev, t = self.world.raycast(o, d, REACH)
        best = None
        for m in self.mobs + (list(self.net.players.values()) if self.net else []):
            if m.dead < 0 and math.dist(m.pos, o) < self.reach() + 4 and m is not p.riding:
                r = m.ray(o, d)
                if r is not None and r <= self.reach() and (best is None or r < best[0]):
                    best = (r, m)
        if best and (t is None or best[0] < t):
            self.target_mob = best[1]
            self.outline.hide()
        elif hit:
            self.target, self.target_prev = hit, prev
            self.outline.setPos(*hit)
            self.outline.show()
        else:
            self.outline.hide()

    def can_harvest(self, b):
        need = BDEF[b][4]
        tool = TOOLS.get(self.player.held())
        return need == 0 or (tool is not None and tool[0] == 'pickaxe' and tool[1] >= need)

    def break_time(self, b):
        hard = HARD[b]
        if hard <= 0:
            return 0.
        tool, speed = TOOLS.get(self.player.held()), 1.
        if tool and tool[0] == BDEF[b][3]:
            speed = (2., 4., 6., 8.)[tool[1] - 1] * (2.5 if b == COBWEB else 1.)
        return hard * (1.5 if self.can_harvest(b) else 5.) / speed

    def handle_mouse(self, dt):
        p, mw = self.player, self.mouseWatcherNode
        self.break_cd -= dt
        self.use_cd -= dt
        if p.dead:
            return
        if mw.isButtonDown(MouseButton.three()) and self.use_cd <= 0:
            self.use_item()
        if not mw.isButtonDown(MouseButton.one()) or self.target is None or self.target_mob is not None:
            self.mine_pos = None
            self.crack.hide()
            return
        if self.break_cd > 0:
            return
        if self.mode == 'creative':
            self.break_block(self.target)
            self.break_cd = .22
            return
        b = self.world.get(*self.target)
        if HARD[b] < 0:
            return
        if self.mine_pos != self.target:
            self.mine_pos, self.mine_prog = self.target, 0.
        bt = self.break_time(b)
        self.mine_prog = 1. if bt <= 0 else self.mine_prog + dt / bt
        if self.swing <= 0:
            self.swing = 1.
            self.sounds.play('step', self.target, .5)
            self.particles((self.target[0] + .5, self.target[1] + .5, self.target[2] + .5), 2, tile=TEXIDX[b, 1], spread=.55)
        if self.mine_prog >= 1:
            self.break_block(self.target)
            self.break_cd = .15
            self.mine_pos = None
            self.crack.hide()
        else:
            self.crack.setPos(*self.target)
            self.crack.setTexOffset(TextureStage.getDefault(), min(4, int(self.mine_prog * 5)) / 16., 0)
            L = self.light_scale(self.target[0] + .5, self.target[1] + .5, self.target[2] + 1.2)
            self.crack.setColorScale(L, L, L, .9)
            self.crack.show()

    def break_block(self, pos):
        w = self.world
        b = w.get(*pos)
        if b == AIR or (HARD[b] < 0 and self.mode == 'survival'):
            return
        survival = self.mode == 'survival'
        harvest = survival and self.can_harvest(b)
        if b == CHEST:
            for s in w.chest_inv(pos):
                if s:
                    self.spawn_item((pos[0] + .5, pos[1] + .5, pos[2] + .5), s[0], s[1])
            w.chests.pop(pos, None)
        w.set(*pos, AIR)
        self.swing = 1.
        self.sounds.play('break', pos)
        self.particles((pos[0] + .5, pos[1] + .5, pos[2] + .5), 12, tile=TEXIDX[b, 1], spread=.4)
        if b == WHEAT3:
            self.adv('farm')
        if harvest:
            for it, c in drops_for(b):
                self.spawn_item((pos[0] + .5, pos[1] + .5, pos[2] + .3), it, c)
        if survival:
            self.player.exhaust += .005

    def on_lclick(self):
        if self.state != 'playing' or self.player.dead or self.sleep_t >= 0 or self.chat_open:
            return
        self.swing = 1.
        m = self.target_mob
        if m is not None and self.attack_cd <= 0:
            tool, wpn = TOOLS.get(self.player.held()), WEAPONS.get(self.player.held())
            dmg = wpn[0] if wpn else (1 if tool is None else (3 + tool[1] if tool[0] == 'sword' else 1 + tool[1]))
            wk = WEAPON_KIND.get(self.player.held())
            if wk and wk[1] == 1 and self.player.vel[2] < -4:            # mace smash
                dmg *= 2
                self.shake = max(self.shake, .35)
                self.particles((m.pos[0], m.pos[1], m.pos[2] + .3), 14, color=(.8, .8, .75), spread=.8, up=True)
            if self.player.vel[2] < -1 and not self.player.on_ground:
                dmg = int(dmg * 1.5)                          # critical hit while falling
                self.particles((m.pos[0], m.pos[1], m.pos[2] + m.hh), 8, color=(1, .9, .4))
            if m.hurt(dmg, self.player.pos):
                self.player.exhaust += .1
                if isinstance(m, Mob) and m.hp <= 0 and m.d.get('hostile'):
                    self.adv('kill')
            self.attack_cd = wpn[1] if wpn else .3
        elif self.mode == 'creative' and self.target is not None:
            self.break_block(self.target)
            self.break_cd = .3

    def on_rclick(self):
        if self.state == 'playing' and not self.player.dead and self.sleep_t < 0 and not self.chat_open:
            self.use_item()

    def place_ok(self, pos):
        for e in [self.player] + self.mobs:
            if (e.pos[0] - e.hw < pos[0] + 1 and e.pos[0] + e.hw > pos[0] and e.pos[1] - e.hw < pos[1] + 1 and
                    e.pos[1] + e.hw > pos[1] and e.pos[2] < pos[2] + 1 and e.pos[2] + e.hh > pos[2]):
                return False
        return True

    def use_item(self):
        p, w = self.player, self.world
        self.use_cd = .25
        it = p.held()
        m = self.target_mob
        if isinstance(m, Mob) and m.kind == 'villager' and m.dead < 0:
            self.trade_with(m)
            return
        if it == FISHING_ROD:
            self.use_rod()
            return
        if isinstance(m, Mob) and m.d.get('mount') and m.dead < 0 and not p.sneak:
            if not m.saddled:
                if it == SADDLE:
                    m.saddled = True
                    m.saddle.show()
                    self.sounds.play(m.d['sound'] or 'pop', m.pos)
                    if self.mode == 'survival':
                        p.consume_held()
                        self.refresh_inv()
                else:
                    self.say('Use a Saddle on it first')
            else:
                p.riding, m.rider = m, p
                p.grapple = None
                self.adv('ride')
                self.say('Riding! WASD steer, Space jump, Shift to get off')
            return
        tb = w.get(*self.target) if self.target else AIR
        if self.target and not p.sneak:
            if tb == CRAFTING:
                self.toggle_inventory(table=True)
                return
            if tb == CHEST:
                self.sounds.play('chest', self.target)
                if self.net and self.net.role == 'client':
                    self.net.conns[0].send({'t': 'chest_get', 'pos': _k2s(self.target)})
                if self.target[2] < SEA - 6:
                    self.adv('loot')
                self.toggle_inventory(chest=self.target)
                return
            if tb == TNT:
                if self.net and self.net.role == 'client':
                    self.net.conns[0].send({'t': 'prime', 'pos': _k2s(self.target)})
                else:
                    w.set(*self.target, AIR)
                    self.add_fx(PrimedTNT(self, *self.target))
                self.swing = 1.
                return
            if tb in (BED, BED_HEAD):
                self.try_sleep(self.target)
                return
        if it is None:
            return
        if it == BOW:
            self.shoot_bow()
            return
        if it == GRAPPLE:
            self.fire_grapple()
            return
        if it == ROYAL_SCEPTER:
            self.scepter()
            return
        if it == SLINGSHOT:
            self.fire_sling()
            return
        if it in FOOD:
            self.eat(it)
            return
        if it in (BUCKET, WATER_BUCKET, LAVA_BUCKET):
            self.use_bucket(it)
            return
        if self.target is None:
            return
        x, y, z = self.target
        if it == HOE:
            if tb in (GRASS, DIRT, SNOWY_GRASS) and w.get(x, y, z + 1) in (AIR, TALL_GRASS, FERN):
                w.set(x, y, z + 1, AIR)
                w.set(x, y, z, FARMLAND)
                self.sounds.play('step', self.target)
                self.swing = 1.
            return
        if it == BONE_MEAL:
            if w.grow(x, y, z, meal=True) is not False:
                self.particles((x + .5, y + .5, z + 1.1), 10, color=(.5, 1, .4), spread=.5, up=True)
                self.swing = 1.
                if self.mode == 'survival':
                    p.consume_held()
                    self.refresh_inv()
            return
        if it == SEEDS:
            if tb == FARMLAND and w.get(x, y, z + 1) == AIR:
                w.set(x, y, z + 1, WHEAT1)
                self.sounds.play('place', self.target)
                self.swing = 1.
                if self.mode == 'survival':
                    p.consume_held()
                    self.refresh_inv()
            return
        pos = self.target if REPL[tb] else self.target_prev
        if pos is None or not REPL[w.get(*pos)] or not 0 <= pos[2] < H:
            return
        below, above = w.get(pos[0], pos[1], pos[2] - 1), w.get(pos[0], pos[1], pos[2] + 1)
        if it in EGG_MOB:
            self.spawn_mob(EGG_MOB[it], (pos[0] + .5, pos[1] + .5, pos[2]))
        elif it == BED:
            hr = math.radians(p.h)
            fx, fy = -math.sin(hr), math.cos(hr)
            d = ((1 if fx > 0 else -1), 0) if abs(fx) > abs(fy) else (0, (1 if fy > 0 else -1))
            head = (pos[0] + d[0], pos[1] + d[1], pos[2])
            if not REPL[w.get(*head)] or not self.place_ok(pos) or not self.place_ok(head):
                return
            w.set(*pos, BED)
            w.set(*head, BED_HEAD)
            self.sounds.play('place', pos)
        elif it in SLABS and tb == it and self.target_prev == (x, y, z + 1):
            w.set(x, y, z, SLABS[it])
            self.sounds.play('place', self.target)
        elif isblk(it):
            place = it
            if it == TORCH:
                if not OPAQUE[below]:
                    if any(OPAQUE[w.get(pos[0] + dx, pos[1] + dy, pos[2])] for dx, dy in HN):
                        place = WALL_TORCH
                    else:
                        return
            elif it == LANTERN:
                if not (OPAQUE[below] or OPAQUE[above]):
                    return
            elif PLANT[it] and not supported(it, below):
                return
            elif it == CACTUS and below not in (SAND, RED_SAND, CACTUS):
                return
            if SOLID[place] and not self.place_ok(pos):
                return
            w.set(*pos, place)
            if place in (TORCH, WALL_TORCH):
                self.adv('torch')
            if place == CHEST:
                w.chests[pos] = [None] * 27
            self.sounds.play('splash' if FLUID[place] else 'place', pos)
        else:
            return
        self.swing = 1.
        if self.mode == 'survival':
            p.consume_held()
            self.refresh_inv()

    def use_bucket(self, it):
        p, w = self.player, self.world
        if it == BUCKET:
            hit, prev, t = w.raycast(self.eye(), self.look_dir(), REACH, SRC_MASK)
            if hit is None or w.get(*hit) not in (WATER, LAVA):
                return
            f = w.get(*hit)
            w.set(*hit, AIR)
            new = WATER_BUCKET if f == WATER else LAVA_BUCKET
            if self.mode == 'survival':
                p.consume_held()
                if p.inv[p.sel] is None:
                    p.inv[p.sel] = [new, 1]
                elif p.add_item(new, 1):
                    self.spawn_item(p.pos, new, 1)
            else:
                p.inv[p.sel] = [new, 1]
            self.sounds.play('splash' if f == WATER else 'fizz', hit)
        else:
            if self.target is None:
                return
            tb = w.get(*self.target)
            pos = self.target if REPL[tb] else self.target_prev
            if pos is None or not (REPL[w.get(*pos)] or FLUID[w.get(*pos)]):
                return
            w.place_fluid(*pos, WATER if it == WATER_BUCKET else LAVA)
            self.sounds.play('splash', pos)
            if it == LAVA_BUCKET:
                self.try_portal(*pos)
            if self.mode == 'survival':
                p.inv[p.sel] = [BUCKET, 1]
        self.swing = 1.
        self.refresh_inv()

    def shoot_bow(self):
        p = self.player
        if self.mode == 'survival':
            if p.count_item(ARROW) == 0:
                self.say('You need arrows!')
                return
            p.remove_item(ARROW, 1)
            self.refresh_inv()
        e, d = self.eye(), self.look_dir()
        self.fx.append(Arrow(self, (e[0] + d[0] * .6, e[1] + d[1] * .6, e[2] + d[2] * .6 - .1),
                             (d[0] * 32, d[1] * 32, d[2] * 32), p, 7.))
        self.sounds.play('twang')
        self.use_cd, self.swing = .7, 1.

    def shoot_arrow(self, o, tgt, shooter, speed, dmg, spread, style='arrow'):
        dx, dy, dz = tgt[0] - o[0], tgt[1] - o[1], tgt[2] - o[2]
        t = max(.1, math.hypot(dx, dy) / speed)
        v = [dx / t + random.gauss(0, spread * speed), dy / t + random.gauss(0, spread * speed), dz / t + 10 * t]
        self.fx.append(Arrow(self, o, v, shooter, dmg, style))
        self.sounds.play('giggle' if style == 'shard' else 'twang', o, .8)

    def try_sleep(self, pos):
        p = self.player
        self.spawn = (pos[0] + .5, pos[1] + .5, pos[2] + .6)
        if self.net and self.net.role == 'client':
            self.say('Respawn point set - only the host can skip the night')
            return
        if self.daylight > .5:
            self.say('Respawn point set - you can only sleep at night')
            return
        if any(m.d.get('hostile') and m.dead < 0 and math.dist(m.pos, p.pos) < 10 for m in self.mobs):
            self.say('You may not rest now, there are monsters nearby')
            return
        self.sleep_t = 0.
        self.adv('bed')
        p.vel = [0., 0., 0.]
        self.say('Sleeping...  (respawn point set)')
        self.sounds.play('sleep')

    def eat(self, it):
        p = self.player
        if self.mode == 'creative' or (p.food >= 20 and p.hp >= 20 and it != GOLDEN_APPLE):
            return
        f, h = FOOD[it]
        p.food, p.hp = min(20, p.food + f), min(20, p.hp + h)
        p.exhaust = 0.
        p.consume_held()
        self.use_cd, self.swing, self.hud_dirty = .6, 1., True
        self.sounds.play('eat')
        self.adv('eat')
        e = self.eye()
        d = self.look_dir()
        self.particles((e[0] + d[0] * .5, e[1] + d[1] * .5, e[2] - .3), 6, tile=ICON_TILE[it], spread=.1)
        self.say('Ate %s  (+%d health)' % (item_name(it), h))
        if it == SILLY_BERRY:
            p.boost_t = 30.
            self.say('Boing! Super jumps for 30 seconds')
        self.refresh_inv()

    def pick_block(self):
        if self.state != 'playing' or self.target is None:
            return
        b, p = self.world.get(*self.target), self.player
        b = {WALL_TORCH: TORCH, WHEAT1: SEEDS, WHEAT2: SEEDS, WHEAT3: SEEDS, BED_HEAD: BED}.get(b, b)
        for i in range(9):
            if p.inv[i] and p.inv[i][0] == b:
                self.select_slot(i)
                return
        if self.mode == 'creative':
            free = next((i for i in range(9) if p.inv[i] is None), p.sel)
            p.inv[free] = [b, max_stack(b)]
            self.select_slot(free)

    def typing(self):
        return not self.ui_cre.isHidden() and self.cre_search.guiItem.getFocus()

    def drop_held(self):
        p = self.player
        if self.typing() or self.state != 'playing' or p.dead or p.inv[p.sel] is None:
            return
        s, d, e = p.inv[p.sel], self.look_dir(), self.eye()
        it = ItemDrop(self, (e[0] + d[0] * .4, e[1] + d[1] * .4, e[2] - .3), s[0], 1, (d[0] * 6, d[1] * 6, d[2] * 6 + 2))
        it.age = -1.
        self.items.append(it)
        p.consume_held()
        self.refresh_inv()

    # ---------------------------------------------------------------- keys
    def select_slot(self, i):
        if self.state in ('playing', 'inventory') and self.player and not self.typing():
            self.player.sel = i
            self.refresh_hotbar()
            h = self.player.held()
            self.item_name.setText(item_name(h) if h else '')
            self.name_t = 2.5

    def scroll(self, d):
        if self.state == 'playing':
            self.select_slot((self.player.sel + d) % 9)
        elif self.state == 'inventory' and self.mode == 'creative' and self.chest_pos is None:
            self.cre_flip(1 if d > 0 else -1)

    def toggle_mode(self):
        if self.state not in ('playing', 'paused', 'inventory') or self.player.dead or self.typing():
            return
        reopen = self.state == 'inventory'
        if reopen:
            self.toggle_inventory()
        self.mode = 'creative' if self.mode == 'survival' else 'survival'
        p = self.player
        p.flying, p.fall_start, p.air = False, None, 10.
        self.say('Game Mode: ' + self.mode.capitalize())
        self.sounds.play('click')
        self.hud_dirty = True
        self.refresh_inv()
        if self.state == 'paused':
            self.btn_pmode['text'] = 'Game Mode: ' + self.mode.capitalize()
        if reopen:
            self.toggle_inventory()

    def toggle_fly(self):
        if self.state == 'playing' and self.mode == 'creative' and not self.typing():
            p = self.player
            p.flying, p.vel[2] = not p.flying, 0.
            self.say('Flying: ' + ('ON' if p.flying else 'OFF'))

    def on_space(self):
        if self.state != 'playing' or self.mode != 'creative' or self.typing():
            return
        now = self.clock.getFrameTime()
        if now - self.last_space < .3:
            self.toggle_fly()
            self.last_space = 0.
        else:
            self.last_space = now

    def toggle_hud(self):
        if self.state in ('playing', 'inventory'):
            self.hud_hidden = not self.hud_hidden
            for n in (self.hud, self.hud_b):
                n.hide() if self.hud_hidden else n.show()

    def toggle_debug(self):
        self.debug = not self.debug

    def take_screenshot(self):
        fn = self.screenshot(namePrefix=os.path.join(DATA_DIR, 'screenshot'))
        if self.state == 'playing' and fn:
            self.say('Saved ' + os.path.basename(str(fn)))

    # ---------------------------------------------------------------- inventory UI
    def toggle_inventory(self, table=False, chest=None):
        p = self.player
        if self.typing():
            return
        if self.state == 'playing' and not p.dead and self.sleep_t < 0:
            self.state = 'inventory'
            self.chest_pos = chest
            self.near_table = table or self.table_nearby()
            self.craft_page = 0
            self.set_mouse_lock(False)
            self.show('chest' if chest else ('cre' if self.mode == 'creative' else 'inv'))
            self.refresh_inv()
        elif self.state == 'inventory':
            if self.cursor:
                left = p.add_item(*self.cursor)
                if left:
                    self.spawn_item((p.pos[0], p.pos[1], p.pos[2] + 1), self.cursor[0], left)
                self.cursor = None
            if self.chest_pos is not None:
                self.sounds.play('chest', self.chest_pos, .7)
            self.chest_pos = None
            self.slot_hover(None)
            self.state = 'playing'
            self.show(None)
            self.set_mouse_lock(True)
            self.refresh_inv()

    def table_nearby(self):
        x, y, z = (int(math.floor(v)) for v in self.player.pos)
        return any(self.world.get(x + dx, y + dy, z + dz) == CRAFTING
                   for dx in range(-3, 4) for dy in range(-3, 4) for dz in range(-2, 4))

    def container(self, kind):
        return self.world.chest_inv(self.chest_pos) if kind == 'chest' else self.player.inv

    def slot_click(self, ident, btn):
        if self.state != 'inventory':
            return
        kind, i = ident
        c = self.cursor
        if kind == 'cre':
            self.cre_search.guiItem.setFocus(False)
            idx = self.cre_page * 60 + i
            if idx < len(self.cre_list):
                it = self.cre_list[idx]
                if c and c[0] == it:
                    c[1] = min(max_stack(it), c[1] + (max_stack(it) if btn == 1 else 1))
                elif c:
                    self.cursor = None
                else:
                    self.cursor = [it, max_stack(it) if btn == 1 else 1]
            else:
                self.cursor = None
        else:
            inv = self.container(kind)
            s = inv[i]
            if btn == 1 and s and c is None and self.chest_pos is not None and self.key('shift'):
                other = self.player.inv if kind == 'chest' else self.world.chest_inv(self.chest_pos)
                left = add_to(other, s[0], s[1])
                inv[i] = [s[0], left] if left else None
            elif btn == 1:
                if c and s and s[0] == c[0]:
                    take = min(max_stack(s[0]) - s[1], c[1])
                    s[1] += take
                    c[1] -= take
                    if c[1] <= 0:
                        self.cursor = None
                else:
                    inv[i], self.cursor = c, s
            else:
                if c is None and s:
                    n = (s[1] + 1) // 2
                    self.cursor = [s[0], n]
                    s[1] -= n
                    if s[1] <= 0:
                        inv[i] = None
                elif c and (s is None or (s[0] == c[0] and s[1] < max_stack(s[0]))):
                    if s is None:
                        inv[i] = [c[0], 1]
                    else:
                        s[1] += 1
                    c[1] -= 1
                    if c[1] <= 0:
                        self.cursor = None
                elif c and s:
                    inv[i], self.cursor = c, s
        self.sounds.play('click', None, .5)
        if self.net and self.chest_pos is not None and kind in ('chest', 'inv'):
            self.net.chest_changed(self.chest_pos)
        self.slot_hover(ident)
        self.refresh_inv()

    def drop_cursor(self):
        if self.state != 'inventory' or not self.cursor:
            return
        if self.mode == 'survival':
            p, d = self.player, self.look_dir()
            e = ItemDrop(self, (p.pos[0] + d[0], p.pos[1] + d[1], p.pos[2] + 1.3), self.cursor[0], self.cursor[1],
                         (d[0] * 5, d[1] * 5, 3))
            e.age = -1.
            self.items.append(e)
        self.cursor = None
        self.refresh_inv()

    def slot_hover(self, ident):
        it = None
        if ident is not None and self.player and self.state == 'inventory':
            if ident[0] == 'cre':
                idx = self.cre_page * 60 + ident[1]
                it = self.cre_list[idx] if idx < len(self.cre_list) else None
            elif ident[0] != 'chest' or self.chest_pos is not None:
                s = self.container(ident[0])[ident[1]]
                it = s[0] if s else None
        if it is None:
            self.hover = None
            self.tooltip.hide()
        else:
            self.hover = ident
            self.tooltip.setText(item_name(it))
            self.tooltip.show()

    def cre_flip(self, d):
        pages = max(1, (len(self.cre_list) + 59) // 60)
        self.cre_page = (self.cre_page + d) % pages
        self.refresh_inv()

    def set_cre_tab(self, t):
        self.cre_tab, self.cre_page = t, 0
        self.cre_search.guiItem.setFocus(False)
        self.refresh_inv()

    def craft_flip(self, d):
        pages = (len(RECIPES) + 8) // 9
        self.craft_page = (self.craft_page + d) % pages
        self.refresh_inv()

    def recipe_list(self):
        p = self.player
        rows = []
        for r in RECIPES:
            ok = all(p.count_item(i) >= c for i, c in r[1]) and (not r[2] or self.near_table)
            rows.append((r, ok))
        return sorted(rows, key=lambda t: not t[1])

    def craft_click(self, k):
        rows = self.recipe_list()
        idx = self.craft_page * 9 + k
        if idx >= len(rows) or not rows[idx][1]:
            return
        p = self.player
        (res, n), ing, _ = rows[idx][0]
        for i, c in ing:
            p.remove_item(i, c)
        left = p.add_item(res, n)
        if left:
            self.spawn_item((p.pos[0], p.pos[1], p.pos[2] + 1), res, left)
        self.sounds.play('pop', None, .6)
        self.refresh_inv()

    def refresh_inv(self):
        p = self.player
        if p is None:
            return
        self.refresh_hotbar()
        if self.state != 'inventory':
            self.cursor_icon.hide()
            return
        if self.chest_pos is not None:
            ci = self.world.chest_inv(self.chest_pos)
            for i, sw in enumerate(self.chest_slots):
                sw.set(ci[i])
            for i, sw in enumerate(self.chest_inv):
                sw.set(p.inv[i])
        elif self.mode == 'creative':
            q = self.cre_query
            self.cre_list = [i for i in CREATIVE_ITEMS if (self.cre_tab == 'All' or item_cat(i) == self.cre_tab)
                             and (not q or q in item_name(i).lower())]
            pages = max(1, (len(self.cre_list) + 59) // 60)
            self.cre_page = min(self.cre_page, pages - 1)
            for i, sw in enumerate(self.cre_hot):
                sw.set(p.inv[i])
            for k, sw in enumerate(self.cre_slots):
                idx = self.cre_page * 60 + k
                sw.set([self.cre_list[idx], 1] if idx < len(self.cre_list) else None)
            self.cre_pg.setText('%d/%d' % (self.cre_page + 1, pages))
            self.cre_info.setText('%s: %d items%s' % (self.cre_tab, len(self.cre_list), ('  matching "%s"' % q) if q else ''))
            for t, b in self.cre_tabs.items():
                b['frameColor'] = ((.25, .45, .8, 1),) * 4 if t == self.cre_tab else \
                    ((.42, .42, .45, .95), (.3, .3, .55, 1), (.5, .52, .78, 1), (.25, .25, .25, .7))
        else:
            for i, sw in enumerate(self.inv_slots):
                sw.set(p.inv[i])
            rows = self.recipe_list()
            pages = (len(rows) + 8) // 9
            self.craft_page = min(self.craft_page, pages - 1)
            for k, (b, ic, t1, t2) in enumerate(self.craft_rows):
                idx = self.craft_page * 9 + k
                if idx >= len(rows):
                    b.hide()
                    continue
                b.show()
                ((res, n), ing, tbl), ok = rows[idx]
                ic.setTexture(self.icons[res], 1)
                ic.setAlphaScale(1 if ok else .45)
                t1.setText('%s x%d' % (item_name(res), n))
                need = ', '.join('%d %s' % (c, item_name(i)) for i, c in ing)
                t2.setText(need + ('   [needs Crafting Table]' if tbl and not self.near_table else ''))
                t1.setFg((.05, .3, .05, 1) if ok else (.42, .42, .42, 1))
                t2.setFg((.12, .12, .12, 1) if ok else (.45, .4, .4, 1))
            self.craft_pg.setText('%d/%d' % (self.craft_page + 1, pages))
            self.craft_note.setText('Crafting Table nearby' if self.near_table else 'Stand near a Crafting Table for more')
            self.inv_stats.setText('Health %d/20     Hunger %d/20\nRight-click food to eat.  Left/right-click slots to move items.' % (p.hp, p.food))
        if self.cursor:
            self.cursor_icon.setTexture(self.icons[self.cursor[0]], 1)
            self.cursor_txt.setText(str(self.cursor[1]) if self.cursor[1] > 1 else '')
            self.cursor_icon.show()
        else:
            self.cursor_icon.hide()

    # ---------------------------------------------------------------- entities / effects
    def extrude(self, it):
        """3D item model: the 16x16 sprite extruded one pixel thick (cached)."""
        m = self.ext_cache.get(it)
        if m is not None:
            return m
        names = {v: k for k, v in TILE.items()}
        tile = int(ICON_TILE[it])
        img = self.tile_imgs[names[tile]]
        a = img[..., 3] > 127
        u0, v0 = (tile % 16) / 16., 1 - (tile // 16 + 1) / AR
        th = 1 / 16.
        vs, cs, us = [], [], []
        for fi, sh in ((3, 1.), (2, .78)):
            corn = FACES[fi][1].copy()
            v = corn.copy()
            v[:, 0] -= .5
            v[:, 1] = (v[:, 1] - .5) * th
            uv = np.stack([u0 + EPS + corn[:, 0] * TSU, v0 + EPS + corn[:, 2] * TSV], 1)
            vs.append(v[None]), cs.append(np.array([[[sh, sh, sh, 1]] * 4], np.float32)), us.append(uv[None])
        pad = np.pad(a, 1)
        rr, cc = np.nonzero(a)
        for fi, (dr, dc), sh in ((0, (0, 1), .82), (1, (0, -1), .82), (4, (-1, 0), 1.), (5, (1, 0), .6)):
            m = ~pad[rr + 1 + dr, cc + 1 + dc]
            if not m.any():
                continue
            r_, c_ = rr[m], cc[m]
            corn = FACES[fi][1]
            mn = np.stack([c_ / 16. - .5, np.full(r_.size, -th / 2), 1 - (r_ + 1) / 16.], 1).astype(np.float32)
            v = mn[:, None, :] + corn[None] * np.array([1 / 16., th, 1 / 16.], np.float32)
            uv = np.empty((r_.size, 4, 2), np.float32)
            uv[..., 0] = (u0 + (c_ + .5) / 256.)[:, None]
            uv[..., 1] = (v0 + (15 - r_ + .5) / (16. * AR))[:, None]
            c = np.full((r_.size, 4, 4), sh, np.float32)
            c[..., 3] = 1
            vs.append(v), cs.append(c), us.append(uv)
        m = geom_np(np.concatenate(vs), np.concatenate(cs), np.concatenate(us), 'item')
        m.setTransparency(TransparencyAttrib.MBinary)
        m.setTwoSided(True)
        self.ext_cache[it] = m
        return m

    def item_model(self, it, s):
        if isblk(it) and (CUBE[it] or it in (CHEST, BED) or it in SLABS):
            return cube_np(TEXIDX[it], s, (-s / 2, -s / 2, 0))
        n = NodePath('item')
        m = self.extrude(it).copyTo(n)
        m.setScale(s)
        return n

    def spawn_item(self, pos, item, count):
        if len(self.items) < 250:
            self.items.append(ItemDrop(self, pos, item, count))

    def spawn_mob(self, kind, pos):
        if len(self.mobs) < 70:
            self.mobs.append(Mob(self, kind, pos))

    def add_fx(self, e):
        self.fx.append(e)

    def particles(self, pos, n, tile=None, color=None, spread=.3, up=False):
        if self.world is None or self.state == 'menu':
            return
        for _ in range(n):
            if len(self.fx) > 350:
                return
            v = [random.uniform(-2, 2), random.uniform(-2, 2), random.uniform(1, 4) if up else random.uniform(0, 3)]
            q = [pos[i] + random.uniform(-spread, spread) for i in range(3)]
            self.fx.append(Particle(self, q, v, tile=tile, color=color or (1, 1, 1), life=random.uniform(.4, .8),
                                    size=.06 if tile is not None else .08))

    def puff(self, pos):
        for _ in range(10):
            v = [random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(.5, 2)]
            q = [pos[0] + random.uniform(-.4, .4), pos[1] + random.uniform(-.4, .4), pos[2] + random.uniform(0, 1)]
            self.fx.append(Particle(self, q, v, color=(.9, .9, .9), life=.8, size=.12, grav=0))

    def light_scale(self, x, y, z):
        w = self.world
        if w is None:
            return 1.
        s, b = w.light_at(int(math.floor(x)), int(math.floor(y)), int(math.floor(z)))
        br = self.settings['brightness'] / 100.
        g = 1 - br * .45
        v = max(((s / 15.) / (4 - 3 * s / 15.)) ** g * self.daylight, ((b / 15.) / (3 - 2 * b / 15.)) ** g)
        if self.handlight and self.player is not None:
            pp = self.player.pos
            h = max(0., 1 - math.dist((x, y, z), (pp[0], pp[1], pp[2] + 1.6)) / 14.) * self.handlight
            v = max(v, h ** 1.5)
        return min(1., v + .025 + br * .05)

    def on_explosion(self, c, r):
        self.sounds.play('explode', c)
        for _ in range(24):
            v = [random.uniform(-4, 4), random.uniform(-4, 4), random.uniform(0, 4)]
            q = [c[i] + random.uniform(-r / 2, r / 2) for i in range(3)]
            g = random.uniform(.4, .8)
            self.fx.append(Particle(self, q, v, color=(g, g, g), life=random.uniform(.6, 1.2), size=.35, grav=-1))
        mult = (.5, .75, 1., 1.5)[self.settings['difficulty']]
        p = self.player
        d = math.dist(c, (p.pos[0], p.pos[1], p.pos[2] + .9))
        if d < r * 4:
            self.shake = max(self.shake, .7 * (1 - d / (r * 4)))
        if d < r * 2:
            p.inv_t = 0.
            p.hurt((1 - d / (r * 2)) * r * 5 * mult, c)
        for m in self.mobs:
            d = math.dist(c, (m.pos[0], m.pos[1], m.pos[2] + m.hh / 2))
            if d < r * 2:
                m.hurt_t = 0.
                m.hurt((1 - d / (r * 2)) * r * 5, c, kb=10.)
        for it in self.items:
            if math.dist(c, it.pos) < r * .7:
                it.gone = True

    def on_player_hurt(self):
        self.sounds.play('hurt')
        self.flash, self.hud_dirty = .6, True
        self.shake = max(self.shake, .25)

    def player_died(self):
        p = self.player
        p.dead, p.vel = True, [0., 0., 0.]
        if self.mode == 'survival':
            stacks = [s for s in p.inv if s] + ([self.cursor] if self.cursor else [])
            for s in stacks:
                self.spawn_item((p.pos[0], p.pos[1], p.pos[2] + 1), s[0], s[1])
            p.inv = [None] * 36
        self.cursor, self.chest_pos, self.sleep_t, self.fade_to = None, None, -1., 0.
        if self.net:
            self.net.chat('%s died' % self.net.name, True)
        self.dead_txt.setText('Your items were dropped where you died.' if self.mode == 'survival' else '')
        self.state = 'dead'
        self.slot_hover(None)
        self.set_mouse_lock(False)
        self.show('dead')
        self.refresh_inv()

    def respawn(self):
        p = self.player
        p.dead, p.hp, p.food, p.air, p.exhaust = False, 20, 20, 10., 0.
        p.vel, p.fall_start, p.inv_t, p.flying = [0., 0., 0.], None, 2., False
        p.pos = list(self.spawn)
        self.state = 'playing'
        self.show(None)
        self.set_mouse_lock(True)
        self.hud_dirty = True
        self.refresh_inv()
        if self.dim != 'over':
            self.travel('over', to_spawn=True)

    def spawn_mobs(self):
        p, w = self.player, self.world
        if p.dead:
            return
        diff = self.settings['difficulty']
        AMBK = ('bird', 'butterfly', 'frog', 'bee', 'ant', 'dragonfly')
        passive = sum(1 for m in self.mobs if not m.d.get('hostile') and m.kind != 'fish' and m.kind not in AMBK)
        amb = sum(1 for m in self.mobs if m.kind in AMBK)
        fish = sum(1 for m in self.mobs if m.kind == 'fish')
        hostile = sum(1 for m in self.mobs if m.d.get('hostile'))
        R = self.settings['render_dist'] * 16
        for _ in range(2):
            r = random.random()
            kind = 'hostile' if r < .4 else ('fish' if r < .52 else ('ambient' if r < .72 else 'passive'))
            if (kind == 'hostile' and (diff == 0 or hostile >= 3 + diff * 3)) or (kind == 'fish' and fish >= 6) or \
                    (kind == 'passive' and passive >= 16) or (kind == 'ambient' and amb >= 18):
                continue
            a, d = random.uniform(0, 2 * math.pi), random.uniform(18, max(19., min(48., R - 6.)))
            x, y = int(math.floor(p.pos[0] + math.cos(a) * d)), int(math.floor(p.pos[1] + math.sin(a) * d))
            if not w.loaded(x, y):
                continue
            top = w.light_top(x, y)
            if top < 2 or top >= H - 4:
                continue
            if kind == 'ambient':
                amb += self.spawn_ambient(x, y, top)
            elif kind == 'fish':
                if FAMILY[w.get(x, y, top + 1)] == WATER and FAMILY[w.get(x, y, top + 2)] == WATER:
                    self.spawn_mob('fish', (x + .5, y + .5, top + 1.2))
                    fish += 1
            elif kind == 'hostile':
                z = random.randint(4, max(4, top - 5)) if (self.daylight > .45 or random.random() < .5) else top + 1
                if not (SOLID[w.get(x, y, z - 1)] and w.get(x, y, z) in (AIR, TALL_GRASS, FERN) and w.get(x, y, z + 1) == AIR):
                    continue
                sk, bl = w.light_at(x, y, z)
                if self.dim == 'silly':
                    self.spawn_mob('gloop' if random.random() < .6 else 'imp', (x + .5, y + .5, z))
                    hostile += 1
                    continue
                if bl > 7 or sk * self.daylight > 7:
                    continue
                r, hb = random.random(), w.gen.biome_at(x, y)[0]
                kind = 'zombie' if r < .35 else ('skeleton' if r < .6 else ('creeper' if r < .82 else 'spider'))
                if hb == DESERT_B and kind == 'zombie':
                    kind = 'mummy'
                elif hb == SNOW_B and random.random() < .3:
                    kind = 'yeti'
                if sk > 10 and random.random() < .08:
                    kind = 'ghost'
                    z += 2
                self.spawn_mob(kind, (x + .5, y + .5, z))
                hostile += 1
            else:
                biome, _ = w.gen.biome_at(x, y)
                if FAMILY[w.get(x, y, top + 1)] == WATER:
                    if biome in (PLAINS_B, FOREST_B, AUTUMN_B, TAIGA_B) and random.random() < .4:
                        z = top + 1
                        while FAMILY[w.get(x, y, z + 1)] == WATER:
                            z += 1
                        if w.get(x, y, z + 1) == AIR:
                            self.spawn_mob('duck', (x + .5, y + .5, z + .3))
                            passive += 1
                    continue
                ground = w.get(x, y, top)
                if ground not in (GRASS, SNOWY_GRASS, SAND, RED_SAND, SNOW, ICE, SILLY_GRASS) or SOLID[w.get(x, y, top + 1)]:
                    continue
                kind = random.choice(BIOME_MOBS[biome])
                if ground == SAND and top <= SEA + 2 and biome != SILLY_B and random.random() < .6:
                    kind = 'turtle'
                for _ in range(random.randint(1, 2 if kind in ('deer', 'fox', 'goat') else 3)):
                    self.spawn_mob(kind, (x + .5 + random.uniform(-1, 1), y + .5 + random.uniform(-1, 1), top + 1.2))
                    passive += 1

    def run_spawners(self):
        p, w = self.player, self.world
        if self.settings['difficulty'] == 0 or p.dead:
            return
        for pos in list(w.spawners):
            if math.dist(pos, p.pos) > 16:
                continue
            self.particles((pos[0] + .5, pos[1] + .5, pos[2] + .5), 3, color=(1, .45, .1), up=True)
            w.spawners[pos] -= 1
            if w.spawners[pos] > 0:
                continue
            w.spawners[pos] = random.randint(5, 12)
            if sum(1 for m in self.mobs if math.dist(m.pos, pos) < 9) >= 4:
                continue
            kind = ('zombie', 'skeleton', 'spider')[(pos[0] * 7 + pos[1] * 13 + pos[2]) % 3]
            for _ in range(random.randint(1, 3)):
                x, y = pos[0] + random.randint(-3, 3), pos[1] + random.randint(-3, 3)
                for z in (pos[2], pos[2] + 1, pos[2] - 1):
                    if w.get(x, y, z) == AIR and w.get(x, y, z + 1) == AIR and SOLID[w.get(x, y, z - 1)]:
                        self.spawn_mob(kind, (x + .5, y + .5, z))
                        self.puff((x + .5, y + .5, z))
                        break

    # ---------------------------------------------------------------- weather
    def cycle_weather(self):
        if self.state != 'playing' or self.typing():
            return
        self.weather = {'clear': 'rain', 'rain': 'thunder', 'thunder': 'clear'}[self.weather]
        self.weather_t = random.uniform(200, 400)
        self.say('Weather: ' + self.weather.capitalize())

    def precip_at(self, x, y, z):
        biome, _ = self.world.gen.biome_at(x, y)
        if biome in (DESERT_B, BADLANDS_B, SILLY_B):
            return None
        return 'snow' if (biome == SNOW_B or z > SEA + 38) else 'rain'

    def weather_step(self, dt):
        p, w = self.player, self.world
        self.weather_t -= dt
        if self.weather_t <= 0 and not (self.net and self.net.role == 'client'):
            if self.weather == 'clear':
                self.weather, self.weather_t = ('thunder' if random.random() < .3 else 'rain'), random.uniform(120, 260)
            else:
                self.weather, self.weather_t = 'clear', random.uniform(300, 700)
        target = 0. if self.dim == 'silly' else {'clear': 0., 'rain': .8, 'thunder': 1.}[self.weather]
        self.rain += max(-dt * .07, min(dt * .07, target - self.rain))
        self.precip_t -= dt
        if self.precip_t <= 0:
            self.precip_t = .3
            self.rebuild_precip()
        now = self.clock.getFrameTime()
        if self.precip_type == 'rain':
            self.precip.setTexOffset(TextureStage.getDefault(), 0, (now * 2.2) % 1.)
        elif self.precip_type == 'snow':
            self.precip.setTexOffset(TextureStage.getDefault(), (math.sin(now * .7) * .15) % 1., (now * .22) % 1.)
        L = .3 + .7 * min(1., self.daylight)
        self.precip.setColorScale(L, L, L, 1)
        if self.weather == 'thunder' and self.rain > .6 and self.dim == 'over' and random.random() < dt / 9.:
            self.lightning()
        self.flash_sky = max(0., self.flash_sky - dt * 2.5)
        if self.bolt is not None:
            self.bolt_t -= dt
            self.bolt.show() if int(self.bolt_t * 30) % 3 else self.bolt.hide()
            if self.bolt_t <= 0:
                self.bolt.removeNode()
                self.bolt = None
        # sound + splashes + snow cover
        vol = 0.
        if self.precip_type == 'rain' and self.rain > .02:
            sk, _ = w.light_at(math.floor(p.pos[0]), math.floor(p.pos[1]), math.floor(p.pos[2] + 1.6))
            vol = self.rain * (1. if sk >= 12 else .3) * self.settings['ambient'] / 100. * .8
            if random.random() < self.rain * 25 * dt:
                x, y = int(math.floor(p.pos[0] + random.uniform(-7, 7))), int(math.floor(p.pos[1] + random.uniform(-7, 7)))
                top = w.light_top(x, y)
                if abs(top - p.pos[2]) < 10:
                    self.fx.append(Particle(self, (x + random.random(), y + random.random(), top + 1.05),
                                            (random.uniform(-.5, .5), random.uniform(-.5, .5), 1.5),
                                            color=(.75, .82, .95), life=.25, size=.04, grav=12))
        if self.rain_snd:
            if vol > .01:
                if self.rain_snd.status() != AudioSound.PLAYING:
                    self.rain_snd.play()
                self.rain_snd.setVolume(vol)
            elif self.rain_snd.status() == AudioSound.PLAYING:
                self.rain_snd.stop()
        if self.precip_type == 'snow' and self.rain > .5 and random.random() < dt * 1.5:
            x, y = int(math.floor(p.pos[0] + random.uniform(-10, 10))), int(math.floor(p.pos[1] + random.uniform(-10, 10)))
            top = w.light_top(x, y)
            if 0 < top < H - 2 and w.get(x, y, top) not in (ICE, SNOW) and OPAQUE[w.get(x, y, top)] and \
                    w.get(x, y, top + 1) == AIR:
                w.set(x, y, top + 1, SNOW_LAYER)

    def rebuild_precip(self):
        self.precip.getChildren().detach()
        p, w = self.player, self.world
        if self.rain < .03 or p is None:
            self.precip_type = None
            return
        bx, by = int(math.floor(p.pos[0])), int(math.floor(p.pos[1]))
        cz = p.pos[2] + 1.6
        self.precip_type = typ = self.precip_at(bx, by, cz)
        if typ is None:
            return
        R = 12
        dx, dy = (a.ravel() for a in np.mgrid[-R:R + 1, -R:R + 1])
        d = np.hypot(dx, dy)
        dx, dy, d = dx[d <= R], dy[d <= R], d[d <= R]
        xs, ys = bx + dx, by + dy
        tops = np.array([w.light_top(int(x), int(y)) for x, y in zip(xs, ys)], np.float32)
        z0 = np.maximum(tops + 1., cz - 10)
        ok = (cz + 12) - z0 >= .5
        if not ok.any():
            return
        xs, ys, z0, d = xs[ok], ys[ok], z0[ok], d[ok]
        ph = ((xs * 7349 + ys * 1931) % 97) / 97.
        alpha = (1 - d / (R + 1)) * np.minimum(1., (d / 2.5) ** 2) * min(1., self.rain * 1.2) * (.55 if typ == 'rain' else .9)
        sc = 3. if typ == 'rain' else 5.
        vs, cs, us = [], [], []
        for k in range(2):
            c = CROSS[k]
            v = np.empty((xs.size, 4, 3), np.float32)
            v[..., 0] = xs[:, None] + c[None, :, 0]
            v[..., 1] = ys[:, None] + c[None, :, 1]
            v[..., 2] = np.where(c[None, :, 2] < .5, z0[:, None], cz + 12)
            uv = np.empty((xs.size, 4, 2), np.float32)
            uv[..., 0] = c[None, :, 0] * 1.5 + ph[:, None]
            uv[..., 1] = v[..., 2] / sc + ph[:, None] * 3
            col = np.ones((xs.size, 4, 4), np.float32)
            col[..., 3] = alpha[:, None]
            vs.append(v), cs.append(col), us.append(uv)
        n = geom_np(np.concatenate(vs), np.concatenate(cs), np.concatenate(us), 'precip')
        n.reparentTo(self.precip)
        n.setTexture(self.rain_tex if typ == 'rain' else self.snow_tex)

    def lightning(self):
        p, w = self.player, self.world
        a, d = random.uniform(0, 2 * math.pi), random.uniform(18, 70)
        x, y = p.pos[0] + math.cos(a) * d, p.pos[1] + math.sin(a) * d
        z = w.light_top(int(math.floor(x)), int(math.floor(y))) + 1
        ls = LineSegs()
        ls.setThickness(3)
        ls.setColor(.92, .95, 1, 1)
        px, py, pz = x, y, z + 70
        ls.moveTo(px, py, pz)
        while pz > z:
            px, py, pz = px + random.uniform(-2.5, 2.5), py + random.uniform(-2.5, 2.5), max(z, pz - random.uniform(3, 8))
            ls.drawTo(px, py, pz)
            if random.random() < .25:
                ls.drawTo(px + random.uniform(-6, 6), py + random.uniform(-6, 6), pz - random.uniform(4, 10))
                ls.moveTo(px, py, pz)
        if self.bolt is not None:
            self.bolt.removeNode()
        self.bolt = self.render.attachNewNode(ls.create())
        self.bolt.setLightOff()
        self.bolt.setFogOff()
        self.bolt_t, self.flash_sky = .4, 1.
        vol = min(1., 30. / d + .25)
        self.taskMgr.doMethodLater(d / 90., lambda t: self.sounds.play('thunder', None, vol, 'ambient'), 'thunder')

    # ---------------------------------------------------------------- nature ambience
    def ambient_step(self, dt):
        p, w = self.player, self.world
        cam = self.camera.getPos(self.render)
        kinds = {}
        for a in self.amb:
            kinds[a[1]] = kinds.get(a[1], 0) + 1
        night = (self.daylight < .45 and self.rain < .3) or self.dim == 'silly'
        if night and kinds.get('fly', 0) < 30 and random.random() < dt * 10:
            x, y = int(math.floor(p.pos[0] + random.uniform(-14, 14))), int(math.floor(p.pos[1] + random.uniform(-14, 14)))
            top = w.light_top(x, y)
            if w.get(x, y, top) in (GRASS, SILLY_GRASS) and abs(top - p.pos[2]) < 12:
                self.add_amb('fly', (x + random.random(), y + random.random(), top + 1 + random.uniform(.3, 2.5)),
                             random.uniform(5, 11))
        if self.daylight > .3 and kinds.get('leaf', 0) < 18 and random.random() < dt * 8:
            x, y = int(math.floor(p.pos[0] + random.uniform(-10, 10))), int(math.floor(p.pos[1] + random.uniform(-10, 10)))
            for z in range(int(cam.z) + 8, int(cam.z) - 4, -1):
                b = w.get(x, y, z)
                if b in LEAF_IDS:
                    if w.get(x, y, z - 1) == AIR:
                        self.add_amb('leaf', (x + random.random(), y + random.random(), z - .05), 9., TEXIDX[b, 1])
                    break
                if SOLID[b]:
                    break
        if kinds.get('ember', 0) < 24:
            for _ in range(4):
                x, y, z = (int(math.floor(cam[i] + random.uniform(-9, 9))) for i in range(3))
                if FAMILY[w.get(x, y, z)] == LAVA and w.get(x, y, z + 1) == AIR and random.random() < .5:
                    self.add_amb('ember', (x + random.random(), y + random.random(), z + 1), random.uniform(1.5, 3))
        if FAMILY[w.get(math.floor(cam.x), math.floor(cam.y), math.floor(cam.z))] == WATER and random.random() < dt * 6:
            d = self.look_dir()
            self.add_amb('bubble', (cam.x + d[0] * 1.5 + random.uniform(-.8, .8), cam.y + d[1] * 1.5 + random.uniform(-.8, .8),
                                    cam.z - .6), 3.)
        t = self.clock.getFrameTime()
        keep = []
        for a in self.amb:
            node, kind, pos, vel, life, ph = a
            a[4] = life = life - dt
            if kind == 'fly':
                vel[0] += random.uniform(-2, 2) * dt
                vel[1] += random.uniform(-2, 2) * dt
                vel[2] += random.uniform(-1.5, 1.5) * dt
                for i in range(3):
                    vel[i] *= max(0., 1 - .8 * dt)
                node.setAlphaScale(max(0., math.sin(t * 2.3 + ph)) * min(1., life))
            elif kind == 'leaf':
                vel[0], vel[1], vel[2] = math.sin(t * 1.3 + ph) * .6 + .3, math.cos(t * 1.1 + ph) * .4, -.7
                node.setR(math.sin(t * 2 + ph) * 40)
            elif kind == 'ember':
                vel[2] = .9
                node.setAlphaScale(min(1., life))
            else:
                vel[2] = 1.2
                if FAMILY[w.get(math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2]))] != WATER:
                    life = 0
            for i in range(3):
                pos[i] += vel[i] * dt
            if kind == 'leaf' and SOLID[w.get(math.floor(pos[0]), math.floor(pos[1]), math.floor(pos[2]))]:
                life = min(life, .5)
                a[4] = life
            if life <= 0 or math.dist(pos, p.pos) > 24:
                node.removeNode()
                continue
            node.setPos(*pos)
            if kind == 'leaf':
                L = self.light_scale(*pos)
                node.setColorScale(L, L, L, min(1., life))
            keep.append(a)
        self.amb = keep

    def add_amb(self, kind, pos, life, tile=None):
        cm = CardMaker('amb')
        s = {'fly': .045, 'leaf': .09, 'ember': .035, 'bubble': .05}[kind]
        cm.setFrame(-s, s, -s, s)
        if tile is not None:
            u0, v0, u1, v1 = tile_uv(tile)
            du, dv = (u1 - u0) / 4, (v1 - v0) / 4
            ox, oy = random.randint(0, 2) * du, random.randint(0, 2) * dv
            cm.setUvRange((u0 + ox, v0 + oy), (u0 + ox + du * 1.5, v0 + oy + dv * 1.5))
        n = self.amb_root.attachNewNode(cm.generate())
        n.setBillboardPointEye()
        n.setPos(*pos)
        if tile is not None:
            n.setTexture(self.atlas)
            n.setTransparency(TransparencyAttrib.MBinary)
        else:
            n.setTextureOff(1)
            n.setLightOff()
            n.setColor(*{'fly': (.8, 1., .35, 1), 'ember': (1., .55, .15, 1), 'bubble': (.75, .85, 1., .7)}[kind])
            n.setTransparency(TransparencyAttrib.MAlpha)
            n.setDepthWrite(False)
            if kind in ('fly', 'ember'):
                n.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OIncomingAlpha,
                                                  ColorBlendAttrib.OOne))
                n.setFogOff()
        self.amb.append([n, kind, list(pos), [0., 0., 0.], life, random.uniform(0, 6.3)])

    # ---------------------------------------------------------------- music
    def gen_music(self):
        try:
            write_music()
            self.music_ready = True
        except Exception as e:
            print('music generation failed:', e)

    def music_step(self, dt):
        if not self.music_ready:
            return
        if not self.music:
            for name, *_ in MUSIC_TRACKS:
                try:
                    self.music[name] = self.loader.loadMusic(Filename.fromOsSpecific(os.path.join(MUSIC_DIR, name + '.wav')))
                except Exception as e:
                    print('music load failed', name, e)
            if not self.music:
                self.music_ready = False
                return
        vol = self.settings['music'] / 100.
        want_menu = self.state == 'menu'
        cur = self.music_cur
        if cur is not None and cur.status() == AudioSound.PLAYING:
            cur.setVolume(vol)
            if want_menu != self.music_menu or vol <= 0 or (not want_menu and self.music_dim != self.dim):
                cur.stop()
                self.music_t = 4.
            return
        self.music_t -= dt
        if self.music_t <= 0 and vol > 0:
            if want_menu:
                names = ['menu']
            else:
                names = [n for n in self.music if n.startswith('silly' if self.dim == 'silly' else 'calm')]
            names = [n for n in names if n in self.music]
            if not names:
                return
            cur = self.music[random.choice(names)]
            cur.setVolume(vol)
            cur.play()
            self.music_cur, self.music_menu, self.music_dim = cur, want_menu, self.dim
            self.music_t = random.uniform(40, 150) if not want_menu else 6.


SRC_MASK = TARGET | _mask([WATER, LAVA])
BIOME_MOBS = {PLAINS_B: ('pig', 'cow', 'sheep', 'chicken', 'rabbit', 'pig', 'cow', 'sheep'), DESERT_B: ('rabbit',),
              SNOW_B: ('penguin', 'goat', 'fox', 'rabbit', 'penguin'), FOREST_B: ('deer', 'fox', 'pig', 'chicken', 'sheep', 'deer'),
              BADLANDS_B: ('rabbit', 'goat'), TAIGA_B: ('deer', 'fox', 'rabbit', 'sheep', 'goat'),
              AUTUMN_B: ('deer', 'fox', 'pig', 'chicken', 'deer')}


def add_to(inv, item, count):
    ms = max_stack(item)
    for s in inv:
        if s and s[0] == item and s[1] < ms:
            take = min(ms - s[1], count)
            s[1] += take
            count -= take
            if not count:
                return 0
    for i in range(len(inv)):
        if inv[i] is None:
            take = min(ms, count)
            inv[i] = [item, take]
            count -= take
            if not count:
                return 0
    return count


# ====================================================================== multiplayer
import socket, struct, queue, base64

NET_PORT, NET_VERSION = 25565, 4
SHIRTS = ((.2, .45, .85), (.85, .25, .25), (.25, .7, .3), (.85, .7, .2), (.6, .3, .8), (.2, .7, .75), (.9, .5, .2))


def _k2s(k):
    return ','.join(str(int(v)) for v in k)


def _s2k(s):
    return tuple(int(v) for v in s.split(','))


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))              # no packets are sent; this only picks the outgoing interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def public_ip(timeout=4):
    """Ask a couple of plain-text echo services for this network's public IP (None if offline)."""
    import urllib.request
    for url in ('https://api.ipify.org', 'https://ifconfig.me/ip', 'https://icanhazip.com'):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                ip = r.read(64).decode().strip()
            if ip.count('.') == 3 or ':' in ip:
                return ip
        except Exception:
            pass
    return None


def upnp_open(port, desc='PyCraft', timeout=3.):
    """Ask the router (UPnP IGD) to forward TCP `port` to this PC. Returns a handle for upnp_close, or None."""
    import urllib.request, re
    from urllib.parse import urljoin
    msg = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\n'
           'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n').encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout)
    locs = []
    try:
        sock.sendto(msg, ('239.255.255.250', 1900))
        while True:
            data = sock.recv(4096).decode(errors='ignore')
            m = re.search(r'(?im)^location:\s*(\S+)', data)
            if m and m.group(1) not in locs:
                locs.append(m.group(1))
    except OSError:
        pass
    finally:
        sock.close()
    me = local_ip()
    for loc in locs:
        try:
            with urllib.request.urlopen(loc, timeout=timeout) as r:
                xml = r.read().decode(errors='ignore')
            for svc in ('WANIPConnection', 'WANPPPConnection'):
                m = re.search(r'<serviceType>(urn:schemas-upnp-org:service:%s:\d)</serviceType>.*?<controlURL>([^<]+)'
                              '</controlURL>' % svc, xml, re.S)
                if not m:
                    continue
                st, ctrl = m.group(1), urljoin(loc, m.group(2))
                args = ('<NewRemoteHost></NewRemoteHost><NewExternalPort>%d</NewExternalPort><NewProtocol>TCP'
                        '</NewProtocol><NewInternalPort>%d</NewInternalPort><NewInternalClient>%s</NewInternalClient>'
                        '<NewEnabled>1</NewEnabled><NewPortMappingDescription>%s</NewPortMappingDescription>'
                        '<NewLeaseDuration>0</NewLeaseDuration>' % (port, port, me, desc))
                if _soap(ctrl, st, 'AddPortMapping', args, timeout):
                    return (ctrl, st, port)
        except Exception:
            pass
    return None


def _soap(ctrl, st, action, args, timeout):
    import urllib.request
    body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:%s xmlns:u="%s">%s</u:%s>'
            '</s:Body></s:Envelope>' % (action, st, args, action)).encode()
    req = urllib.request.Request(ctrl, body, {'Content-Type': 'text/xml; charset="utf-8"',
                                              'SOAPAction': '"%s#%s"' % (st, action)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def upnp_close(handle):
    if handle:
        ctrl, st, port = handle
        _soap(ctrl, st, 'DeletePortMapping', '<NewRemoteHost></NewRemoteHost><NewExternalPort>%d</NewExternalPort>'
                                             '<NewProtocol>TCP</NewProtocol>' % port, 3.)


class Conn:
    """One TCP peer: length-prefixed JSON messages, reader + writer threads."""

    def __init__(self, sock, inbox, cid, start=True):
        self.sock, self.inbox, self.id, self.name = sock, inbox, cid, '?'
        self.out, self.alive = queue.Queue(), True
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        if start:
            self.start()

    def start(self):
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._writer, daemon=True).start()

    def send(self, msg):
        if self.alive:
            self.out.put(msg)

    def _writer(self):
        try:
            while self.alive:
                m = self.out.get()
                if m is None:
                    break
                data = json.dumps(m, separators=(',', ':')).encode()
                self.sock.sendall(struct.pack('>I', len(data)) + data)
        except Exception:
            pass
        self.close()

    def _recv(self, n):
        buf = bytearray()
        while len(buf) < n:
            c = self.sock.recv(min(65536, n - len(buf)))
            if not c:
                raise ConnectionError('closed')
            buf += c
        return bytes(buf)

    def _reader(self):
        try:
            while self.alive:
                n = struct.unpack('>I', self._recv(4))[0]
                if n > 64 * 1024 * 1024:
                    raise ValueError('message too large')
                m = json.loads(self._recv(n).decode())
                if isinstance(m, dict):
                    self.inbox.put((self.id, m))
        except Exception:
            pass
        self.close()
        self.inbox.put((self.id, {'t': '_closed'}))

    def close(self):
        if self.alive:
            self.alive = False
            self.out.put(None)
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass


def build_player_model(name):
    root, limbs = NodePath('player'), []
    shirt = SHIRTS[zlib.crc32(name.encode()) % len(SHIRTS)]
    skin, pants, hair = (.86, .66, .52), (.2, .22, .45), (.28, .18, .1)
    body = root.attachNewNode('body')
    box_np(body, (-.25, -.13, .75), (.25, .13, 1.45), shirt)
    head = root.attachNewNode('head')
    head.setPos(0, 0, 1.45)
    box_np(head, (-.22, -.22, 0), (.22, .22, .44), skin)
    box_np(head, (-.23, -.23, .32), (.23, .23, .46), hair)
    for sx in (-.1, .1):
        box_np(head, (sx - .04, .22, .2), (sx + .04, .235, .26), (.15, .2, .55))
    for sx, s in ((-1, 1), (1, -1)):
        piv = root.attachNewNode('leg')
        piv.setPos(sx * .12, 0, .75)
        box_np(piv, (-.12, -.12, -.75), (.12, .12, 0), pants)
        limbs.append((piv, s))
        piv = root.attachNewNode('arm')
        piv.setPos(sx * .37, 0, 1.43)
        box_np(piv, (-.11, -.11, -.7), (.11, .11, 0), shirt)
        box_np(piv, (-.11, -.11, -.7), (.11, .11, -.45), skin)
        limbs.append((piv, -s))
    body.flattenStrong()
    root.setTextureOff(1)
    tn = TextNode('tag')
    tn.setText(name)
    tn.setAlign(TextNode.ACenter)
    tn.setTextColor(1, 1, 1, 1)
    tn.setCardColor(0, 0, 0, .45)
    tn.setCardAsMargin(.15, .15, .05, .05)
    tag = root.attachNewNode(tn)
    tag.setScale(.28)
    tag.setPos(0, 0, 2.15)
    tag.setBillboardPointEye()
    tag.setLightOff()
    tag.setDepthTest(False)
    tag.setDepthWrite(False)
    tag.setBin('fixed', 50)
    return root, head, limbs


class RemotePlayer:
    """Another player's avatar (interpolated, attackable)."""
    hw, hh = .3, 1.8

    def __init__(self, game, pid, name, pos=(0, 0, 0)):
        self.game, self.id, self.name = game, pid, name
        self.node, self.head, self.limbs = build_player_model(name)
        self.node.reparentTo(game.ent_root)
        self.pos, self.tgt, self.h, self.pitch, self.anim, self.dead, self.flash = list(pos), list(pos), 0., 0., 0., -1., 0.
        self.d = {'hostile': False}

    def set_state(self, p, h, pitch):
        self.tgt, self.h, self.pitch = [float(v) for v in p], float(h), float(pitch)

    def update(self, dt):
        old = list(self.pos)
        f = min(1., 12 * dt)
        for i in range(3):
            self.pos[i] += (self.tgt[i] - self.pos[i]) * f
        if math.dist(self.pos, self.tgt) > 8:
            self.pos = list(self.tgt)
        sp = math.hypot(self.pos[0] - old[0], self.pos[1] - old[1]) / max(dt, 1e-3)
        self.anim += dt * sp * 2.2
        a = math.sin(self.anim) * min(1., sp / 2.) * 40
        for piv, s in self.limbs:
            piv.setP(a * s)
        self.node.setPos(*self.pos)
        self.node.setH(self.h)
        self.head.setP(self.pitch)
        self.flash = max(0., self.flash - dt)
        L = self.game.light_scale(self.pos[0], self.pos[1], self.pos[2] + 1.5)
        self.node.setColorScale(L, L * (1 - self.flash), L * (1 - self.flash), 1)

    def ray(self, o, d):
        return ray_aabb(o, d, (self.pos[0] - .3, self.pos[1] - .3, self.pos[2]), (self.pos[0] + .3, self.pos[1] + .3, self.pos[2] + 1.8))

    def hurt(self, dmg, src=None, kb=0.):
        if self.game.net:
            self.game.net.send_to(self.id, {'t': 'hit', 'target': self.id, 'dmg': dmg,
                                            'src': list(src) if src is not None else None})
        self.flash = .4
        self.game.sounds.play('hurt', self.pos)
        return True

    def destroy(self):
        self.node.removeNode()


class Net:
    def __init__(self, game, role, name):
        self.g, self.role, self.name = game, role, name
        self.inbox, self.conns, self.players = queue.Queue(), {}, {}
        self.my_id, self.next_id, self.pending, self.pos_t, self.env_t, self.srv = 0, 1, [], 0., 0., None

    # ---- setup
    def host(self, port=NET_PORT):
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(('', port))
        self.srv.listen(8)
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self):
        while self.srv is not None:
            try:
                s, addr = self.srv.accept()
            except OSError:
                break
            cid, self.next_id = self.next_id, self.next_id + 1
            c = Conn(s, self.inbox, cid, start=False)       # register before the reader can queue its hello
            self.inbox.put((cid, {'t': '_new', 'conn': c}))
            c.start()

    def connect(self, addr):
        host, _, port = addr.strip().partition(':')
        s = socket.create_connection((host or 'localhost', int(port or NET_PORT)), timeout=6)
        s.settimeout(None)
        self.conns[0] = Conn(s, self.inbox, 0)
        self.conns[0].send({'t': 'hello', 'name': self.name, 'v': NET_VERSION, 'pw': self.g.settings.get('password', '')})

    def close(self):
        upnp_close(getattr(self, 'upnp', None))
        if self.srv is not None:
            srv, self.srv = self.srv, None
            try:
                srv.close()
            except OSError:
                pass
        for c in list(self.conns.values()):
            c.close()
        for p in self.players.values():
            p.destroy()
        self.conns, self.players = {}, {}

    # ---- sending
    def send_to(self, pid, msg):
        if self.role == 'client':
            self.conns[0].send(msg)
        elif pid in self.conns:
            self.conns[pid].send(msg)

    def broadcast(self, msg, exclude=None):
        for cid, c in list(self.conns.items()):
            if cid != exclude:
                c.send(msg)

    def on_local_set(self, x, y, z, b):
        self.pending.append([x, y, z, b])

    def chat(self, text, system=False):
        msg = {'t': 'chat', 'name': '' if system else self.name, 'msg': text[:200]}
        if self.role == 'host':
            self.broadcast(msg)
            self.g.chat_show(msg['name'], msg['msg'])
        else:
            self.conns[0].send(msg)

    def chest_changed(self, pos):
        inv = self.g.world.chest_inv(pos)
        msg = {'t': 'chest' if self.role == 'host' else 'chest_set', 'pos': _k2s(pos), 'inv': inv}
        self.broadcast(msg) if self.role == 'host' else self.conns[0].send(msg)

    def player_count(self):
        return len(self.players) + 1

    # ---- per frame
    def step(self, dt):
        g = self.g
        for _ in range(400):
            try:
                cid, m = self.inbox.get_nowait()
            except queue.Empty:
                break
            try:
                (self.host_msg if self.role == 'host' else self.client_msg)(cid, m)
            except Exception as e:
                print('net message error', m.get('t'), e)
        if self.role == 'client' and 0 not in self.conns:
            return
        w, p = g.world, g.player
        if p is None or w is None or g.state in ('menu', 'loading'):
            return
        if self.pending:
            msg = {'t': 'sets', 'b': self.pending}
            self.pending = []
            self.broadcast(msg) if self.role == 'host' else self.conns[0].send(msg)
        self.pos_t -= dt
        if self.pos_t <= 0:
            self.pos_t = 1 / 15.
            st = {'t': 'pos', 'id': self.my_id, 'p': [round(v, 3) for v in p.pos], 'h': round(p.h, 1),
                  'pi': round(p.p, 1)}
            self.broadcast(st) if self.role == 'host' else self.conns[0].send(st)
        if self.role == 'host':
            self.env_t -= dt
            if self.env_t <= 0:
                self.env_t = 2.
                self.broadcast({'t': 'env', 'time': g.time_of_day, 'weather': g.weather, 'rain': g.rain})
        for rp in self.players.values():
            rp.update(dt)

    def welcome(self, c):
        g, w = self.g, self.g.world
        chunks = {_k2s(k): base64.b64encode(v).decode() for k, v in w.save_chunks().items()}
        c.send({'t': 'welcome', 'id': c.id, 'seed': w.seed, 'time': g.time_of_day, 'weather': g.weather,
                'spawn': list(g.spawn[:2]), 'chunks': chunks, 'chests': {_k2s(k): v for k, v in w.chests.items()},
                'players': [{'id': 0, 'name': self.name, 'p': list(g.player.pos)}] +
                           [{'id': rp.id, 'name': rp.name, 'p': rp.pos} for rp in self.players.values()]})

    def apply_sets(self, lst, remote):
        w = self.g.world
        for x, y, z, b in lst:
            x, y, z, b = int(x), int(y), int(z), int(b)
            if not (0 <= z < H and (b == AIR or b in BDEF)):
                continue
            if remote:
                w.remote_set(x, y, z, b)
            else:
                w.ensure_chunk((x >> 4, y >> 4))
                w.set(x, y, z, b)

    def host_msg(self, cid, m):
        g, t = self.g, m.get('t')
        c = self.conns.get(cid)
        if t == '_new':
            self.conns[cid] = m['conn']
        elif t == 'hello' and c is not None:
            if m.get('v') != NET_VERSION:
                c.send({'t': 'kick', 'why': 'Different PyCraft version'})
                return
            if g.settings.get('password', '') and m.get('pw') != g.settings.get('password', ''):
                c.send({'t': 'kick', 'why': 'Wrong server password'})
                return
            c.name = str(m.get('name', 'Player'))[:16] or 'Player'
            self.welcome(c)
            self.broadcast({'t': 'join', 'id': cid, 'name': c.name}, exclude=cid)
            self.players[cid] = RemotePlayer(g, cid, c.name, g.spawn[:2] + (60,))
            self.chat('%s joined the game' % c.name, True)
        elif t == 'pos' and cid in self.players:
            self.players[cid].set_state(m['p'], m['h'], m['pi'])
            m['id'] = cid
            self.broadcast(m, exclude=cid)
        elif t in ('sets', 'set'):
            self.apply_sets(m['b'] if t == 'sets' else [[m['x'], m['y'], m['z'], m['b']]], False)
        elif t == 'chat':
            name = c.name if c else '?'
            self.broadcast({'t': 'chat', 'name': name, 'msg': str(m.get('msg', ''))[:200]})
            g.chat_show(name, str(m.get('msg', ''))[:200])
        elif t == 'hit':
            if m.get('target') == 0:
                g.player.hurt(float(m.get('dmg', 1)), m.get('src'))
            elif m.get('target') in self.conns:
                self.conns[m['target']].send(m)
        elif t == 'chest_get':
            c.send({'t': 'chest', 'pos': m['pos'], 'inv': g.world.chest_inv(_s2k(m['pos']))})
        elif t == 'chest_set':
            pos = _s2k(m['pos'])
            g.world.chests[pos] = m['inv']
            self.broadcast({'t': 'chest', 'pos': m['pos'], 'inv': m['inv']}, exclude=cid)
            if g.chest_pos == pos:
                g.refresh_inv()
        elif t == 'prime':
            pos = _s2k(m['pos'])
            g.world.ensure_chunk((pos[0] >> 4, pos[1] >> 4))
            if g.world.get(*pos) == TNT:
                g.world.set(*pos, AIR)
                g.add_fx(PrimedTNT(g, *pos))
        elif t == '_closed':
            self.conns.pop(cid, None)
            rp = self.players.pop(cid, None)
            if rp:
                rp.destroy()
                self.broadcast({'t': 'leave', 'id': cid})
                self.chat('%s left the game' % rp.name, True)

    def client_msg(self, cid, m):
        g, t = self.g, m.get('t')
        if t == 'welcome':
            self.my_id = m['id']
            data = dict(seed=m['seed'], time=m['time'], weather=m['weather'], spawn=m['spawn'], player=None,
                        chunks={_s2k(k): base64.b64decode(v) for k, v in m['chunks'].items()},
                        chests={_s2k(k): v for k, v in m['chests'].items()})
            g.start_world(m['seed'], 'survival', data)
            g.world.net, g.world.no_physics = self, True
            for pl in m['players']:
                self.players[pl['id']] = RemotePlayer(g, pl['id'], pl['name'], pl['p'])
            g.adv('mp')
        elif t == 'join':
            self.players[m['id']] = RemotePlayer(g, m['id'], m['name'], g.spawn[:2] + (60,))
        elif t == 'leave':
            rp = self.players.pop(m['id'], None)
            if rp:
                rp.destroy()
        elif t == 'pos' and m.get('id') in self.players:
            self.players[m['id']].set_state(m['p'], m['h'], m['pi'])
        elif t == 'sets' and g.world is not None:
            self.apply_sets(m['b'], True)
        elif t == 'env':
            g.time_of_day, g.weather = float(m['time']), m['weather']
        elif t == 'chat':
            g.chat_show(m.get('name', ''), m.get('msg', ''))
        elif t == 'hit' and g.player is not None:
            g.player.hurt(float(m.get('dmg', 1)), m.get('src'))
        elif t == 'chest' and g.world is not None:
            pos = _s2k(m['pos'])
            g.world.chests[pos] = m['inv']
            if g.chest_pos == pos:
                g.refresh_inv()
        elif t == 'kick':
            g.net_lost('Kicked: ' + m.get('why', ''))
        elif t == '_closed':
            g.net_lost('Disconnected from the host')


# ====================================================================== Discord rich presence (optional)
class Discord:
    """Uses the optional 'pypresence' package and a Discord application ID (see settings.json)."""

    def __init__(self, game):
        self.g, self.status, self.q, self.last = game, 'off', queue.Queue(), None
        self.start = int(time.time())
        app = str(game.settings.get('discord_app_id', '')).strip()
        if not game.settings.get('discord', True):
            self.status = 'disabled in settings'
        elif not app:
            self.status = 'no application ID set'
        else:
            threading.Thread(target=self._run, args=(app,), daemon=True).start()
            self.status = 'connecting'

    def _run(self, app):
        try:
            import asyncio
            asyncio.set_event_loop(asyncio.new_event_loop())
            from pypresence import Presence
        except ImportError:
            self.status = "'pypresence' not installed"
            return
        try:
            rpc = Presence(app)
            rpc.connect()
            self.status = 'connected'
        except Exception as e:
            self.status = 'Discord not running (%s)' % type(e).__name__
            return
        while True:
            kw = self.q.get()
            if kw is None:
                break
            try:
                rpc.update(start=self.start, large_image='logo', large_text='PyCraft', **kw)
            except Exception as e:
                self.status = 'update failed (%s)' % type(e).__name__
        try:
            rpc.close()
        except Exception:
            pass

    def tick(self):
        if self.status != 'connected':
            return
        g = self.g
        if g.state == 'menu' or g.world is None or g.player is None:
            kw = dict(details='In the main menu', state='Choosing a world')
        else:
            b, _ = g.world.gen.biome_at(g.player.pos[0], g.player.pos[1])
            w = {'thunder': ' - Thunderstorm', 'rain': ' - Raining'}.get(g.weather, '')
            kw = dict(details='%s - %s%s' % (g.mode.capitalize(), BIOME_NAMES[b], w))
            if g.net:
                kw.update(state='Multiplayer', party_size=[g.net.player_count(), 8])
            else:
                kw['state'] = 'Singleplayer'
        if kw != self.last:
            self.last = kw
            self.q.put(kw)


# ====================================================================== advancements
ADVANCEMENTS = [('wood', 'Getting Wood', 'Collect a log'), ('bench', 'Benchmarking', 'Craft a crafting table'),
                ('pick', 'Time to Mine!', 'Get a pickaxe'), ('iron', 'Acquire Hardware', 'Get an iron ingot'),
                ('diamond', 'Diamonds!', 'Get a diamond'), ('torch', 'Let There Be Light', 'Place a torch'),
                ('eat', 'Yummy', 'Eat something'), ('kill', 'Monster Hunter', 'Defeat a hostile mob'),
                ('bow', 'Sharpshooter', 'Hit a mob with an arrow'), ('farm', 'Farmer', 'Harvest ripe wheat'),
                ('fish', "Gone Fishin'", 'Get a raw fish'), ('bed', 'Sweet Dreams', 'Sleep through the night'),
                ('loot', 'Treasure Hunter', 'Open a dungeon chest'), ('sky', 'Sky High', 'Stand above y=74'),
                ('storm', 'Stormchaser', 'Witness a thunderstorm'), ('mp', 'Not Alone', 'Play multiplayer')]
ADV_NAMES = {k: (t, d) for k, t, d in ADVANCEMENTS}


# ====================================================================== game extensions: chat, minimap, advancements, multiplayer UI
def _build_extras(self):
    a = self.aspect2d
    # chat
    self.chat_lines, self.chat_open = [], False
    self.chat_txt = OnscreenText(parent=self.a2dBottomLeft, text='', pos=(.04, .62), scale=.042, fg=(1, 1, 1, 1),
                                 align=TextNode.ALeft, shadow=(0, 0, 0, 1), mayChange=True)
    self.chat_entry = DirectEntry(parent=self.a2dBottomLeft, scale=.045, width=34, pos=(.04, 0, .52), numLines=1,
                                  frameColor=(0, 0, 0, .6), text_fg=(1, 1, 1, 1), initialText='',
                                  command=self.send_chat, focus=0)
    self.chat_entry.hide()
    # minimap
    self.map_on, self.map_t = True, 0.
    self.map_tex = Texture()
    self.map_tex.setup2dTexture(128, 128, Texture.TUnsignedByte, Texture.FRgb8)
    self.map_tex.setMagfilter(SamplerState.FTNearest)
    self.map_frame = DirectFrame(parent=self.a2dTopRight, frameColor=(.1, .1, .1, .85),
                                 frameSize=(-.48, -.02, -.48, -.02))
    self.map_card = make_card(self.map_frame, self.map_tex, .44, .44, (-.25, -.25))
    self.map_lbl = OnscreenText(parent=self.map_frame, text='', pos=(-.25, -.52), scale=.035, fg=(1, 1, 1, 1),
                                shadow=(0, 0, 0, 1), mayChange=True)
    self.map_frame.hide()
    self.block_col = np.zeros((256, 3), np.float32)
    names = {v: k for k, v in TILE.items()}
    for b in BDEF:
        img = self.tile_imgs[names[int(TEXIDX_FANCY[b, 0])]].astype(np.float32)
        m = img[..., 3] > 0
        self.block_col[b] = img[m, :3].mean(0) if m.any() else (128, 128, 128)
    # advancement toast + screen
    self.adv_done, self.toast_q, self.toast_t, self.adv_poll_t = set(), [], 0., 0.
    self.toast = DirectFrame(parent=self.a2dTopRight, frameColor=(.15, .15, .2, .92), frameSize=(-1.25, -.52, -.2, -.02))
    self.toast_t1 = OnscreenText(parent=self.toast, text='Advancement Made!', pos=(-1.22, -.08), scale=.04,
                                 fg=(1, .85, .2, 1), align=TextNode.ALeft, mayChange=True)
    self.toast_t2 = OnscreenText(parent=self.toast, text='', pos=(-1.22, -.15), scale=.045, fg=(1, 1, 1, 1),
                                 align=TextNode.ALeft, mayChange=True)
    self.toast.hide()
    self.ui_adv = DirectFrame(parent=a, frameColor=(0, 0, 0, .75), frameSize=(-1.3, 1.3, -.9, .9))
    self.text(self.ui_adv, 'Advancements', (0, .75), .08)
    self.adv_rows = []
    for i, (k, t, d) in enumerate(ADVANCEMENTS):
        x, y = -1.22 + (i // 9) * .84, .58 - (i % 9) * .14
        self.adv_rows.append((k, self.text(self.ui_adv, '', (x, y), .045, align=TextNode.ALeft),
                              self.text(self.ui_adv, d, (x + .04, y - .05), .032, (.75, .75, .75, 1), TextNode.ALeft)))
    self.button(self.ui_adv, 'Back', (0, -.78), lambda: self.show('pause'))
    self.ui_adv.hide()
    # multiplayer screen
    self.ui_mp = DirectFrame(parent=a, frameColor=(0, 0, 0, .7), frameSize=(-1, 1, -.75, .75))
    self.text(self.ui_mp, 'Multiplayer', (0, .6), .08)
    self.text(self.ui_mp, 'Your name', (-.5, .42), .04, (.8, .8, .8, 1), TextNode.ALeft)
    self.mp_name = DirectEntry(parent=self.ui_mp, scale=.05, width=12, pos=(-.5, 0, .33), numLines=1,
                               frameColor=(0, 0, 0, .85), text_fg=(1, 1, 1, 1),
                               initialText=self.settings.get('name', 'Player%d' % random.randint(10, 99)))
    self.text(self.ui_mp, 'Server address (host:port)', (-.5, .2), .04, (.8, .8, .8, 1), TextNode.ALeft)
    self.mp_addr = DirectEntry(parent=self.ui_mp, scale=.05, width=20, pos=(-.5, 0, .11), numLines=1,
                               frameColor=(0, 0, 0, .85), text_fg=(1, 1, 1, 1),
                               initialText=self.settings.get('last_server', 'localhost'))
    self.text(self.ui_mp, 'Password (optional - also used when you host)', (-.5, .02), .035, (.8, .8, .8, 1), TextNode.ALeft)
    self.mp_pw = DirectEntry(parent=self.ui_mp, scale=.05, width=12, pos=(-.5, 0, -.07), numLines=1, obscured=1,
                             frameColor=(0, 0, 0, .85), text_fg=(1, 1, 1, 1), initialText=self.settings.get('password', ''))
    self.button(self.ui_mp, 'Join Server', (0, -.2), self.mp_join)
    self.mp_status = self.text(self.ui_mp, 'To host: load a world, press Esc, then "Open to LAN".', (0, -.3), .036,
                               (.9, .9, .6, 1))
    self.text(self.ui_mp, 'Hosting tries to open port %d on your router automatically (UPnP) and shows your public\n'
                          'address. For a 24/7 server run:  python3 pycraft.py --server  on any Linux machine.' % NET_PORT,
              (0, -.42), .03, (.7, .7, .7, 1))
    self.button(self.ui_mp, 'Back', (0, -.6), lambda: self.show('menu'))
    self.ui_mp.hide()


def _typing_any(self):
    return (not self.ui_cre.isHidden() and self.cre_search.guiItem.getFocus()) or self.chat_open or \
        (not self.ui_mp.isHidden())


# ---- chat
def _open_chat(self, prefix=''):
    if self.state != 'playing' or self.chat_open or self.typing():
        return
    self.chat_open = True
    self.chat_entry.show()
    self.chat_entry.enterText('')
    self.chat_entry['focus'] = 1
    self.chat_entry.guiItem.setFocus(True)
    self.set_mouse_lock(False)
    self.taskMgr.doMethodLater(.02, lambda t: self.chat_entry.enterText(prefix), 'chatclear')


def _close_chat(self):
    self.chat_open = False
    self.chat_entry.guiItem.setFocus(False)
    self.chat_entry.hide()
    if self.state == 'playing':
        self.set_mouse_lock(True)


def _send_chat(self, text):
    text = text.strip()
    self.close_chat()
    if not text:
        return
    if text.startswith('/'):
        self.run_command(text[1:])
    elif self.net:
        self.net.chat(text)
    else:
        self.chat_show(self.settings.get('name', 'Player'), text)


def _chat_show(self, name, msg):
    self.chat_lines.append((('<%s> ' % name) if name else '', msg, self.clock.getFrameTime()))
    self.chat_lines = self.chat_lines[-8:]


def _chat_step(self, dt):
    now = self.clock.getFrameTime()
    lines = [n + m for n, m, t in self.chat_lines if self.chat_open or now - t < 10]
    self.chat_txt.setText('\n'.join(lines[-8:]))
    self.chat_txt.setPos(.04, .62 + .045 * (len(lines[-8:]) - 1))


def _run_command(self, cmd):
    p, w = self.player, self.world
    parts = cmd.split()
    if not parts or p is None:
        return
    c, args, host = parts[0].lower(), parts[1:], not (self.net and self.net.role == 'client')
    say = lambda m: self.chat_show('', m)
    try:
        if c == 'help':
            say('/time day|night|<hour>  /weather clear|rain|thunder  /tp x y z  /give <item> [n]')
            say('/gamemode survival|creative  /seed  /spawn  /map   (T = chat, M = minimap)')
        elif c == 'time' and host:
            v = args[0] if args else 'day'
            hours = {'day': 7, 'noon': 12, 'sunset': 18, 'night': 21, 'midnight': 0}.get(v)
            hours = float(v) if hours is None else hours
            self.time_of_day = ((hours - 6) / 24.) % 1.
            say('Time set to %s' % v)
        elif c == 'weather' and host and args and args[0] in ('clear', 'rain', 'thunder'):
            self.weather, self.weather_t = args[0], random.uniform(200, 400)
            say('Weather set to ' + args[0])
        elif c == 'tp' and len(args) == 3:
            p.pos, p.vel, p.fall_start = [float(a) for a in args], [0., 0., 0.], None
            say('Teleported')
        elif c == 'give' and args:
            n = int(args[-1]) if len(args) > 1 and args[-1].isdigit() else 1
            q = ' '.join(args[:-1] if len(args) > 1 and args[-1].isdigit() else args).lower().replace('_', ' ')
            hits = [i for i in CREATIVE_ITEMS if item_name(i).lower() == q] or \
                   [i for i in CREATIVE_ITEMS if q in item_name(i).lower()]
            if not hits:
                say('Unknown item: ' + q)
            elif self.mode != 'creative' and self.net:
                say('/give needs creative mode in multiplayer')
            else:
                left = p.add_item(hits[0], n)
                self.refresh_inv()
                say('Gave %d %s' % (n - left, item_name(hits[0])))
        elif c == 'gamemode' and args and args[0] in ('survival', 'creative') and args[0] != self.mode:
            self.toggle_mode()
        elif c == 'seed':
            say('Seed: %s' % w.seed)
        elif c == 'spawn':
            p.pos, p.vel = list(self.spawn), [0., 0., 0.]
        elif c == 'map':
            self.toggle_minimap()
        else:
            say('Unknown or host-only command. Try /help')
    except (ValueError, IndexError):
        say('Bad arguments. Try /help')


# ---- minimap
def _toggle_minimap(self):
    if self.typing():
        return
    self.map_on = not self.map_on
    self.say('Minimap ' + ('ON' if self.map_on else 'OFF'))


def _chunk_map(self, ch):
    if ch.mapimg is None:
        b = ch.blocks
        m = (b != AIR) & ~PLANT[b]
        top = H - 1 - np.argmax(m[:, :, ::-1], 2)
        I, J = np.indices((16, 16))
        tb = b[I, J, top]
        shade = .8 + np.clip((top - SEA) / 60., -.3, .3)
        dzx = np.diff(top, axis=1, prepend=top[:, :1])
        col = self.block_col[tb] * (shade + np.clip(dzx, -2, 2) * .06)[..., None]
        col[FAMILY[tb] == WATER] *= .85
        ch.mapimg = np.clip(col, 0, 255).astype(np.uint8)
    return ch.mapimg


def _minimap_step(self, dt):
    show = self.map_on and self.state in ('playing', 'paused', 'inventory') and not self.hud_hidden
    self.map_frame.show() if show else self.map_frame.hide()
    self.map_t -= dt
    if not show or self.map_t > 0:
        return
    self.map_t = .5
    p, w = self.player, self.world
    bx, by = int(math.floor(p.pos[0])), int(math.floor(p.pos[1]))
    pcx, pcy = bx >> 4, by >> 4
    canvas = np.zeros((144, 144, 3), np.uint8)
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            ch = w.chunks.get((pcx + dx, pcy + dy))
            if ch is not None:
                r, c = (4 - dy) * 16, (dx + 4) * 16
                canvas[r:r + 16, c:c + 16] = self.chunk_map(ch).transpose(1, 0, 2)[::-1]
    ox, oy = (pcx - 4) * 16, (pcy + 4) * 16 + 15

    def px(x, y):
        return oy - int(math.floor(y)), int(math.floor(x)) - ox
    if self.net:
        for rp in self.net.players.values():
            r, c = px(rp.pos[0], rp.pos[1])
            if 1 <= r < 143 and 1 <= c < 143:
                canvas[r - 1:r + 2, c - 1:c + 2] = (60, 160, 255)
    r, c = px(p.pos[0], p.pos[1])
    hr = math.radians(p.h)
    for k in range(5):
        rr, cc = r - int(round(math.cos(hr) * k)), c - int(round(math.sin(hr) * k))
        if 0 <= rr < 144 and 0 <= cc < 144:
            canvas[rr, cc] = (255, 255, 255)
    canvas[max(0, r - 1):r + 2, max(0, c - 1):c + 2] = (255, 40, 40)
    r0, c0 = min(max(0, r - 64), 16), min(max(0, c - 64), 16)
    img = np.ascontiguousarray(canvas[r0:r0 + 128, c0:c0 + 128][::-1])
    self.map_tex.setRamImageAs(img.tobytes(), 'RGB')
    self.map_lbl.setText('%d, %d, %d' % (bx, by, int(p.pos[2])))


# ---- advancements
def _adv(self, key):
    if key in self.adv_done or self.state == 'menu' or self.world is None:
        return
    self.adv_done.add(key)
    self.toast_q.append(ADV_NAMES[key][0])


def _adv_step(self, dt):
    self.adv_poll_t -= dt
    p = self.player
    if self.adv_poll_t <= 0 and p is not None and not p.dead:
        self.adv_poll_t = 1.
        have = {s[0] for s in p.inv if s}
        for key, items in (('wood', (LOG, BIRCH_LOG, SPRUCE_LOG)), ('bench', (CRAFTING,)), ('iron', (IRON_INGOT,)),
                           ('diamond', (DIAMOND,)), ('fish', (RAW_FISH,)), ('sillium', (SILLIUM_INGOT,)),
                           ('pick', tuple(i for i, tt in TOOLS.items() if tt[0] == 'pickaxe'))):
            if have & set(items):
                self.adv(key)
        if p.on_ground and p.pos[2] > 74:
            self.adv('sky')
        if self.weather == 'thunder' and self.rain > .6:
            self.adv('storm')
    if self.toast_t > 0:
        self.toast_t -= dt
        k = min(1., self.toast_t, 4. - self.toast_t) * 4
        self.toast.setZ(.25 * (1 - min(1., k)))
        if self.toast_t <= 0:
            self.toast.hide()
    elif self.toast_q:
        self.toast_t2.setText(self.toast_q.pop(0))
        self.toast_t = 4.
        self.toast.show()
        self.sounds.play('pop')
        self.sounds.play('chirp', None, .5)


def _show_advancements(self):
    for k, t1, t2 in self.adv_rows:
        done = k in self.adv_done
        t1.setText(('[x] ' if done else '[ ] ') + ADV_NAMES[k][0])
        t1.setFg((1, .85, .2, 1) if done else (.6, .6, .6, 1))
    self.show('adv')


# ---- multiplayer UI
def _mp_join(self):
    name = self.mp_name.get().strip()[:16] or 'Player'
    addr = self.mp_addr.get().strip() or 'localhost'
    self.settings['name'], self.settings['last_server'] = name, addr
    self.save_settings()
    self.settings['password'] = self.mp_pw.get()
    self.mp_status.setText('Connecting to %s ...' % addr)
    self.graphicsEngine.renderFrame()
    net = Net(self, 'client', name)
    try:
        net.connect(addr)
    except Exception as e:
        self.mp_status.setText('Could not connect: %s' % e)
        return
    self.net = net
    self.mp_status.setText('Connected - downloading world...')


def _open_to_lan(self):
    if self.net or self.world is None or self.state != 'paused':
        return
    name = self.settings.get('name', 'Host')
    net = Net(self, 'host', name)
    try:
        net.host(NET_PORT)
    except OSError as e:
        self.say('Could not host: %s' % e)
        return
    self.net = self.world.net = net
    self.btn_lan['text'] = 'Hosting on %s:%d' % (local_ip(), NET_PORT)
    self.chat_show('', 'Hosting! LAN players join at %s:%d%s' % (
        local_ip(), NET_PORT, '  (password protected)' if self.settings.get('password') else ''))
    self.chat_show('', 'Opening port %d on your router and looking up your public address...' % NET_PORT)

    def go_public():                                    # background: UPnP + public IP, reported in chat
        h = upnp_open(NET_PORT)
        net.upnp = h
        ip = public_ip()
        if self.net is not net:
            upnp_close(h)
            return
        if ip and h:
            net.public = '%s:%d' % (ip, NET_PORT)
            self.chat_show('', 'Public server is up! Internet players join at  %s' % net.public)
        elif ip:
            self.chat_show('', 'Your router did not allow automatic port forwarding (UPnP off?).')
            self.chat_show('', 'Forward TCP %d to %s manually, then friends join at  %s:%d' % (NET_PORT, local_ip(), ip, NET_PORT))
        else:
            self.chat_show('', 'Could not reach the internet to find your public IP - LAN only.')
    threading.Thread(target=go_public, daemon=True).start()
    self.adv('mp')


def _net_lost(self, why):
    if self.net:
        self.net.close()
        self.net = None
    if self.state != 'menu':
        self.start_menu()
    self.show('mp')
    self.mp_status.setText(why)


for _nm, _f in (('build_extras', _build_extras), ('typing', _typing_any), ('open_chat', _open_chat),
                ('close_chat', _close_chat), ('send_chat', _send_chat), ('chat_show', _chat_show),
                ('chat_step', _chat_step), ('run_command', _run_command), ('toggle_minimap', _toggle_minimap),
                ('chunk_map', _chunk_map), ('minimap_step', _minimap_step), ('adv', _adv), ('adv_step', _adv_step),
                ('show_advancements', _show_advancements), ('mp_join', _mp_join), ('open_to_lan', _open_to_lan),
                ('net_lost', _net_lost)):
    setattr(Game, _nm, _f)



# ====================================================================== v4: portals, dimensions, help
HELP_PAGES = [
    ('Controls', 'WASD move    Space jump    Ctrl sprint    Shift sneak / dismount\n'
                 'Mouse look    Left click break / attack    Right click place / use / eat / ride\n'
                 'Middle click pick block    1-9 or wheel hotbar    E inventory    Q drop item\n'
                 'T chat    / command    M minimap    G survival/creative    F fly (creative)\n'
                 'F1 hide HUD    F2 screenshot    F3 debug info    F4 cycle weather    F11 fullscreen\n\n'
                 'Double-tap Space in creative to fly. Slabs can be walked up without jumping.\n'
                 'Two slabs of the same kind stacked turn into a full block.'),
    ('Multiplayer - hosting', '1. Load or create a world and press Esc.\n'
                              '2. Click "Open to LAN / Host". LAN friends join with the address shown in chat.\n'
                              '3. PyCraft also asks your router to open port 25565 (UPnP) and shows your PUBLIC\n'
                              '   address in chat - give that to friends on other networks.\n'
                              '4. Set a password in Multiplayer > Password before hosting a public server.\n\n'
                              'If chat says UPnP was refused: forward TCP 25565 to this PC in your router, and allow\n'
                              'Python through the firewall (Windows asks; tick Private AND Public).\n\n'
                              'Dedicated 24/7 server on Linux (no screen needed):\n'
                              '   python3 pycraft.py --server --password <pw>\n'
                              'Options: --port --world --seed --max-players --no-upnp.  See README.md.'),
    ('Multiplayer - joining', 'Main menu > Multiplayer. Type your name and the host address (host:port), then Join.\n\n'
                              'Shared between players: blocks, chests, time, weather, chat, PvP, deaths.\n'
                              'Per-player for now: mobs and dropped items.\n'
                              'Sillyland travel is single-player only (portals tell you so in multiplayer).\n\n'
                              'Troubleshooting:\n'
                              ' - "Could not connect": check the address, that the host clicked Open to LAN,\n'
                              '   and the host\'s firewall / port forwarding.\n'
                              ' - "Different PyCraft version": everyone needs the same pycraft.py file.'),
    ('Discord status', 'Shows "Survival - Forest", party size and play time on your Discord profile.\n\n'
                       '1. pip install pypresence\n'
                       '2. Open discord.com/developers/applications, click New Application, name it PyCraft.\n'
                       '3. Copy the Application ID.\n'
                       '4. Edit  %s\n'
                       '   and set  "discord_app_id": "<the id>"\n'
                       '5. Optional: Rich Presence > Art Assets > upload an image named  logo\n'
                       '6. Restart PyCraft with Discord open. Settings shows the connection status.' % SETTINGS_PATH),
    ('Sillyland portal', 'Build a vertical 5x5 frame:\n'
                         '   S C C C S        S = Sand (the 4 corners)\n'
                         '   C . . . C        C = Cobblestone (the edges)\n'
                         '   C . . . C        . = empty (3x3 inside)\n'
                         '   C . . . C\n'
                         '   S C C C S\n'
                         'Then empty a Lava Bucket into the middle. Stand in the portal for 2 seconds.\n'
                         'Ruined portals in the overworld have a lava pool next to them - repair the frame!\n\n'
                         'Sillyland: pink hills, floating islands, giant mushrooms, jelly blocks (bouncy),\n'
                         'Gloops, Imps, Floaties and rideable Hoppers. Mine Sillium Ore with an iron pickaxe.'),
    ('Gear & mounts', 'Weapons: Iron/Sillium Spear (long reach), Battle Axe (huge hits, slow), Dagger (fast).\n'
                      'Sillium tools mine fastest. Sillium Blade = best sword.\n'
                      'Slingshot: fires Pebbles (pick them up off the ground).\n'
                      'Grappling Hook: right-click a block up to 32 away to zip to it (Shift lets go).\n'
                      'Paraglider: hold it, jump off something and hold Space to glide - no fall damage.\n'
                      'Silly Berry: eat for super jumps for 30 seconds.\n\n'
                      'Mounts: right-click a Horse (overworld) or Hopper (Sillyland) while holding a Saddle,\n'
                      'then right-click it to ride. WASD steers, Space jumps, Ctrl gallops, Shift gets off.'),
    ('Commands & tips', '/give <item> [n]   /time day|night|<hour>   /weather clear|rain|thunder\n'
                        '/tp x y z   /gamemode survival|creative   /seed   /spawn   /map   /help\n\n'
                        'Tips: torches stop monsters spawning. Beds skip the night and set your spawn.\n'
                        'Wolves are peaceful until you hit them. Lighthouses guide you to the coast.\n'
                        'Dungeons have spawners; mineshafts have chests. Sky islands hide good loot.\n'
                        'Creative inventory has tabs and a search box. F3 shows biome and light levels.'),
]


def _build_help(self):
    a = self.aspect2d
    self.ui_help = DirectFrame(parent=a, frameColor=(0, 0, 0, .82), frameSize=(-1.45, 1.45, -.92, .92))
    self.help_title = self.text(self.ui_help, '', (0, .78), .07, (1, .9, .4, 1))
    self.help_body = OnscreenText(parent=self.ui_help, text='', pos=(-1.35, .62), scale=.043, fg=(1, 1, 1, 1),
                                  align=TextNode.ALeft, mayChange=True, shadow=(0, 0, 0, 1))
    self.help_pg = self.text(self.ui_help, '', (0, -.71), .04, (.8, .8, .8, 1))
    self.button(self.ui_help, '< Prev', (-.5, -.8), lambda: self.show_help(self.help_page - 1), w=.32, h=.08, scale=.04)
    self.button(self.ui_help, 'Next >', (.5, -.8), lambda: self.show_help(self.help_page + 1), w=.32, h=.08, scale=.04)
    self.button(self.ui_help, 'Back', (0, -.8), self.close_help, w=.32, h=.08, scale=.04)
    self.ui_help.hide()
    self.help_page, self.help_back = 0, 'menu'


def _show_help(self, page=0):
    if self.ui_help.isHidden():
        self.help_back = 'pause' if self.state == 'paused' else 'menu'
    self.help_page = page % len(HELP_PAGES)
    title, body = HELP_PAGES[self.help_page]
    self.help_title.setText(title)
    self.help_body.setText(body)
    self.help_pg.setText('Page %d / %d' % (self.help_page + 1, len(HELP_PAGES)))
    self.show('help')


def _close_help(self):
    self.show(self.help_back)


# ---- Sillyland portal
def _frame_ok(self, ox, oy, oz, axis):
    w = self.world
    for a in range(5):
        for k in range(5):
            px, py = (ox + a, oy) if axis == 0 else (ox, oy + a)
            b = w.get(px, py, oz + k)
            ea, ek = a in (0, 4), k in (0, 4)
            if ea and ek:
                if b != SAND:
                    return False
            elif ea or ek:
                if b != COBBLE:
                    return False
            elif not (b == AIR or FAMILY[b] == LAVA):
                return False
    return True


def _try_portal(self, x, y, z):
    for axis in (0, 1):
        for ia in range(1, 4):
            for iz in range(1, 4):
                ox, oy = (x - ia, y) if axis == 0 else (x, y - ia)
                if self.frame_ok(ox, oy, z - iz, axis):
                    for a in range(1, 4):
                        for k in range(1, 4):
                            px, py = (ox + a, oy) if axis == 0 else (ox, oy + a)
                            self.world.set(px, py, z - iz + k, SILLY_PORTAL, upd=False)
                    c = (x + .5, y + .5, z + .5)
                    self.particles(c, 30, color=(.9, .5, 1.), spread=1.5, up=True)
                    self.sounds.play('portal', c)
                    self.say('The portal hums to life!')
                    self.adv('portal')
                    return True
    return False


def _build_portal_at(self, x, y, z):
    """Frame + portal along x, base at (x, y, z)."""
    w = self.world
    for a in range(-1, 6):
        for dy in (-2, -1, 0, 1, 2):
            w.set(x + a, y + dy, z - 1, SILLY_COBBLE if self.dim == 'silly' else COBBLE, upd=False)
            for k in range(0, 6):
                w.set(x + a, y + dy, z + k, AIR, upd=False)
    for a in range(5):
        for k in range(5):
            ea, ek = a in (0, 4), k in (0, 4)
            w.set(x + a, y, z + k, SAND if (ea and ek) else (COBBLE if (ea or ek) else SILLY_PORTAL), upd=False)


def _portal_step(self, dt):
    p = self.player
    inside = not p.dead and p.touching(SILLY_PORTAL)
    if inside and not self.portal_lock:
        self.portal_t += dt
        self.ov_water.setColor(.75, .3, .95, min(.7, self.portal_t * .35))
        self.ov_water.show()
        if self.portal_t > 2.:
            self.travel('over' if self.dim == 'silly' else 'silly')
    elif not inside:
        self.portal_t, self.portal_lock = 0., False


def _travel(self, dim, to_spawn=False):
    if self.net:
        self.say('Sillyland travel is single-player only for now')
        self.portal_lock = True
        return
    p = self.player
    if p.riding is not None:
        p.dismount()
    for lst in (self.mobs, self.items, self.fx):
        for e in lst:
            e.node.removeNode()
        lst.clear()
    for a_ in self.amb:
        a_[0].removeNode()
    self.amb = []
    self.precip.getChildren().detach()
    if self.rain_snd:
        self.rain_snd.stop()
    old = self.world
    old.root.stash()
    self.worlds[self.dim] = old
    self.dim = dim
    w = self.worlds.get(dim)
    if w is None:
        chunks, chests = self.dim_saved.pop(dim, ({}, {}))
        w = World(self, old.seed, chunks, chests, dim=dim)
        self.worlds[dim] = w
    else:
        w.root.unstash()
    self.world = w
    if to_spawn:
        p.pos = [self.spawn[0], self.spawn[1], p.pos[2]]
    self.arrival = ('spawn',) if to_spawn else (p.pos[0], p.pos[1])
    self.portal_lock, self.portal_t = True, 0.
    self.state = 'loading'
    self.load_txt.setText('Entering Sillyland...' if dim == 'silly' else 'Returning to the Overworld...')
    self.show('load')
    self.sounds.play('portal')
    if dim == 'silly':
        self.adv('silly')


def _arrive(self):
    p, w = self.player, self.world
    arr, self.arrival = self.arrival, None
    if arr[0] == 'spawn':
        p.pos = list(self.spawn) if self.spawn[2] is not None else [self.spawn[0], self.spawn[1], 80.]
        p.vel = [0., 0., 0.]
        return
    x, y = int(math.floor(arr[0])), int(math.floor(arr[1]))
    for r in range(0, 12):
        for dx in range(-r, r + 1):
            for dy in (-r, r) if abs(dx) != r else range(-r, r + 1):
                for z in range(4, H - 4):
                    if w.get(x + dx, y + dy, z) == SILLY_PORTAL and w.get(x + dx, y + dy, z - 1) != SILLY_PORTAL:
                        for ox, oy in ((0, -2), (0, 2), (-2, 0), (2, 0)):
                            px, py = x + dx + ox, y + dy + oy
                            if not SOLID[w.get(px, py, z)] and not SOLID[w.get(px, py, z + 1)]:
                                p.pos, p.vel = [px + .5, py + .5, float(z)], [0., 0., 0.]
                                return
    top = w.top_solid(x, y)
    if top < 4 or top > H - 10:
        top = 50
    z = top + 1
    self.build_portal_at(x - 2, y + 2, z)
    p.pos, p.vel, p.fall_start = [x + .5, y - .5, float(z)], [0., 0., 0.], None
    self.say('A portal formed behind you')


for _nm, _f in (('build_help', _build_help), ('show_help', _show_help), ('close_help', _close_help),
                ('frame_ok', _frame_ok), ('try_portal', _try_portal), ('build_portal_at', _build_portal_at),
                ('portal_step', _portal_step), ('travel', _travel), ('arrive', _arrive)):
    setattr(Game, _nm, _f)
def _reach(self):
    wp = WEAPONS.get(self.player.held()) if self.player else None
    return wp[2] if wp else REACH - 1


def _fire_grapple(self):
    e, d = self.eye(), self.look_dir()
    hit, prev, t = self.world.raycast(e, d, 32, OPAQUE)
    if hit is None:
        self.say('Nothing to hook onto')
        return
    self.player.grapple, self.player.grapple_t = (e[0] + d[0] * t, e[1] + d[1] * t, e[2] + d[2] * t), 0.
    self.sounds.play('zip')
    self.use_cd, self.swing = .8, 1.


def _fire_sling(self):
    p = self.player
    if self.mode == 'survival':
        if p.count_item(PEBBLE) == 0:
            self.say('You need pebbles!')
            return
        p.remove_item(PEBBLE, 1)
        self.refresh_inv()
    e, d = self.eye(), self.look_dir()
    self.fx.append(Arrow(self, (e[0] + d[0] * .6, e[1] + d[1] * .6, e[2] + d[2] * .6 - .1),
                         (d[0] * 26, d[1] * 26, d[2] * 26), p, 4.5, 'pebble'))
    self.sounds.play('twang', None, .6)
    self.use_cd, self.swing = .45, 1.


def _draw_rope(self):
    p = self.player
    if self.rope is not None:
        self.rope.removeNode()
        self.rope = None
    if p is not None and p.grapple is not None:
        ls = LineSegs()
        ls.setThickness(2)
        ls.setColor(.85, .8, .65, 1)
        e, d = self.eye(), self.look_dir()
        ls.moveTo(e[0] + d[0] * .6 + .15, e[1] + d[1] * .6, e[2] - .35)
        ls.drawTo(*p.grapple)
        self.rope = self.render.attachNewNode(ls.create())
        self.rope.setLightOff()


for _nm, _f in (('reach', _reach), ('fire_grapple', _fire_grapple), ('fire_sling', _fire_sling),
                ('draw_rope', _draw_rope)):
    setattr(Game, _nm, _f)
BIOME_MOBS[SILLY_B] = ('floatie', 'hopper', 'floatie')
BIOME_MOBS[PLAINS_B] = BIOME_MOBS[PLAINS_B] + ('horse', 'horse')
BIOME_MOBS[AUTUMN_B] = BIOME_MOBS[AUTUMN_B] + ('horse',)
for _b in (FOREST_B, TAIGA_B, SNOW_B):
    BIOME_MOBS[_b] = BIOME_MOBS[_b] + ('wolf',)
ADVANCEMENTS += [('portal', 'Silly Idea', 'Light a Sillyland portal'), ('silly', 'Silly Business', 'Enter Sillyland'),
                 ('ride', 'Giddy Up', 'Ride a mount'), ('sillium', 'Sillium Shine', 'Get a Sillium ingot'),
                 ('glide', 'Free as a Bird', 'Glide with a paraglider')]
ADV_NAMES.update({k: (t, d) for k, t, d in ADVANCEMENTS})



# ====================================================================== v5: boss, villages, fishing
class Bobber:
    def __init__(self, game, pos, vel):
        self.game, self.pos, self.vel = game, list(pos), list(vel)
        self.gone, self.state, self.t, self.bite = False, 'fly', random.uniform(4, 11), 0.
        self.node = NodePath('bobber')
        box_np(self.node, (-.06, -.06, -.06), (.06, .06, .06), (.9, .15, .15))
        box_np(self.node, (-.04, -.04, .06), (.04, .04, .12), (.95, .95, .95))
        self.node.setTextureOff(1)
        self.node.reparentTo(game.ent_root)

    def update(self, dt):
        g, w = self.game, self.game.world
        if math.dist(self.pos, g.player.pos) > 32:
            self.gone = True
            return
        cell = w.get(math.floor(self.pos[0]), math.floor(self.pos[1]), math.floor(self.pos[2]))
        if self.state == 'fly':
            self.vel[2] -= 18 * dt
            q = [self.pos[i] + self.vel[i] * dt for i in range(3)]
            b = w.get(math.floor(q[0]), math.floor(q[1]), math.floor(q[2]))
            if FAMILY[b] == WATER:
                self.state, self.pos = 'float', q
                self.pos[2] = math.floor(q[2]) + .85
                g.sounds.play('splash', self.pos, .5)
            elif SOLID[b]:
                self.state = 'ground'
            else:
                self.pos = q
        elif self.state == 'float':
            if FAMILY[cell] != WATER and FAMILY[w.get(math.floor(self.pos[0]), math.floor(self.pos[1]), math.floor(self.pos[2] - .5))] != WATER:
                self.state = 'fly'
                self.vel = [0., 0., 0.]
            self.t -= dt
            if self.bite > 0:
                self.bite -= dt
                if self.bite <= 0:
                    self.t = random.uniform(4, 11)
            elif self.t <= 0:
                self.bite = 1.3
                g.sounds.play('splash', self.pos, .8)
                g.particles(self.pos, 8, color=(.7, .8, 1.), up=True)
        bob = (math.sin(g.clock.getFrameTime() * 3) * .03 - (.18 if self.bite > 0 else 0)) if self.state == 'float' else 0
        self.node.setPos(self.pos[0], self.pos[1], self.pos[2] + bob)
        L = g.light_scale(*self.pos)
        self.node.setColorScale(L, L, L, 1)


FISH_LOOT = [(RAW_FISH, 70), (STICK, 4), (STRING, 4), (BONE, 4), (EMERALD, 5), (SADDLE, 2), (IRON_INGOT, 4),
             (GOLDEN_APPLE, 1), (HONEY, 3), (PRISM_SHARD, 2), (DIAMOND, 1)]


def _use_rod(self):
    p = self.player
    if self.bobber is not None and not self.bobber.gone:
        b = self.bobber
        if b.bite > 0:
            r = random.random() * sum(wt for _, wt in FISH_LOOT)
            for it, wt in FISH_LOOT:
                r -= wt
                if r <= 0:
                    break
            d = [p.pos[i] - b.pos[i] + (1.2 if i == 2 else 0) for i in range(3)]
            e = ItemDrop(self, b.pos, it, 1, (d[0] * 1.2, d[1] * 1.2, d[2] * 1.2 + 4))
            self.items.append(e)
            self.say('Caught: %s!' % item_name(it))
            self.adv('catch')
        b.gone = True
        b.node.removeNode()
        self.bobber = None
    else:
        e, d = self.eye(), self.look_dir()
        self.bobber = Bobber(self, (e[0] + d[0], e[1] + d[1], e[2] + d[2] - .2), (d[0] * 12, d[1] * 12, d[2] * 12 + 3))
        self.sounds.play('twang', None, .4)
    self.swing, self.use_cd = 1., .4


def _fish_step(self, dt):
    b = self.bobber
    if self.fishline is not None:
        self.fishline.removeNode()
        self.fishline = None
    if b is None:
        return
    if b.gone or self.player.held() != FISHING_ROD or self.player.dead:
        b.node.removeNode()
        self.bobber = None
        return
    b.update(dt)
    ls = LineSegs()
    ls.setThickness(1.5)
    ls.setColor(.9, .9, .9, 1)
    e, d = self.eye(), self.look_dir()
    ls.moveTo(e[0] + d[0] * .7 + .2, e[1] + d[1] * .7, e[2] + .1)
    ls.drawTo(*b.pos)
    self.fishline = self.render.attachNewNode(ls.create())
    self.fishline.setLightOff()


def _scepter(self):
    p = self.player
    e, d = self.eye(), self.look_dir()
    for k in range(5):
        a = (k - 2) * .09
        dx, dy = d[0] * math.cos(a) - d[1] * math.sin(a), d[0] * math.sin(a) + d[1] * math.cos(a)
        self.fx.append(Arrow(self, (e[0] + d[0] * .6, e[1] + d[1] * .6, e[2] - .1), (dx * 28, dy * 28, d[2] * 28 + 1), p, 6.,
                             'shard'))
    self.sounds.play('giggle', None, .6)
    self.use_cd, self.swing = 1.1, 1.


def _build_bossbar(self):
    self.boss, self.boss_t, self.village_t, self.bobber, self.fishline = None, 0., 0., None, None
    self.fov_cur = float(self.settings['fov'])
    self.bossbar = DirectFrame(parent=self.a2dTopCenter, frameColor=(.1, .05, .12, .85), frameSize=(-.62, .62, -.17, -.06))
    self.boss_fill = DirectFrame(parent=self.bossbar, frameColor=(.9, .3, .85, 1), frameSize=(-.6, .6, -.15, -.12))
    self.boss_name = OnscreenText(parent=self.bossbar, text='', pos=(0, -.105), scale=.042, fg=(1, .9, 1, 1),
                                  shadow=(0, 0, 0, 1), mayChange=True)
    self.bossbar.hide()


def _boss_step(self, dt):
    p, w = self.player, self.world
    b = self.boss
    if b is not None and (b.gone or b not in self.mobs):
        b = self.boss = None
    if b is not None and math.dist(b.pos, p.pos) < 64:
        f = max(0., b.hp / b.d['hp'])
        self.boss_fill['frameSize'] = (-.6, -.6 + 1.2 * f, -.15, -.12)
        self.boss_fill['frameColor'] = (1., .25, .3, 1) if f < .5 else (.9, .3, .85, 1)
        self.boss_name.setText('The Silly King' + ('  -  ENRAGED' if f < .5 else ''))
        self.bossbar.show()
    else:
        self.bossbar.hide()
    self.boss_t -= dt
    if self.boss_t > 0 or b is not None or self.dim != 'silly' or p.dead:
        return
    self.boss_t = 1.
    for a in list(w.markers[BOSS_ALTAR]):
        if math.dist(a, p.pos) < 16:
            self.spawn_mob('silly_king', (a[0] + .5, a[1] + 5.5, a[2] - 1))
            self.boss = self.mobs[-1]
            self.boss.altar = a
            self.say('The Silly King awakens!')
            self.sounds.play('portal')
            self.shake = .6
            break


def _boss_defeated(self, m):
    for it, a, b in ((SILLIUM_INGOT, 6, 10), (ROYAL_SCEPTER, 1, 1), (JELLY, 3, 5), (GOLDEN_APPLE, 2, 3)):
        self.spawn_item((m.pos[0], m.pos[1], m.pos[2] + 1), it, random.randint(a, b))
    if m.altar is not None:
        self.world.set(*m.altar, SILLIUM_BLOCK)
    self.boss = None
    self.adv('boss')
    self.say('The Silly King has been defeated!')
    self.sounds.play('explode', m.pos)


def _village_step(self, dt):
    self.village_t -= dt
    if self.village_t > 0:
        return
    self.village_t = 2.
    p, w = self.player, self.world
    for bell in list(w.markers[BELL]):
        if math.dist(bell, p.pos) > 56:
            continue
        if sum(1 for m in self.mobs if m.kind == 'villager' and math.dist(m.pos, bell) < 28) >= 4:
            continue
        x, y = bell[0] + random.randint(-8, 8), bell[1] + random.randint(-8, 8)
        if not w.loaded(x, y):
            continue
        z = w.light_top(x, y) + 1
        if not SOLID[w.get(x, y, z)] and not SOLID[w.get(x, y, z + 1)] and not FLUID[w.get(x, y, z)]:
            self.spawn_mob('villager', (x + .5, y + .5, z + .1))


def _trade(self, m):
    p = self.player
    (ci, cn), (gi, gn) = m.trade
    if self.mode == 'creative' or p.count_item(ci) >= cn:
        if self.mode != 'creative':
            p.remove_item(ci, cn)
        left = p.add_item(gi, gn)
        if left:
            self.spawn_item(p.pos, gi, left)
        self.say('Traded %d %s for %d %s' % (cn, item_name(ci), gn, item_name(gi)))
        self.sounds.play('hmm', m.pos)
        self.adv('trade')
        self.refresh_inv()
    else:
        self.say('Villager offers %d %s for %d %s' % (gn, item_name(gi), cn, item_name(ci)))


def _spawn_ambient(self, x, y, top):
    w = self.world
    biome, _ = w.gen.biome_at(x, y)
    if biome == SILLY_B:
        return 0
    ground, above = w.get(x, y, top), w.get(x, y, top + 1)
    green = biome in (PLAINS_B, FOREST_B, AUTUMN_B, TAIGA_B)
    day, r = self.daylight > .5 and self.rain < .3, random.random()
    if FAMILY[above] == WATER:
        if day and r < .5:
            z = top + 1
            while FAMILY[w.get(x, y, z + 1)] == WATER:
                z += 1
            self.spawn_mob('dragonfly', (x + .5, y + .5, z + 1.6))
            return 1
        return 0
    if r < .35 and green and self.daylight > .4:
        z = w.surface_z(x, y, top + 14)
        if z is None:
            return 0
        n = random.randint(2, 4)
        for _ in range(n):
            self.spawn_mob('bird', (x + .5 + random.uniform(-1, 1), y + .5 + random.uniform(-1, 1), z + 1.1))
        return n
    if SOLID[above]:
        return 0
    if r < .52 and green and day and ground == GRASS:
        self.spawn_mob('butterfly', (x + .5, y + .5, top + 1.6))
        return 1
    if r < .68 and green and day and ground == GRASS:
        for _ in range(random.randint(1, 3)):
            self.spawn_mob('bee', (x + .5 + random.uniform(-1, 1), y + .5 + random.uniform(-1, 1), top + 1.5))
        return 2
    if r < .84 and ground in (GRASS, DIRT, SAND, RED_SAND, DIRT_PATH) and day:
        n = random.randint(3, 6)
        for _ in range(n):
            self.spawn_mob('ant', (x + .5 + random.uniform(-.8, .8), y + .5 + random.uniform(-.8, .8), top + 1.05))
        return n
    if green and ground == GRASS and abs(top - SEA) <= 2:
        self.spawn_mob('frog', (x + .5, y + .5, top + 1.1))
        return 1
    return 0


for _nm, _f in (('use_rod', _use_rod), ('fish_step', _fish_step), ('scepter', _scepter), ('build_bossbar', _build_bossbar),
                ('boss_step', _boss_step), ('boss_defeated', _boss_defeated), ('village_step', _village_step),
                ('trade_with', _trade), ('spawn_ambient', _spawn_ambient)):
    setattr(Game, _nm, _f)
BIOME_MOBS[TAIGA_B] = BIOME_MOBS[TAIGA_B] + ('bear',)
BIOME_MOBS[FOREST_B] = BIOME_MOBS[FOREST_B] + ('bear',)
ADVANCEMENTS += [('boss', 'Silly Slayer', 'Defeat the Silly King'), ('trade', 'Wheeler Dealer', 'Trade with a villager'),
                 ('catch', 'Reel Talent', 'Catch something with a fishing rod')]
ADV_NAMES.update({k: (t, d) for k, t, d in ADVANCEMENTS})
HELP_PAGES.insert(6, ('Villages, fishing & the boss',
                      'Villages: houses, paths, a well, a farm and a bell. Villagers gather around the bell.\n'
                      'Right-click a villager to see their trade; right-click again with the price to trade.\n'
                      'Emeralds come from emerald ore (mountains), loot, fishing and selling wheat/coal/fish.\n\n'
                      'Fishing Rod (3 sticks + 2 string): right-click to cast into water. When the bobber dips\n'
                      'and splashes, right-click quickly to reel in fish - or treasure!\n\n'
                      'Weapons: every ore has a Spear (reach), Mace (heavy; double damage while falling),\n'
                      'Dagger (fast) and Battle Axe (huge hits). Craft them at a crafting table.\n\n'
                      'THE SILLY KING: find a Jelly Throne arena in Sillyland and step near the glowing altar.\n'
                      'He leaps and makes shockwaves, fires prism volleys and summons Gloops. Below half\n'
                      'health he gets angry. Reward: Sillium, golden apples and the Royal Scepter.'))


# ====================================================================== dedicated server (headless, Linux-friendly)
class _NullSounds:
    def play(self, *a, **k):
        pass


class HeadlessWorld(World):
    """The real World (same physics, saves, chunk format) without any rendering."""

    def __init__(self, server, seed, saved=None, chests=None):
        self.game, self.seed, self.dim = server, seed, 'over'
        self.gen = TerrainGen(seed)
        self.chunks, self.saved, self.chests = {}, dict(saved or {}), dict(chests or {})
        self.spawners, self.sched, self.pending, self.tick = {}, [], {}, 0
        self.net, self.remote_apply, self.no_physics, self.overrides = None, False, False, {}
        self.markers = {BOSS_ALTAR: set(), BELL: set()}
        self.futures, self.jobs, self.touched = {}, {}, {}

    def block_update(self, x, y, z):
        b = self.get(x, y, z)
        if b in (SAND, GRAVEL, RED_SAND):                 # no falling-block entity on a server: land it directly
            if z > 0 and REPL[self.get(x, y, z - 1)]:
                zz = z - 1
                while zz > 0 and REPL[self.get(x, y, zz - 1)]:
                    zz -= 1
                self.set(x, y, z, AIR)
                self.set(x, y, zz, b)
            return
        World.block_update(self, x, y, z)

    def explode(self, x, y, z, r):
        ix, iy, iz, ri = int(math.floor(x)), int(math.floor(y)), int(math.floor(z)), int(math.ceil(r))
        for dx in range(-ri, ri + 1):
            for dy in range(-ri, ri + 1):
                for dz in range(-ri, ri + 1):
                    if dx * dx + dy * dy + dz * dz > (r + random.random() * .6 - .3) ** 2:
                        continue
                    p = (ix + dx, iy + dy, iz + dz)
                    b = self.get(*p)
                    if BLAST[b]:
                        self.chests.pop(p, None)
                        self.set(*p, AIR)
                        if b == TNT:
                            self.game.timers.append((time.time() + random.uniform(.5, 1.2), p))

    def touch(self, key):
        self.touched[key] = time.time()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                self.ensure_chunk((key[0] + dx, key[1] + dy))

    def trim(self, keep_s=300):
        now = time.time()
        for k in list(self.chunks):
            ch = self.chunks[k]
            if not ch.modified and now - self.touched.get(k, 0) > keep_s:
                del self.chunks[k]


class DedicatedServer:
    TPS = 20

    def __init__(self, a):
        self.args, self.settings, self.mode = a, {'password': a.password or ''}, 'survival'
        self.sounds, self.timers, self.stop_flag = _NullSounds(), [], False
        self.inbox, self.conns, self.players, self.next_id, self.pending = queue.Queue(), {}, {}, 1, []
        self.path = os.path.abspath(os.path.expanduser(a.world))
        self.extra_dims, self.time_of_day, self.weather, self.rain = {}, .02, 'clear', 0.
        self.weather_t = random.uniform(300, 700)
        data = None
        if os.path.exists(self.path):
            with open(self.path, 'rb') as f:
                data = pickle.load(f)
        if data:
            dims = dict(data.get('dims') or {'over': (data.get('chunks') or {}, data.get('chests') or {})})
            over = dims.pop('over', ({}, {}))
            self.extra_dims = dims                       # Sillyland etc. are kept untouched in the file
            seed = data['seed']
            self.time_of_day, self.weather = data.get('time', .02), data.get('weather', 'clear')
            sp = data.get('spawn') or (data.get('player') or {}).get('spawn')
            self.log('Loaded world %s (seed %s, %d edited chunks)' % (self.path, seed, len(over[0])))
        else:
            seed = a.seed if a.seed is not None else random.randint(0, 2 ** 31)
            over, sp = ({}, {}), None
            self.log('Creating new world %s (seed %s)' % (self.path, seed))
        self.world = HeadlessWorld(self, seed, over[0], over[1])
        self.world.net = self
        self.spawn = (float(sp[0]), float(sp[1])) if sp else self.world.gen.find_spawn()

    # ---- stubs the World expects from the game
    def spawn_item(self, *a, **k):
        pass

    def add_fx(self, *a, **k):
        pass

    def particles(self, *a, **k):
        pass

    def on_local_set(self, x, y, z, b):
        self.pending.append([x, y, z, b])

    @staticmethod
    def log(msg):
        print(time.strftime('[%H:%M:%S] ') + msg, flush=True)

    # ---- networking
    def send(self, cid, msg):
        c = self.conns.get(cid)
        if c is not None:
            c.send(msg)

    def broadcast(self, msg, exclude=None):
        for cid in list(self.players):
            if cid != exclude:
                self.send(cid, msg)

    def chat(self, text, name=''):
        self.broadcast({'t': 'chat', 'name': name, 'msg': text[:200]})
        self.log(('<%s> ' % name if name else '* ') + text)

    def accept_loop(self):
        while not self.stop_flag:
            try:
                s, addr = self.srv.accept()
            except OSError:
                break
            cid, self.next_id = self.next_id, self.next_id + 1
            c = Conn(s, self.inbox, cid, start=False)
            self.inbox.put((cid, {'t': '_new', 'conn': c, 'addr': addr[0]}))
            c.start()

    def handle(self, cid, m):
        t, w = m.get('t'), self.world
        if t == '_new':
            self.conns[cid] = m['conn']
            self.log('Connection from %s' % m['addr'])
            return
        c = self.conns.get(cid)
        if c is None:
            return
        if t == 'hello':
            if m.get('v') != NET_VERSION:
                c.send({'t': 'kick', 'why': 'Different PyCraft version (server is protocol %d)' % NET_VERSION})
                return
            if self.settings['password'] and m.get('pw') != self.settings['password']:
                c.send({'t': 'kick', 'why': 'Wrong server password'})
                self.log('Rejected %s: wrong password' % m.get('name'))
                return
            if len(self.players) >= self.args.max_players:
                c.send({'t': 'kick', 'why': 'Server is full'})
                return
            name = ''.join(ch for ch in str(m.get('name', 'Player'))[:16] if ch.isprintable()) or 'Player'
            taken = {p['name'] for p in self.players.values()}
            base, n = name, 2
            while name in taken:
                name, n = '%s%d' % (base[:14], n), n + 1
            c.name = name
            chunks = {_k2s(k): base64.b64encode(v).decode() for k, v in w.save_chunks().items()}
            c.send({'t': 'welcome', 'id': cid, 'seed': w.seed, 'time': self.time_of_day, 'weather': self.weather,
                    'spawn': list(self.spawn), 'chunks': chunks, 'chests': {_k2s(k): v for k, v in w.chests.items()},
                    'players': [{'id': pid, 'name': p['name'], 'p': p['p']} for pid, p in self.players.items()]})
            self.players[cid] = {'name': name, 'p': [self.spawn[0], self.spawn[1], 60.]}
            self.broadcast({'t': 'join', 'id': cid, 'name': name}, exclude=cid)
            self.chat('%s joined the game (%d online)' % (name, len(self.players)))
        elif cid not in self.players:
            return                                        # ignore everything until a valid hello
        elif t == 'pos':
            try:
                self.players[cid]['p'] = [float(v) for v in m['p']][:3]
                out = {'t': 'pos', 'id': cid, 'p': self.players[cid]['p'], 'h': float(m['h']), 'pi': float(m['pi'])}
            except (KeyError, TypeError, ValueError):
                return
            self.broadcast(out, exclude=cid)
        elif t in ('sets', 'set'):
            lst = m.get('b', []) if t == 'sets' else [[m.get('x'), m.get('y'), m.get('z'), m.get('b')]]
            for e in lst[:4096]:
                try:
                    x, y, z, b = (int(v) for v in e)
                except (TypeError, ValueError):
                    continue
                if 0 <= z < H and (b == AIR or b in BDEF) and abs(x) < 3_000_000 and abs(y) < 3_000_000:
                    w.touch((x >> 4, y >> 4))
                    w.set(x, y, z, b)
        elif t == 'chat':
            self.chat(str(m.get('msg', ''))[:200], c.name)
        elif t == 'hit':
            if m.get('target') in self.players and m['target'] != cid:
                self.send(m['target'], {'t': 'hit', 'target': m['target'], 'dmg': min(40., float(m.get('dmg', 1))),
                                        'src': m.get('src')})
        elif t == 'chest_get':
            try:
                pos = _s2k(m['pos'])
            except (KeyError, ValueError):
                return
            c.send({'t': 'chest', 'pos': m['pos'], 'inv': w.chest_inv(pos)})
        elif t == 'chest_set':
            inv = m.get('inv')
            ok = isinstance(inv, list) and len(inv) == 27 and all(
                s is None or (isinstance(s, list) and len(s) == 2 and all(isinstance(v, int) for v in s) and 0 < s[1] <= 64)
                for s in inv)
            if ok:
                pos = _s2k(m['pos'])
                w.chests[pos] = inv
                self.broadcast({'t': 'chest', 'pos': m['pos'], 'inv': inv}, exclude=cid)
        elif t == 'prime':
            pos = _s2k(m['pos'])
            w.touch((pos[0] >> 4, pos[1] >> 4))
            if w.get(*pos) == TNT:
                w.set(*pos, AIR)
                self.timers.append((time.time() + 4., pos))
        elif t == '_closed':
            self.conns.pop(cid, None)
            p = self.players.pop(cid, None)
            if p:
                self.broadcast({'t': 'leave', 'id': cid})
                self.chat('%s left the game (%d online)' % (p['name'], len(self.players)))

    # ---- console
    def console_loop(self):
        while not self.stop_flag:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                return                                    # no terminal (e.g. systemd): just keep running
            self.inbox.put((-1, {'t': '_console', 'line': line.strip()}))

    def command(self, line):
        parts = line.split()
        if not parts:
            return
        c, args = parts[0].lower().lstrip('/'), parts[1:]
        if c == 'help':
            self.log('Commands: list, say <msg>, kick <name>, time day|night|<hour>, weather clear|rain|thunder, '
                     'save, stop')
        elif c == 'list':
            self.log('%d/%d online: %s' % (len(self.players), self.args.max_players,
                                           ', '.join(p['name'] for p in self.players.values()) or '-'))
        elif c == 'say':
            self.chat(' '.join(args), '[Server]')
        elif c == 'kick' and args:
            for pid, p in list(self.players.items()):
                if p['name'].lower() == args[0].lower():
                    self.send(pid, {'t': 'kick', 'why': 'Kicked by the server'})
                    self.log('Kicked ' + p['name'])
        elif c == 'time' and args:
            hours = {'day': 7, 'noon': 12, 'sunset': 18, 'night': 21, 'midnight': 0}.get(args[0])
            try:
                hours = float(args[0]) if hours is None else hours
            except ValueError:
                return self.log('Usage: time day|night|<hour>')
            self.time_of_day = ((hours - 6) / 24.) % 1.
            self.log('Time set')
        elif c == 'weather' and args and args[0] in ('clear', 'rain', 'thunder'):
            self.weather, self.weather_t = args[0], random.uniform(200, 400)
            self.log('Weather set to ' + args[0])
        elif c == 'save':
            self.save()
        elif c in ('stop', 'quit', 'exit'):
            self.stop_flag = True
        else:
            self.log('Unknown command - type help')

    # ---- persistence
    def save(self):
        w = self.world
        dims = dict(self.extra_dims)
        dims['over'] = (w.save_chunks(), {k: [list(s) if s else None for s in v] for k, v in w.chests.items()})
        data = dict(version=4, seed=w.seed, time=self.time_of_day, mode='survival', weather=self.weather, dim='over',
                    mounts=[], player=None, spawn=list(self.spawn), adv=[], dims=dims)
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        with open(self.path + '.tmp', 'wb') as f:
            pickle.dump(data, f, protocol=4)
        os.replace(self.path + '.tmp', self.path)
        self.log('World saved (%d edited chunks)' % len(dims['over'][0]))

    # ---- main loop
    def run(self):
        import signal
        a = self.args
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind((a.bind, a.port))
        self.srv.listen(16)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: setattr(self, 'stop_flag', True))
            except (ValueError, OSError):
                pass
        threading.Thread(target=self.accept_loop, daemon=True).start()
        threading.Thread(target=self.console_loop, daemon=True).start()
        self.log('PyCraft dedicated server listening on port %d (protocol %d, max %d players%s)' % (
            a.port, NET_VERSION, a.max_players, ', password protected' if self.settings['password'] else ''))
        self.log('LAN address: %s:%d   - type "help" for console commands' % (local_ip(), a.port))

        def go_public():
            h = None if a.no_upnp else upnp_open(a.port, 'PyCraft server')
            self.upnp = h
            ip = public_ip()
            if ip:
                self.log('Public address: %s:%d %s' % (ip, a.port, '(router port opened via UPnP)' if h else
                                                       '(make sure TCP %d is open in the firewall / forwarded)' % a.port))
        self.upnp = None
        threading.Thread(target=go_public, daemon=True).start()
        last, env_t, save_t = time.time(), 0., 0.
        try:
            while not self.stop_flag:
                now = time.time()
                dt, last = min(.25, now - last), now
                for _ in range(2000):
                    try:
                        cid, m = self.inbox.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        self.command(m['line']) if m.get('t') == '_console' else self.handle(cid, m)
                    except Exception as e:
                        self.log('error handling %s: %s' % (m.get('t'), e))
                for item in [t for t in self.timers if t[0] <= now]:
                    self.timers.remove(item)
                    self.world.explode(item[1][0] + .5, item[1][1] + .5, item[1][2] + .5, 4.)
                self.world.do_tick()
                if self.pending:
                    msg, self.pending = {'t': 'sets', 'b': self.pending}, []
                    self.broadcast(msg)
                self.time_of_day = (self.time_of_day + dt / DAY_LEN) % 1.
                self.weather_t -= dt
                if self.weather_t <= 0:
                    if self.weather == 'clear':
                        self.weather, self.weather_t = ('thunder' if random.random() < .3 else 'rain'), random.uniform(120, 260)
                    else:
                        self.weather, self.weather_t = 'clear', random.uniform(300, 700)
                target = {'clear': 0., 'rain': .8, 'thunder': 1.}[self.weather]
                self.rain += max(-dt * .07, min(dt * .07, target - self.rain))
                env_t -= dt
                if env_t <= 0:
                    env_t = 2.
                    self.broadcast({'t': 'env', 'time': self.time_of_day, 'weather': self.weather, 'rain': self.rain})
                save_t += dt
                if save_t > a.autosave:
                    save_t = 0.
                    self.save()
                    self.world.trim()
                time.sleep(max(0., 1. / self.TPS - (time.time() - now)))
        finally:
            self.log('Stopping server...')
            self.broadcast({'t': 'kick', 'why': 'Server closed'})
            time.sleep(.3)
            self.save()
            upnp_close(self.upnp)
            for c in list(self.conns.values()):
                c.close()
            self.srv.close()


def server_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='pycraft.py --server', description='PyCraft dedicated (headless) server')
    ap.add_argument('--server', action='store_true')
    ap.add_argument('--port', type=int, default=NET_PORT)
    ap.add_argument('--bind', default='', help='address to listen on (default: all interfaces)')
    ap.add_argument('--world', default=os.path.join(DATA_DIR, 'server_world.sav'),
                    help='world file (a singleplayer world.sav works too)')
    ap.add_argument('--seed', type=int, default=None, help='seed for a new world')
    ap.add_argument('--password', default=os.environ.get('PYCRAFT_PASSWORD', ''))
    ap.add_argument('--max-players', type=int, default=8)
    ap.add_argument('--autosave', type=float, default=120., help='seconds between autosaves')
    ap.add_argument('--no-upnp', action='store_true', help="don't ask the router to open the port")
    DedicatedServer(ap.parse_args(argv)).run()


if __name__ == '__main__':
    if '--server' in sys.argv:
        server_main(sys.argv[1:])
    else:
        Game().run()
