from model.Game import Game
from model.Move import Move
from model.Wizard import Wizard
from model.World import World
from model.LaneType import LaneType
from model.ActionType import ActionType
from model.Faction import Faction
from model.Message import Message
from random import choice, random
from math import sin, cos, fabs, pi
import copy


try:
    from debug_client import DebugClient
    from debug_client import Color
except:
    debug = None
else:
    debug = DebugClient()


def clamp(n, smallest, largest):
        return max(smallest, min(n, largest))


class MyStrategy:

    def __init__(self):
        # ------------------------------
        self.area_cope = [] # debug
        self.width = None
        self.x_cage_offset = None
        self.y_cage_offset = None
        self.for_debug_start = None
        # ------------------------------
        self.lane = None
        self.x, self.y = None, None
        self.lane_point_index = 0
        self.min_distance_to_enemy = float("inf")
        self.target_point_x, self.target_point_y = None, None
        self.step_point_x, self.step_point_y = None, None
        self.last5step = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]  # for stuck check
        self.stuck_start_tick = None
        self.faction = None
        self.enemy_faction = None
        self.is_fight = False
        self.last_tick = 0
        self.last_map_master_direction = 0
        self.get_out_bin = 1
        self.sin_table = [sin(pi/18*x) for x in range(-18, 19)]
        self.cos_table = [cos(pi/18*x) for x in range(-18, 19)]

    def move(self, me: Wizard, world: World, game: Game, move: Move):
        if world.tick_index == 0:
            self.init(me, move)
            return
        if world.tick_index < 10 and not me.master:
            if me.messages:
                for m in me.messages:
                    self.lane = m.lane
        if world.tick_index == 10 and self.lane is None:
            self.lane = choice([LaneType.BOTTOM, LaneType.MIDDLE, LaneType.TOP])

        if world.tick_index - self.last_tick > 500:  # check death
            self.lane_point_index = 0
            self.last_map_master_direction = 0
            self.stuck_start_tick = None
            self.is_fight = False
            self.lane_analysis(world)

        self.last_tick = world.tick_index
        move.speed = 0
        move.strafe_speed = 0
        move.turn = 0
        self.x = me.x
        self.y = me.y

        # Stuck
        if self.check_stuck(world.tick_index):
            self.get_out(move, game)
            self.debug_func(world)  # debug
            print("stuck")
            return

        # Escape
        if self.check_danger(me):
            if self.check_if_enemy_near(world, me, game):
                self.map_master(-1, me)
            else:
                self.map_master(1, me)
            self.step_point_x, self.step_point_y = self.find_way(world, me)
            self.go(me, move, game)
            self.debug_func(world)  # debug
            print("escape")
            return

        # Fight
        self.is_fight, enemy, distance_to_closest_minion, is_wizard = self.situation_analysis(world, me)
        if self.is_fight:
            self.attack(move, game, me, enemy)
            if (me.life < me.max_life * 0.5) or (distance_to_closest_minion < 200):
                self.map_master(-1, me)
                self.step_point_x, self.step_point_y = self.find_way(world, me)
                self.go_back(me, move, game)
            """else:
                    if not is_wizard and distance_to_closest_minion > 500 - 360 * (me.life / me.max_life):
                    self.map_master(1, me)
                    self.step_point_x, self.step_point_y = self.find_way(world, me)
                    self.go(me, move, game)"""
            self.debug_func(world)  # debug
            print("fight")
            return

        # GO
        if world.tick_index < 1500 - int(self.lane == LaneType.MIDDLE) * 220:  # wait for minions
            if me.y < 450 + me.x:
                self.map_master(-1, me)
            else:
                self.map_master(1, me)
        else:
            self.map_master(1, me)
        self.step_point_x, self.step_point_y = self.find_way(world, me)
        self.go(me, move, game)
        self.debug_func(world)  # debug
        print("GO")

    def attack(self, move, game, me, enemy):
        if enemy is None:
            return
        angle = me.get_angle_to(enemy.x, enemy.y)
        move.turn = angle
        if fabs(angle) < game.staff_sector / 2:
            move.cast_angle = angle
            move.min_cast_distance = me.get_distance_to(enemy.x, enemy.y) #- enemy.radius + game.getMagicMissileRadius
            move.action = ActionType.MAGIC_MISSILE

    def check_danger(self, me):
        if me.life < me.max_life * 0.3:
            return True
        else:
            return False

    def check_if_enemy_near(self, world, me, game):
        for i in world.wizards + world.buildings + world.minions:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < game.wizard_vision_range:
                    return True
        return False

    def check_stuck(self, tick):
        if self.stuck_start_tick is None:
            if self.is_fight:
                return False
            for i in range(4):
                self.last5step[i][0] = self.last5step[i + 1][0]
                self.last5step[i][1] = self.last5step[i + 1][1]
            self.last5step[4] = [self.x, self.y]
            for i in range(3):
                if self.last5step[i] != self.last5step[i + 1]:
                    return False
            else:
                self.stuck_start_tick = tick
                return True
        elif tick - self.stuck_start_tick > 15:
            self.get_out_bin *= -1
            self.stuck_start_tick = None
            return False
        else:
            return True

    def find_way(self, world, me):
        width = 20
        cage_length = 800
        half_cage_length = cage_length / 2
        area_len = int(cage_length / width - 1)
        if self.x > half_cage_length:
            x_cage_offset = int((self.x - half_cage_length) // width)
        else:
            x_cage_offset = int((self.x - half_cage_length) // width) + 1
        if self.y > half_cage_length:
            y_cage_offset = int((self.y - half_cage_length) // width)
        else:
            y_cage_offset = int((self.y - half_cage_length) // width) + 1
        stop_x = int(clamp(self.target_point_x // width - x_cage_offset, 0, area_len))
        stop_y = int(clamp(self.target_point_y // width - y_cage_offset, 0, area_len))
        area = [[0 for i in range(int(cage_length / width))] for j in range(int(cage_length / width))]
        for i in world.minions + world.buildings + world.trees + world.wizards:
            if (me.get_distance_to(i.x, i.y) > half_cage_length - width) or (i.x == me.x and i.y == me.y):
                continue
            add_radius_x = []
            add_radius_y = []
            for j in range(1, int((i.radius + me.radius) // width) + 1):
                for k in range(-18, 19):
                    add_radius_x.append((j * width) * self.sin_table[k] * 0.99)
                    add_radius_y.append((j * width) * self.cos_table[k] * 0.99)
            add_radius_x.append(0)
            add_radius_y.append(0)
            for j in range(len(add_radius_x)):
                if me.get_distance_to(i.x + add_radius_x[j], i.y + add_radius_y[j]) < half_cage_length - width:
                    area[int((i.x + add_radius_x[j]) // width - x_cage_offset)][int((i.y + add_radius_y[j]) // width - y_cage_offset)] = -1
        area[int(self.x // width - x_cage_offset)][int(self.y // width - y_cage_offset)] = 0
        # ------------------------------------
        self.area_cope = copy.deepcopy(area) # debug
        self.width = width # debug
        self.x_cage_offset = x_cage_offset
        self.y_cage_offset = y_cage_offset
        # ------------------------------------
        area[int(self.x // width - x_cage_offset)][int(self.y // width - y_cage_offset)] = 1
        points = [[int(self.x // width - x_cage_offset), int(self.y // width - y_cage_offset)]]  # Start points... ???
        index = 1
        break_flag = True
        # bfs
        while break_flag and len(points) != 0:
            index += 1
            add_to_points = []
            for i in points:
                x, y = i[0], i[1]
                if x == stop_x and y == stop_y:
                    break_flag = False
                    break
                if x != area_len:
                    if area[x+1][y] == 0:
                        area[x+1][y] = index
                        add_to_points.append([x+1, y])
                    if y != area_len:
                        if area[x+1][y+1] == 0:
                            area[x+1][y+1] = index
                            add_to_points.append([x+1, y+1])
                    if y != 0:
                        if area[x+1][y-1] == 0:
                            area[x+1][y-1] = index
                            add_to_points.append([x+1, y-1])
                if x != 0:
                    if area[x-1][y] == 0:
                        area[x-1][y] = index
                        add_to_points.append([x-1, y])
                    if y != area_len:
                        if area[x-1][y+1] == 0:
                            area[x-1][y+1] = index
                            add_to_points.append([x-1, y+1])
                    if y != 0:
                        if area[x-1][y-1] == 0:
                            area[x-1][y-1] = index
                            add_to_points.append([x-1, y-1])
                if y != area_len:
                    if area[x][y+1] == 0:
                        area[x][y+1] = index
                        add_to_points.append([x, y+1])
                if y != 0:
                    if area[x][y-1] == 0:
                        area[x][y-1] = index
                        add_to_points.append([x, y-1])
            points = add_to_points

        # find way in array
        index = area[stop_x][stop_y]
        x, y = stop_x, stop_y
        # debug
        self.for_debug_start = [(x + x_cage_offset) * width + width / 2, (y + y_cage_offset) * width + width / 2]
        self.for_debug = []
        # debug
        if index > 1:
            while index != 2:
                self.for_debug.append([x, y])
                index -= 1
                if y != area_len:
                    if area[x][y + 1] == index:
                        x, y = x, y + 1
                        continue
                if y != 0:
                    if area[x][y - 1] == 0:
                        x, y = x, y - 1
                        continue
                if x != area_len:
                    if area[x + 1][y] == index:
                        x, y = x + 1, y
                        continue
                    if y != area_len:
                        if area[x + 1][y + 1] == index:
                            x, y = x + 1, y + 1
                            continue
                    if y != 0:
                        if area[x + 1][y - 1] == index:
                            x, y = x + 1, y - 1
                            continue
                if x != 0:
                    if area[x - 1][y] == index:
                        x, y = x - 1, y
                        continue
                    if y != area_len:
                        if area[x - 1][y + 1] == index:
                            x, y = x - 1, y + 1
                            continue
                    if y != 0:
                        if area[x - 1][y - 1] == index:
                            x, y = x - 1, y - 1
                            continue
        return (x + x_cage_offset) * width + width / 2, (y + y_cage_offset) * width + width / 2

    def get_out(self, move, game):
        move.speed = -game.wizard_forward_speed
        move.strafe_speed = game.wizard_strafe_speed * 0.5 * self.get_out_bin
        move.turn = game.wizard_max_turn_angle * self.get_out_bin

    def go(self, me, move, game):
        angle = me.get_angle_to(self.step_point_x, self.step_point_y)
        move.turn = clamp(angle, -game.wizard_max_turn_angle, game.wizard_max_turn_angle)
        move.speed = game.wizard_forward_speed * cos(angle)
        move.strafe_speed = game.wizard_strafe_speed * sin(angle)

    def go_back(self, me, move, game):
        angle = me.get_angle_to(self.step_point_x, self.step_point_y)
        move.speed = game.wizard_backward_speed * cos(angle)
        move.strafe_speed = game.wizard_strafe_speed * sin(angle)

    def init(self, me, move):
        self.x = me.x
        self.y = me.y
        self.target_point_x, self.target_point_y = self.x, self.y
        self.faction = me.faction
        if self.faction == Faction.ACADEMY:
            self.enemy_faction = Faction.RENEGADES
        else:
            self.enemy_faction = Faction.ACADEMY
        if me.master:
            move.messages = [Message(LaneType.TOP, None, None),
                             Message(LaneType.BOTTOM, None, None),
                             Message(LaneType.BOTTOM, None, None),
                             Message(LaneType.BOTTOM, None, None)]
            self.lane = LaneType.MIDDLE

    def lane_analysis(self, world):
        top, mid, bot = 0, 0, 0
        for i in world.wizards:
            if i.faction == self.faction and (i.x != self.x and i.y != self.y):
                # Check if wizard in base
                if i.x < 800 and i.y > 3200:
                    continue
                # Count wizards on different lines
                y_2, y_1 = 3200 - i.x, 4800 - i.x
                if i.y < y_2:
                    top += 1
                if y_2 < i.y < y_1:
                    mid += 1
                if i.y > y_1:
                    bot += 1
        if mid == 0:
            self.lane = LaneType.MIDDLE
            return
        if bot == 0:
            self.lane = LaneType.BOTTOM
            return
        if top == 0:
            self.lane = LaneType.TOP
        if mid == 1:
            self.lane = LaneType.MIDDLE
            return
        if bot == 1:
            self.lane = LaneType.BOTTOM
            return
        if top == 1:
            self.lane = LaneType.TOP

    def map_master(self, direction, me):
        if self.last_map_master_direction == direction:
            if me.get_distance_to(self.target_point_x, self.target_point_y) > 200:
                return
        else:
            self.last_map_master_direction = direction
        if self.lane == LaneType.BOTTOM:
            self.lane_point_index = clamp(self.lane_point_index + direction, 0, 17)
            if self.lane_point_index <= 8:
                self.target_point_x = self.lane_point_index * 400 + 250
                self.target_point_y = 3750
            else:
                self.target_point_x = 3750
                self.target_point_y = 4000 - (self.lane_point_index - 8) * 400 - 250
        elif self.lane == LaneType.MIDDLE:
            self.lane_point_index = clamp(self.lane_point_index + direction, 0, 9)
            self.target_point_x = self.lane_point_index * 400 + 250
            self.target_point_y = 4000 - self.lane_point_index * 400 - 250
        elif self.lane == LaneType.TOP:
            self.lane_point_index = clamp(self.lane_point_index + direction, 0, 17)
            if self.lane_point_index <= 8:
                self.target_point_x = 200
                self.target_point_y = 4000 - self.lane_point_index * 400 - 250
            else:
                self.target_point_x = (self.lane_point_index - 8) * 400 + 250
                self.target_point_y = 250

    def situation_analysis(self, world, me):
        minions, wizards, buildings = [], [], []
        enemy, is_wizard = None, False
        distance_to_closest_minion = float("inf")
        for i in world.wizards:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    wizards.append(i)
        if len(wizards) > 0:
            enemy = min(wizards, key=lambda x: x.life)
            is_wizard = True
        for i in world.buildings:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    buildings.append(i)
        if len(buildings) > 0:
            if enemy is None:
                enemy = min(buildings, key=lambda x: x.life)
        for i in world.minions:
            if i.faction == self.enemy_faction:
                if me.get_distance_to(i.x, i.y) < me.cast_range:
                    minions.append(i)
        if len(minions) > 0:
            if enemy is None:
                enemy = min(minions, key=lambda x: x.life)
            closest_minion = min(minions, key=lambda x: me.get_distance_to(x.x, x.y))
            distance_to_closest_minion = me.get_distance_to(closest_minion.x, closest_minion.y)
        if enemy is None:
            return False, None, None, is_wizard
        else:
            return True, enemy, distance_to_closest_minion, is_wizard

    def debug_func(self, world):
        if world.tick_index % 15 != 0:
            return
        if debug:
            area = self.area_cope
            width = self.width
            with debug.pre() as dbg:
                for i in self.for_debug:
                    dbg.fill_circle((i[0]+ self.x_cage_offset) * width + width/2,
                                    (i[1] + self.y_cage_offset) * width + width/2, 10,
                                    Color(r=0.0, g=0.0, b=1.0))
                for i in range(len(area)):
                    for j in range(len(area)):
                        if area[i][j] == 0:
                            dbg.rect((i + self.x_cage_offset) * width,
                                     (j + self.y_cage_offset) * width,
                                     (i + 1 + self.x_cage_offset) * width,
                                     (j + 1 + self.y_cage_offset) * width,
                                     Color(r=0.0, g=0.0, b=0.0))
                        else:
                            dbg.fill_rect((i + self.x_cage_offset) * width,
                                          (j + self.y_cage_offset) * width,
                                          (i + 1 + self.x_cage_offset) * width,
                                          (j + 1 + self.y_cage_offset) * width,
                                          Color(r=0.0, g=0.0, b=0.0))
            with debug.post() as dbg:
                dbg.fill_circle(self.step_point_x, self.step_point_y, 10, Color(r=0.0, g=1.0, b=0.0))
                dbg.fill_circle(self.target_point_x, self.target_point_y, 20, Color(r=1.0, g=0.0, b=0.0))
                dbg.fill_circle(self.for_debug_start[0], self.for_debug_start[1], 40, Color(r=0.0, g=0.0, b=1.0))
